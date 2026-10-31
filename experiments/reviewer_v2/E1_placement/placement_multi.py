"""Segmented M2 placement over the graph-only M1 interface.

A state contains consecutive model segments. Each segment has one or more
complete, GPU-disjoint replicas. Replica chains may split or merge at segment
boundaries. Unassigned GPUs remain idle. This module never constructs request
events.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import time
from collections import defaultdict
from configparser import ConfigParser
from pathlib import Path

from rcaps.v3.resource_graph import from_topology, layer_dag
from rcaps.v3.topology import TopologyModel, profile_at


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DECODE_COST_WEIGHT = 8
WEIGHTS = (0.40, 0.35, 0.25)
BEAM_WIDTH = 64
STAGE_BUDGET = 500
MAX_ACCEPTED_MOVES = 16


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(state: dict) -> dict:
    """Remove JSON/int-key variation without changing replica order."""
    return {"segments": [
        {"start": int(segment["start"]), "end": int(segment["end"]),
         "replicas": [[int(node) for node in replica]
                      for replica in segment["replicas"]]}
        for segment in state["segments"]],
        "lengths": {int(node): int(value)
                    for node, value in state["lengths"].items()}}


def signature(state: dict) -> str:
    return json.dumps(normalize(state), sort_keys=True, separators=(",", ":"))


def from_single_boundary(state: dict, model: TopologyModel) -> dict:
    """Convert a single-boundary state into the segmented representation."""
    result = {"segments": [
        {"start": 0, "end": state["prefix_layers"],
         "replicas": [list(state["stem"])]},
        {"start": state["prefix_layers"], "end": model.layers,
         "replicas": [list(branch) for branch in state["branches"]]}],
        "lengths": dict(state["lengths"])}
    validate(model, result)
    return result


def _has_link(resources, left, right) -> bool:
    return (left, right) in resources.links


def _replica_edges(replica: list[int]) -> list[tuple[int, int]]:
    return list(zip(replica, replica[1:]))


def validate(model: TopologyModel, state: dict) -> dict:
    """Check canonical reachability, hardware capacity, and the full M1 DAG."""
    state = normalize(state)
    segments = state["segments"]
    if len(segments) not in (2, 3):
        raise ValueError("Expected one or two layer boundaries")
    if segments[0]["start"] != 0 or segments[-1]["end"] != model.layers:
        raise ValueError("Segments must cover the complete model")
    if any(segment["end"] <= segment["start"] for segment in segments):
        raise ValueError("Empty model segment")
    if any(left["end"] != right["start"]
           for left, right in zip(segments, segments[1:])):
        raise ValueError("Layer segment gap or overlap")
    resources = from_topology(model)
    spans = {}
    used = set()
    for segment in segments:
        replicas = segment["replicas"]
        if not 1 <= len(replicas) <= 4:
            raise ValueError("Replica width outside 1..4")
        for replica in replicas:
            if not replica:
                raise ValueError("Empty segment replica")
            cursor = segment["start"]
            for node in replica:
                if node not in resources.gpus or node in used:
                    raise ValueError(f"Unknown or reused GPU {node}")
                used.add(node)
                length = state["lengths"].get(node)
                if (length is None or length < 1 or
                        length > resources.gpus[node].capacity_layers):
                    raise ValueError(f"Invalid layer capacity on GPU {node}")
                if model.manager.get_kv_cache_capacity(model.types[node], length) <= 0:
                    raise ValueError(f"GPU {node} has no KV capacity")
                spans[node] = (cursor, cursor + length)
                cursor += length
            if cursor != segment["end"]:
                raise ValueError("Replica does not cover its segment")
            if any(not _has_link(resources, left, right)
                   for left, right in _replica_edges(replica)):
                raise ValueError("Missing internal physical link")
    if used != set(state["lengths"]):
        raise ValueError("Length allocation includes an idle GPU")
    entries = tuple(replica[0] for replica in segments[0]["replicas"])
    if any(not _has_link(resources, "source", entry) for entry in entries):
        raise ValueError("Missing source link")
    previous_reachable = set(range(len(entries)))
    transitions = []
    for level in range(len(segments) - 1):
        left_replicas = segments[level]["replicas"]
        right_replicas = segments[level + 1]["replicas"]
        level_edges = [(i, j) for i, left in enumerate(left_replicas)
                       for j, right in enumerate(right_replicas)
                       if _has_link(resources, left[-1], right[0])]
        next_reachable = {j for i, j in level_edges if i in previous_reachable}
        if next_reachable != set(range(len(right_replicas))):
            raise ValueError("A replica cannot be reached from the source")
        transitions.append(level_edges)
        previous_reachable = next_reachable
    last = segments[-1]["replicas"]
    if any(not _has_link(resources, replica[-1], "sink") for replica in last):
        raise ValueError("Missing sink link")
    can_finish = set(range(len(last)))
    for level in range(len(transitions) - 1, -1, -1):
        can_finish = {i for i, j in transitions[level] if j in can_finish}
        if can_finish != set(range(len(segments[level]["replicas"]))):
            raise ValueError("A replica cannot reach the sink")
    dag = layer_dag(resources, spans, entries)
    for segment in segments:
        for replica in segment["replicas"]:
            if any(edge not in dag.edge_set for edge in _replica_edges(replica)):
                raise ValueError("Canonical chain absent from M1 DAG")
    # The forward/backward transition checks above require every entry to reach the sink.
    if dag.path_count() < len(entries):
        raise ValueError("Not every entry has a complete path")
    return {"spans": spans, "dag": dag, "resources": resources,
            "transitions": transitions,
            "layer_copies": sum(end - start for start, end in spans.values()),
            "active_gpus": len(used), "idle_gpus": len(model.types) - len(used)}


def _transfer(resources, left, right) -> tuple[float, float, float]:
    link = resources.link(left, right)
    payload = (resources.token_bytes if left == "source" else
               resources.token_bytes + resources.activation_bytes)
    prompt = link.latency_s + payload * resources.prompt_tokens / link.bandwidth_bytes_per_s
    decode = link.latency_s + payload / link.bandwidth_bytes_per_s
    demand = (payload * resources.prompt_tokens / link.bandwidth_bytes_per_s +
              DECODE_COST_WEIGHT * payload / link.bandwidth_bytes_per_s)
    return prompt, decode, demand


def measure(model: TopologyModel, state: dict) -> dict:
    """Worst canonical path and equal-split static resource demand for M2."""
    state = normalize(state)
    checked = validate(model, state)
    spans, resources = checked["spans"], checked["resources"]
    segments, transitions = state["segments"], checked["transitions"]
    demand: dict[str, float] = defaultdict(float)
    # Probability is split evenly among physically reachable successors.
    probabilities = [[0.0] * len(segment["replicas"]) for segment in segments]
    for index in range(len(segments[0]["replicas"])):
        probabilities[0][index] = 1.0 / len(segments[0]["replicas"])
    worst_prompt = [[float("-inf")] * len(segment["replicas"]) for segment in segments]
    worst_decode = [[float("-inf")] * len(segment["replicas"]) for segment in segments]
    for index, replica in enumerate(segments[0]["replicas"]):
        source_prompt, source_decode, source_work = _transfer(resources, "source", replica[0])
        worst_prompt[0][index] = source_prompt
        worst_decode[0][index] = source_decode
        demand[f"link:source->{replica[0]}"] += source_work / len(segments[0]["replicas"])
    for level, segment in enumerate(segments):
        for index, replica in enumerate(segment["replicas"]):
            probability = probabilities[level][index]
            if probability <= 0:
                continue
            internal_prompt = internal_decode = 0.0
            for node in replica:
                length = state["lengths"][node]
                profile = resources.gpus[node].profile
                gpu_prompt = length * profile_at(profile.prompt_bs2time,
                                                 resources.prompt_tokens)
                gpu_decode = length * profile_at(profile.decode_bs2time,
                                                 resources.decode_batch)
                internal_prompt += gpu_prompt
                internal_decode += gpu_decode
                demand[f"gpu:{node}"] += probability * (
                    gpu_prompt + DECODE_COST_WEIGHT * gpu_decode)
            for left, right in _replica_edges(replica):
                prompt, decode, work = _transfer(resources, left, right)
                internal_prompt += prompt
                internal_decode += decode
                demand[f"link:{left}->{right}"] += probability * work
            worst_prompt[level][index] += internal_prompt
            worst_decode[level][index] += internal_decode
            if level == len(segments) - 1:
                prompt, decode, work = _transfer(resources, replica[-1], "sink")
                worst_prompt[level][index] += prompt
                worst_decode[level][index] += decode
                demand[f"link:{replica[-1]}->sink"] += probability * work
                continue
            successors = [j for i, j in transitions[level] if i == index]
            flow = probability / len(successors)
            for successor in successors:
                next_replica = segments[level + 1]["replicas"][successor]
                prompt, decode, work = _transfer(resources, replica[-1], next_replica[0])
                probabilities[level + 1][successor] += flow
                demand[f"link:{replica[-1]}->{next_replica[0]}"] += flow * work
                worst_prompt[level + 1][successor] = max(
                    worst_prompt[level + 1][successor],
                    worst_prompt[level][index] + prompt)
                worst_decode[level + 1][successor] = max(
                    worst_decode[level + 1][successor],
                    worst_decode[level][index] + decode)
    bottleneck = max(demand, key=demand.get)
    return {"ttft_s": max(worst_prompt[-1]),
            "tpot_s": max(worst_decode[-1]),
            "bottleneck_s": demand[bottleneck],
            "bottleneck_resource": bottleneck}


def objective(metrics: dict, reference: dict) -> float:
    return sum(weight * metrics[key] / reference[key]
               for weight, key in zip(WEIGHTS,
                                      ("ttft_s", "tpot_s", "bottleneck_s")))


def save(model: TopologyModel, template: Path, state: dict,
         destination: Path, metadata: dict) -> dict:
    """Export the unchanged simulator deployment format for this candidate."""
    state = normalize(state)
    checked = validate(model, state)
    spans, dag = checked["spans"], checked["dag"]
    destination.mkdir(parents=True, exist_ok=True)
    solution = ConfigParser()
    solution["Settings"] = {"offset": "2"}
    solution["Solution"] = {f"compute_node_{node + 2}": repr(list(range(*span)))
                            for node, span in sorted(spans.items())}
    solution_file = destination / "solution.ini"
    with solution_file.open("w", encoding="utf-8") as stream:
        solution.write(stream)
    simulator = ConfigParser()
    if not simulator.read(template):
        raise FileNotFoundError(template)
    for node, (start, end) in spans.items():
        kv = model.manager.get_kv_cache_capacity(model.types[node], end - start)
        if kv <= 0:
            raise ValueError(f"GPU {node} has no KV capacity")
        simulator[f"compute_node_{node + 2}"]["kv_cache_capacity"] = str(kv)
    for section in list(simulator.sections()):
        if section.startswith("link_"):
            simulator.remove_section(section)
    link_names = []
    for left, right in dag.edges:
        lookup = f"Link-{left}-{right}"
        if lookup not in model.config:
            lookup = f"Link-{right}-{left}"
        left_name = left if left == "source" else f"compute_node_{left + 2}"
        right_name = right if right == "sink" else f"compute_node_{right + 2}"
        name = f"link_{left_name}_{right_name}"
        link_names.append(name)
        simulator[name] = {"in": left_name, "out": right_name,
                           "latency": model.config[lookup]["latency"],
                           "bandwidth": model.config[lookup]["bandwidth"]}
    simulator["Links"]["names"] = repr(link_names)
    cluster_file = destination / "simulator_cluster.ini"
    with cluster_file.open("w", encoding="utf-8") as stream:
        simulator.write(stream)
    record = {"algorithm": "E1 multi-entry placement search",
              "state": state,
              "intervals": {str(node): list(span) for node, span in spans.items()},
              "widths": [len(item["replicas"]) for item in state["segments"]],
              "layer_copies": checked["layer_copies"],
              "active_gpus": checked["active_gpus"],
              "idle_gpus": checked["idle_gpus"],
              "compatibility_edges": len(dag.edges),
              "compatible_paths": dag.path_count(),
              "solution": solution_file.as_posix(),
              "simulator_cluster": cluster_file.as_posix(),
              "solution_sha256": digest(solution_file),
              "sim_cluster_sha256": digest(cluster_file), **metadata}
    (destination / "placement.json").write_text(json.dumps(record, indent=2) + "\n",
                                                 encoding="utf-8")
    return record


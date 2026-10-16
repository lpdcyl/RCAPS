"""Adaptive shared-stem and two/three-suffix placement search.

The frozen V2 path uses a six-request event graph as its placement surrogate.
An injected evaluator can score the same candidates without event simulation.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import time
from collections import defaultdict
from configparser import ConfigParser
from pathlib import Path
from typing import Callable

from .event_graph import interleaved_workload_graph
from .partition import ROOT, scenario
from .topology import TopologyModel, profile_at


ARRIVALS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25)
BEAM_WIDTH = 96
SHORTLIST_PER_FAMILY = 4
PlacementEvaluator = Callable[[TopologyModel, dict], dict]


def has_link(model: TopologyModel, left: str | int, right: str | int) -> bool:
    return (f"Link-{left}-{right}" in model.config or
            f"Link-{right}-{left}" in model.config)


def link_cost(model: TopologyModel, left: str | int, right: str | int) -> float:
    if not has_link(model, left, right):
        return float("inf")
    latency, bandwidth = model.link(left, right)
    return latency + model.manager.get_model_activation_size() / bandwidth


def route_order(model: TopologyModel, nodes: tuple[int, ...] | list[int],
                previous: str | int, *, terminal: bool = True) -> list[int] | None:
    pending = set(nodes)
    result = []
    while pending:
        node = min(pending, key=lambda item: (link_cost(model, previous, item),
                                               -model.capacity[item], item))
        if not has_link(model, previous, node):
            return None
        result.append(node)
        pending.remove(node)
        previous = node
    return result if not terminal or has_link(model, previous, "sink") else None


def allocate(model: TopologyModel, nodes: list[int], total: int) -> dict[int, int] | None:
    if not nodes or len(nodes) > total or sum(model.capacity[n] for n in nodes) < total:
        return None
    lengths = {node: 1 for node in nodes}
    costs = {}
    for node in nodes:
        profile = model.profiles[model.types[node]]
        costs[node] = (0.4 * profile_at(profile.prompt_bs2time, model.prompt_tokens) +
                       0.35 * profile_at(profile.decode_bs2time, model.decode_batch))
    for _ in range(total - len(nodes)):
        node = min((n for n in nodes if lengths[n] < model.capacity[n]),
                   key=lambda n: ((lengths[n] + 1) * costs[n], n), default=None)
        if node is None:
            return None
        lengths[node] += 1
    return lengths


def intervals(model: TopologyModel, state: dict) -> dict[int, tuple[int, int]]:
    stem = state["stem"]
    branches = state["branches"]
    if len(branches) not in (2, 3) or not stem or len(set(stem)) != len(stem):
        raise ValueError("Invalid stem or suffix count")
    used = set(stem)
    if any(model.types[node] != "A100" for node in stem):
        raise ValueError("Shared stem must use A100 GPUs")
    if not has_link(model, "source", stem[0]):
        raise ValueError("Missing source link")
    spans = {}
    position = 0
    for node in stem:
        length = state["lengths"][node]
        if not 1 <= length <= model.capacity[node]:
            raise ValueError(f"Invalid layer count on GPU {node}")
        spans[node] = (position, position + length)
        position += length
    if position != state["prefix_layers"] or position >= model.layers:
        raise ValueError("Invalid shared prefix coverage")
    for branch in branches:
        if not branch or not has_link(model, stem[-1], branch[0]):
            raise ValueError("Missing branch entry link")
        cursor = position
        for node in branch:
            if node in used:
                raise ValueError(f"GPU {node} appears more than once")
            used.add(node)
            length = state["lengths"][node]
            if not 1 <= length <= model.capacity[node]:
                raise ValueError(f"Invalid layer count on GPU {node}")
            spans[node] = (cursor, cursor + length)
            cursor += length
        if cursor != model.layers or not has_link(model, branch[-1], "sink"):
            raise ValueError("Branch does not complete the model")
    if used != set(model.types):
        raise ValueError("Every physical GPU must carry at least one layer")
    for route in [stem, *branches]:
        if any(not has_link(model, a, b) for a, b in zip(route, route[1:])):
            raise ValueError("Missing physical edge on canonical route")
    return spans


def stages(model: TopologyModel, state: dict, branch: list[int]) -> list[dict]:
    spans = intervals(model, state)
    result = []
    previous: str | int = "source"
    for node in [*state["stem"], *branch, "sink"]:
        latency, bandwidth = model.link(previous, node)
        token_size = model.manager.get_model_token_size()
        activation = model.manager.get_model_activation_size()
        if node == "sink":
            prefill = decode = 0.0
        else:
            length = spans[node][1] - spans[node][0]
            profile = model.profiles[model.types[node]]
            prefill = length * profile_at(profile.prompt_bs2time, model.prompt_tokens)
            decode = length * profile_at(profile.decode_bs2time, model.decode_batch)
        result.append({"device": str(node), "prefill_s": prefill,
                       "decode_s": decode, "incoming_link": f"{previous}->{node}",
                       "incoming_latency_s": latency,
                       "incoming_bytes_per_s": bandwidth,
                       "payload_bytes": (token_size if previous == "source" else
                                         token_size + activation),
                       "prefill_items": model.prompt_tokens})
        previous = node
    return result


def measure(model: TopologyModel, state: dict,
            arrivals_s: tuple[float, ...] = ARRIVALS) -> dict:
    pipelines = [stages(model, state, branch) for branch in state["branches"]]
    requests = [pipelines[i % len(pipelines)] for i in range(len(arrivals_s))]
    graph, first, final = interleaved_workload_graph(
        requests, prompt_tokens=model.prompt_tokens, generated_tokens=8,
        arrivals_s=list(arrivals_s))
    first_paths = [graph.critical_path(event) for event in first]
    final_paths = [graph.critical_path(event) for event in final]
    ttft = max(path.completion_s - arrival for path, arrival in zip(first_paths, arrivals_s))
    tpot = max((last.completion_s - start.completion_s) / 7
               for start, last in zip(first_paths, final_paths))
    demand: dict[str, float] = defaultdict(float)
    for pipeline in requests:
        for stage in pipeline:
            demand[f"link:{stage['incoming_link']}"] += (
                stage["payload_bytes"] / stage["incoming_bytes_per_s"])
            if stage["device"] != "sink":
                demand[f"gpu:{stage['device']}"] += max(
                    stage["prefill_s"] / model.prompt_tokens,
                    stage["decode_s"] / model.decode_batch)
    bottleneck = max(demand, key=demand.get)
    return {"ttft_s": ttft, "tpot_s": tpot, "bottleneck_s": demand[bottleneck],
            "bottleneck_resource": bottleneck}


def objective(metrics: dict, reference: dict) -> float:
    return (0.40 * metrics["ttft_s"] / reference["ttft_s"] +
            0.35 * metrics["tpot_s"] / reference["tpot_s"] +
            0.25 * metrics["bottleneck_s"] / reference["bottleneck_s"])


def reference_state(model: TopologyModel, name: str) -> dict:
    source = ROOT / "rcaps" / "layouts" / name / "placement.json"
    record = json.loads(source.read_text(encoding="utf-8"))
    spans = {int(node): span for node, span in record["intervals"].items()}
    return {"stem": [record["shared"]], "prefix_layers": spans[record["shared"]][1],
            "branches": record["branches"],
            "lengths": {node: end - start for node, (start, end) in spans.items()}}


def assign_branches(model: TopologyModel, remaining: list[int], k: int,
                    required: int) -> list[list[list[int]]]:
    """Capacity-feasible finite-width assignment beam over all remaining GPUs."""
    ordered = sorted(remaining, key=lambda n: (-model.capacity[n], n))
    total = sum(model.capacity[n] for n in ordered)
    if total < k * required:
        return []
    beam = [((tuple(() for _ in range(k))), (0,) * k)]
    seen = set()
    for index, node in enumerate(ordered):
        future = sum(model.capacity[n] for n in ordered[index + 1:])
        possibilities = []
        for branches, caps in beam:
            for target in range(k):
                next_branches = tuple(tuple((*branch, node)) if i == target else branch
                                      for i, branch in enumerate(branches))
                next_caps = tuple(caps[i] + (model.capacity[node] if i == target else 0)
                                  for i in range(k))
                if any(cap + future < required for cap in next_caps):
                    continue
                if any(len(branch) > required for branch in next_branches):
                    continue
                signature = tuple(sorted(tuple(sorted(branch)) for branch in next_branches))
                if signature in seen:
                    continue
                seen.add(signature)
                deficit = sum(max(0, required - cap) ** 2 for cap in next_caps)
                balance = max(next_caps) - min(next_caps)
                possibilities.append((deficit + 0.05 * balance,
                                      signature, next_branches, next_caps))
        possibilities.sort(key=lambda item: (item[0], item[1]))
        beam = [(branches, caps) for _, _, branches, caps in
                possibilities[:BEAM_WIDTH]]
        if not beam:
            return []
        seen.clear()
    result = []
    for branches, caps in beam:
        if min(caps) >= required and all(branches):
            result.append([list(branch) for branch in branches])
    return result[:8]


def cheap_cost(model: TopologyModel, state: dict) -> float:
    pipelines = [stages(model, state, branch) for branch in state["branches"]]
    prompt = []
    decode = []
    for pipeline in pipelines:
        prompt.append(sum(stage["prefill_s"] + stage["incoming_latency_s"] +
                          stage["payload_bytes"] * model.prompt_tokens /
                          stage["incoming_bytes_per_s"] for stage in pipeline))
        decode.append(sum(stage["decode_s"] + stage["incoming_latency_s"] +
                          stage["payload_bytes"] /
                          stage["incoming_bytes_per_s"] for stage in pipeline))
    return 0.4 * max(prompt) + 0.35 * max(decode)


def construct(model: TopologyModel, stem_nodes: tuple[int, ...], p: int,
              branches: list[list[int]]) -> dict | None:
    stem = route_order(model, stem_nodes, "source", terminal=False)
    if stem is None:
        return None
    ordered = [route_order(model, branch, stem[-1]) for branch in branches]
    if any(route is None for route in ordered):
        return None
    lengths = allocate(model, stem, p)
    if lengths is None:
        return None
    for route in ordered:
        allocation = allocate(model, route, model.layers - p)
        if allocation is None:
            return None
        lengths.update(allocation)
    state = {"stem": stem, "prefix_layers": p,
             "branches": ordered, "lengths": lengths}
    try:
        intervals(model, state)
    except ValueError:
        return None
    return state


def initial_states(model: TopologyModel, *, fixed_structure: bool,
                   branch_counts: tuple[int, ...] = (2, 3)) -> list[dict]:
    a100s = tuple(sorted(n for n, kind in model.types.items() if kind == "A100"))
    families: dict[tuple[int, int], list[tuple[float, dict]]] = defaultdict(list)
    stem_sizes = (1,) if fixed_structure else range(1, len(a100s) + 1)
    for size in stem_sizes:
        for shared in itertools.combinations(a100s, size):
            remaining = [n for n in sorted(model.types) if n not in shared]
            for k in ((2,) if fixed_structure else branch_counts):
                for p in ((model.capacity[shared[0]],) if fixed_structure else
                          range(size, sum(model.capacity[n] for n in shared) + 1)):
                    required = model.layers - p
                    if required <= 0 or sum(model.capacity[n] for n in remaining) < k * required:
                        continue
                    assignments = assign_branches(model, remaining, k, required)
                    for assignment in assignments:
                        state = construct(model, shared, p, assignment)
                        if state is not None:
                            families[(k, size)].append((cheap_cost(model, state), state))
    shortlisted = []
    for family in sorted(families):
        candidates = sorted(families[family], key=lambda item: (item[0],
                           tuple(item[1]["stem"]), item[1]["prefix_layers"],
                           tuple(tuple(b) for b in item[1]["branches"])))
        shortlisted.extend(state for _, state in candidates[:SHORTLIST_PER_FAMILY])
    if not shortlisted:
        raise ValueError("No feasible adaptive placement found")
    return shortlisted


def neighbors(model: TopologyModel, state: dict, *, allow_prefix: bool):
    for route_kind, routes in (("stem", [state["stem"]]),
                               ("branch", state["branches"])):
        for route_index, route in enumerate(routes):
            for index in range(len(route) - 1):
                left, right = route[index:index + 2]
                for donor, receiver in ((left, right), (right, left)):
                    if (state["lengths"][donor] <= 1 or
                            state["lengths"][receiver] >= model.capacity[receiver]):
                        continue
                    candidate = copy.deepcopy(state)
                    candidate["lengths"][donor] -= 1
                    candidate["lengths"][receiver] += 1
                    yield f"{route_kind}{route_index}:layer {donor}->{receiver}", candidate
                candidate = copy.deepcopy(state)
                selected = (candidate["stem"] if route_kind == "stem" else
                            candidate["branches"][route_index])
                selected[index:index + 2] = [right, left]
                yield f"{route_kind}{route_index}:swap {left}<->{right}", candidate
    if not allow_prefix:
        return
    if all(state["lengths"][path[0]] < model.capacity[path[0]]
           for path in state["branches"]):
        last = state["stem"][-1]
        if state["lengths"][last] > 1:
            candidate = copy.deepcopy(state)
            candidate["lengths"][last] -= 1
            for path in candidate["branches"]:
                candidate["lengths"][path[0]] += 1
            candidate["prefix_layers"] -= 1
            yield "prefix -1", candidate
    if all(state["lengths"][path[0]] > 1 for path in state["branches"]):
        last = state["stem"][-1]
        if state["lengths"][last] < model.capacity[last]:
            candidate = copy.deepcopy(state)
            candidate["lengths"][last] += 1
            for path in candidate["branches"]:
                candidate["lengths"][path[0]] -= 1
            candidate["prefix_layers"] += 1
            yield "prefix +1", candidate


def optimize(model: TopologyModel, name: str, *, fixed_structure: bool,
             max_steps: int = 16, branch_counts: tuple[int, ...] = (2, 3),
             use_frozen_reference: bool = True,
             evaluator: PlacementEvaluator | None = None) -> tuple[dict, dict]:
    started = time.perf_counter()
    evaluate = measure if evaluator is None else evaluator
    candidates = initial_states(model, fixed_structure=fixed_structure,
                                branch_counts=branch_counts)
    reference = (evaluate(model, reference_state(model, name))
                 if use_frozen_reference else evaluate(model, candidates[0]))
    evaluations = 0
    ranked = []
    for state in candidates:
        metrics = evaluate(model, state)
        evaluations += 1
        ranked.append((objective(metrics, reference), state, metrics))
    current_score, state, current = min(ranked, key=lambda item: item[0])
    trace = [{"step": 0, "score": current_score, "move": "best feasible initializer"}]
    for step in range(1, max_steps + 1):
        best = None
        for move, candidate in neighbors(model, state,
                                         allow_prefix=not fixed_structure):
            try:
                intervals(model, candidate)
                metrics = evaluate(model, candidate)
            except ValueError:
                continue
            evaluations += 1
            candidate_score = objective(metrics, reference)
            if candidate_score < current_score - 1e-9 and (
                    best is None or candidate_score < best[0]):
                best = (candidate_score, move, candidate, metrics)
        if best is None:
            break
        current_score, move, state, current = best
        trace.append({"step": step, "score": current_score, "move": move})
    return state, {"reference": reference, "metrics": current,
                   "score": current_score, "trace": trace,
                   "shortlisted_candidates": len(candidates),
                   "candidate_evaluations": evaluations,
                   "planning_s": time.perf_counter() - started}


def save(model: TopologyModel, template: Path, state: dict, destination: Path,
         metadata: dict, *, compatibility_dag=None) -> dict:
    spans = intervals(model, state)
    destination.mkdir(parents=True, exist_ok=True)
    solution = ConfigParser()
    solution["Settings"] = {"offset": "2"}
    solution["Solution"] = {f"compute_node_{node + 2}": repr(list(range(*span)))
                            for node, span in sorted(spans.items())}
    solution_file = destination / "solution.ini"
    with solution_file.open("w", encoding="utf-8") as stream:
        solution.write(stream)
    sim = ConfigParser()
    if not sim.read(template):
        raise FileNotFoundError(template)
    for node, (start, end) in spans.items():
        sim[f"compute_node_{node + 2}"]["kv_cache_capacity"] = str(
            model.manager.get_kv_cache_capacity(model.types[node], end - start))
    for section in list(sim.sections()):
        if section.startswith("link_"):
            sim.remove_section(section)
    if compatibility_dag is None:
        edges: list[tuple[str | int, str | int]] = [("source", state["stem"][0])]
        for left, (_, end) in spans.items():
            for right, (start, limit) in spans.items():
                if left != right and start <= end < limit and has_link(model, left, right):
                    edges.append((left, right))
            if end == model.layers and has_link(model, left, "sink"):
                edges.append((left, "sink"))
    else:
        if compatibility_dag.spans != spans or compatibility_dag.layers != model.layers:
            raise ValueError("Compatibility DAG does not match the placement")
        edges = list(compatibility_dag.edges)
    names = []
    for left, right in edges:
        lookup = f"Link-{left}-{right}"
        if lookup not in model.config:
            lookup = f"Link-{right}-{left}"
        left_name = left if left == "source" else f"compute_node_{left + 2}"
        right_name = right if right == "sink" else f"compute_node_{right + 2}"
        name = f"link_{left_name}_{right_name}"
        names.append(name)
        sim[name] = {"in": left_name, "out": right_name,
                     "latency": model.config[lookup]["latency"],
                     "bandwidth": model.config[lookup]["bandwidth"]}
    sim["Links"]["names"] = repr(names)
    cluster_file = destination / "simulator_cluster.ini"
    with cluster_file.open("w", encoding="utf-8") as stream:
        sim.write(stream)
    record = {"algorithm": "adaptive shared-stem replication search",
              "stem": state["stem"], "prefix_layers": state["prefix_layers"],
              "branches": state["branches"], "intervals": {str(k): list(v)
                                                             for k, v in spans.items()},
              "solution": solution_file.as_posix(),
              "simulator_cluster": cluster_file.as_posix(), **metadata}
    (destination / "placement.json").write_text(json.dumps(record, indent=2) + "\n",
                                                 encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, choices=("single", "multi"))
    parser.add_argument("--variant", required=True, choices=("adaptive", "fixed"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=16)
    args = parser.parse_args()
    cluster, template = scenario(args.scenario)
    model = TopologyModel(cluster)
    state, metrics = optimize(model, args.scenario,
                              fixed_structure=args.variant == "fixed",
                              max_steps=args.max_steps)
    record = save(model, template, state, args.output_dir, metrics)
    print(json.dumps({key: record[key] for key in
                      ("stem", "prefix_layers", "branches", "score",
                       "candidate_evaluations", "planning_s")}, indent=2))


if __name__ == "__main__":
    main()

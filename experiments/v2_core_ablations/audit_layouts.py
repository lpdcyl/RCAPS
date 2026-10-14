"""Check every ablation layout against the unchanged 24-GPU physical graph."""

from __future__ import annotations

import ast
import hashlib
import json
from configparser import ConfigParser
from pathlib import Path

from rcaps.placement.adaptive import has_link, intervals
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(solution_path: Path, cluster_path: Path, scenario: str) -> dict:
    physical, _ = scenario_files(scenario)
    model = TopologyModel(physical)
    placement_path = solution_path.parent / "placement.json"
    placement = json.loads(placement_path.read_text(encoding="utf-8"))
    state = {"stem": placement["stem"], "prefix_layers": placement["prefix_layers"],
             "branches": placement["branches"],
             "lengths": {int(node): end - start for node, (start, end)
                         in placement["intervals"].items()}}
    spans = intervals(model, state)
    if {str(node): list(pair) for node, pair in spans.items()} != placement["intervals"]:
        raise ValueError(f"Placement interval mismatch: {placement_path}")
    solution = ConfigParser()
    cluster = ConfigParser()
    if not solution.read(solution_path) or not cluster.read(cluster_path):
        raise ValueError(f"Cannot read layout: {solution_path}")
    if len(model.types) != 24 or len(spans) != 24:
        raise ValueError("Expected exactly 24 physical GPUs")
    for node, (start, end) in spans.items():
        name = f"compute_node_{node + 2}"
        loaded = ast.literal_eval(solution["Solution"][name])
        if loaded != list(range(start, end)):
            raise ValueError(f"Layer assignment mismatch: {name}")
        if cluster[name]["machine_type"].strip('"') != model.types[node]:
            raise ValueError(f"GPU type mismatch: {name}")
        expected_kv = model.manager.get_kv_cache_capacity(model.types[node], end - start)
        if int(cluster[name]["kv_cache_capacity"]) != expected_kv:
            raise ValueError(f"KV capacity mismatch: {name}")
    expected_edges = {("source", state["stem"][0])}
    for left, (_, end) in spans.items():
        for right, (start, limit) in spans.items():
            if left != right and start <= end < limit and has_link(model, left, right):
                expected_edges.add((left, right))
        if end == model.layers and has_link(model, left, "sink"):
            expected_edges.add((left, "sink"))
    actual_edges = {}
    for section in cluster.sections():
        if not section.startswith("link_"):
            continue
        def endpoint(value: str) -> str | int:
            return (value if value in ("source", "sink") else
                    int(value.removeprefix("compute_node_")) - 2)
        left = endpoint(cluster[section]["in"])
        right = endpoint(cluster[section]["out"])
        edge = (left, right)
        if edge in actual_edges:
            raise ValueError(f"Duplicate compatibility edge: {edge}")
        lookup = f"Link-{left}-{right}"
        if lookup not in model.config:
            lookup = f"Link-{right}-{left}"
        for field in ("latency", "bandwidth"):
            if cluster[section][field] != model.config[lookup][field]:
                raise ValueError(f"Physical {field} mismatch: {edge}")
        actual_edges[edge] = section
    if set(actual_edges) != expected_edges:
        raise ValueError(f"Compatibility edge mismatch: {cluster_path}")
    return {"physical_topology_sha256": digest(physical),
            "placement_sha256": digest(placement_path),
            "solution_sha256": digest(solution_path),
            "sim_cluster_sha256": digest(cluster_path),
            "gpu_count": len(spans), "compatibility_edge_count": len(actual_edges)}

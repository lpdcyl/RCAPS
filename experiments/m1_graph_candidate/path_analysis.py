"""Audit actual routed paths in the reused seed-0/1/2 formal windows."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from rcaps.placement.resource_graph import from_topology, layer_dag
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel

from .run import HERE, ROOT
from experiments.m1_simplification.evidence import digest


def deployment(name: str):
    layout = json.loads((HERE / "layouts" / name / "placement.json").read_text(encoding="utf-8"))
    physical, _ = scenario_files(name)
    model = TopologyModel(physical)
    spans = {int(gpu): tuple(span) for gpu, span in layout["intervals"].items()}
    graph = layer_dag(from_topology(model), spans, (layout["stem"][0],))
    canonical = {tuple(gpu + 2 for gpu in layout["stem"] + branch)
                 for branch in layout["branches"]}
    branch_of = {gpu: index for index, branch in enumerate(layout["branches"])
                 for gpu in branch}
    cross_edges = {(left, right) for left, right in graph.edges
                   if left in branch_of and right in branch_of
                   and branch_of[left] != branch_of[right]}
    return graph, canonical, cross_edges, branch_of


def analyze_window(name: str, seed: int, source: Path) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw["scenario"] != name or raw["seed"] != seed:
        raise ValueError(f"Wrong window identity: {source}")
    graph, canonical, cross_edges, _ = deployment(name)
    used_cross_edges = set()
    gpu_visits = Counter()
    routed = stitched = crossed = 0
    for encoded, count in raw["route_counts"].items():
        nodes = tuple(int(item) for item in encoded.split("-"))
        if count <= 0 or not nodes:
            raise ValueError(f"Invalid path count: {encoded}")
        physical_nodes = tuple(node - 2 for node in nodes)
        boundary = 0
        edges = [("source", physical_nodes[0]),
                 *zip(physical_nodes, physical_nodes[1:]),
                 (physical_nodes[-1], "sink")]
        if any(edge not in graph.edge_set for edge in edges):
            raise ValueError(f"Path uses undeployed edge: {encoded}")
        for gpu in physical_nodes:
            start, end = graph.spans[gpu]
            if not start <= boundary < end:
                raise ValueError(f"Path has a layer gap: {encoded}")
            boundary = end
            gpu_visits[gpu] += count
        if boundary != graph.layers:
            raise ValueError(f"Path does not finish the model: {encoded}")
        route_cross_edges = set(zip(physical_nodes, physical_nodes[1:])) & cross_edges
        if route_cross_edges:
            crossed += count
            used_cross_edges.update(route_cross_edges)
        if nodes not in canonical:
            stitched += count
        routed += count
    if routed > raw["arrivals"]:
        raise ValueError(f"More routed requests than arrivals: {source}")
    busy = {gpu: value for gpu, value in raw.get("gpu_busy_fraction", {}).items()
            if value is not None}
    return {
        "scenario": name, "seed": seed,
        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": digest(source),
        "trace_sha256": raw["trace_sha256"],
        "arrivals": raw["arrivals"], "routed_requests": routed,
        "not_routed_by_window_end": raw["arrivals"] - routed,
        "canonical_suffixes": len(canonical),
        "legal_complete_paths": graph.path_count(),
        "distinct_used_paths": len(raw["route_counts"]),
        "canonical_path_requests": routed - stitched,
        "noncanonical_path_requests": stitched,
        "noncanonical_path_fraction_of_routed": stitched / routed if routed else None,
        "legal_cross_suffix_edges": len(cross_edges),
        "distinct_used_cross_suffix_edges": len(used_cross_edges),
        "cross_suffix_path_requests": crossed,
        "cross_suffix_path_fraction_of_routed": crossed / routed if routed else None,
        "gpu_route_visits": {str(gpu): count for gpu, count in sorted(gpu_visits.items())},
        "gpu_busy_fraction": busy,
        "all_recorded_paths_valid": True,
    }


def collect() -> dict:
    index = json.loads((HERE / "run_index.json").read_text(encoding="utf-8"))
    rows = []
    for item in index:
        source_info = item["sources"]["m1_graph_candidate"]
        source = ROOT / source_info["source"]
        if digest(source) != source_info["sha256"]:
            raise ValueError(f"Changed formal source: {source}")
        rows.append(analyze_window(item["scenario"], item["seed"], source))
    return {"method": "m1_graph_candidate (audited static window reuse)",
            "denominator": "routed_requests; not all arrivals are necessarily routed by window end",
            "rows": rows}


def main() -> None:
    result = collect()
    output = HERE / "path_analysis.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

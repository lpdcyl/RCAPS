"""Summarize paired 70B search ablations and measured resource bottlenecks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, stdev

from experiments.validation_2026.equivalence import static_single_equals_coarse
from rcaps.placement.partition import scenario as placement_scenario, topology_groups
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METHODS = ("helix", "rcaps_coarse", "rcaps_full_search",
           "rcaps_static_no_graph", "rcaps")
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
RESOURCES = ("gpu_queue_request_s", "gpu_busy_fraction",
             "outbound_wait_request_s", "link_dispatch_wait_request_s",
             "link_service_request_s", "link_occupied_fraction",
             "link_propagation_request_s")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stats(values: list[float]) -> dict:
    return {"values": values, "mean": mean(values),
            "sd": stdev(values) if len(values) > 1 else 0.0}


def route_regions(routes: dict[str, int], region: dict[int, int]) -> dict:
    total = crossings = transitions = 0
    for route, count in routes.items():
        nodes = [int(part) - 2 for part in route.split("-") if part]
        changes = sum(region[left] != region[right]
                      for left, right in zip(nodes, nodes[1:]))
        total += count
        crossings += count * (changes > 0)
        transitions += count * changes
    return {"fraction_cross_region": crossings / total if total else None,
            "mean_region_transitions": transitions / total if total else None}


def collect() -> dict:
    result = {}
    if not static_single_equals_coarse():
        raise AssertionError("Single static layout no longer equals topology-only")
    for scenario in ("single", "multi"):
        model = TopologyModel(placement_scenario(scenario)[0])
        regions = {node: index for index, group in enumerate(topology_groups(model))
                   for node in group}
        seeds: dict[str, dict] = {}
        equivalent_reuse = []
        for seed in (0, 1, 2):
            runs = {}
            for method in METHODS:
                folder = (ROOT / "benchmarks/runs" if method == "helix" else
                          HERE / "runs70b")
                path = folder / scenario / f"seed{seed}" / f"{method}.json"
                if path.exists():
                    runs[method] = read(path)
                elif scenario == "single" and method == "rcaps_static_no_graph":
                    coarse = HERE / "runs70b" / scenario / f"seed{seed}" / "rcaps_coarse.json"
                    if coarse.exists():
                        runs[method] = read(coarse)
                        equivalent_reuse.append(seed)
            if not runs:
                continue
            hashes = {run["trace_sha256"] for run in runs.values()}
            if len(hashes) != 1:
                raise ValueError(f"Request trace mismatch: {scenario}, seed {seed}")
            seeds[str(seed)] = runs
        aggregates = {}
        for method in METHODS:
            rows = [seeds[str(seed)][method] for seed in (0, 1, 2)
                    if str(seed) in seeds and method in seeds[str(seed)]]
            if rows:
                aggregates[method] = {metric: stats([row[metric] for row in rows])
                                      for metric in METRICS}
        pairs = {}
        for left, right in (("rcaps_full_search", "rcaps_coarse"),
                            ("rcaps", "rcaps_full_search"),
                            ("rcaps", "rcaps_coarse"),
                            ("rcaps_static_no_graph", "rcaps_coarse"),
                            ("rcaps_static_no_graph", "helix"),
                            ("rcaps", "helix")):
            rows = [(seeds[str(seed)][left], seeds[str(seed)][right])
                    for seed in (0, 1, 2) if str(seed) in seeds and
                    left in seeds[str(seed)] and right in seeds[str(seed)]]
            if rows:
                pairs[f"{left}_minus_{right}"] = {
                    metric: stats([a[metric] - b[metric] for a, b in rows])
                    for metric in METRICS}
        retention = {}
        for metric in METRICS[:3]:
            values = []
            for seed in (0, 1, 2):
                row = seeds.get(str(seed), {})
                if not all(method in row for method in
                           ("helix", "rcaps_static_no_graph", "rcaps")):
                    continue
                baseline = row["helix"][metric]
                full = row["rcaps"][metric]
                static = row["rcaps_static_no_graph"][metric]
                denominator = full - baseline
                values.append(None if abs(denominator) < 1e-9 else
                              (static - baseline) / denominator)
            if values:
                valid = [value for value in values if value is not None]
                retention[metric] = {"values": values,
                                     "mean": mean(valid) if valid else None}
        profiles = {}
        for method in ("rcaps_coarse", "rcaps", "rcaps_static_no_graph"):
            rows = [seeds[str(seed)][method] for seed in (0, 1, 2)
                    if str(seed) in seeds and method in seeds[str(seed)] and
                    "gpu_queue_request_s" in seeds[str(seed)][method]]
            if not rows:
                continue
            profile = {}
            for metric in RESOURCES:
                keys = sorted(set().union(*(row.get(metric, {}) for row in rows)))
                profile[metric] = {key: stats([row.get(metric, {}).get(key, 0.0)
                                               for row in rows]) for key in keys}
            fractions = [route_regions(row["route_counts"], regions) for row in rows]
            for metric in ("fraction_cross_region", "mean_region_transitions"):
                profile[metric] = stats([row[metric] for row in fractions])
            profile["measured_resource_rankings"] = {
                metric: sorted(profile[metric],
                               key=lambda key: profile[metric][key]["mean"],
                               reverse=True)[:10]
                for metric in ("gpu_queue_request_s", "gpu_busy_fraction",
                               "outbound_wait_request_s",
                               "link_dispatch_wait_request_s",
                               "link_occupied_fraction")}
            profiles[method] = profile
        result[scenario] = {"seeds": {seed: list(rows) for seed, rows in seeds.items()},
                            "static_equivalence_reuse_seeds": equivalent_reuse,
                            "metrics": aggregates, "paired_differences": pairs,
                            "fraction_of_full_gain_retained": retention,
                            "resource_profile": profiles}
    costs = HERE / "placement_costs.json"
    return {"A_B_and_static_ablation": result,
            "placement_costs": read(costs) if costs.exists() else None,
            "seeds": [0, 1, 2],
            "statistical_significance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "summary.json")
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(), indent=2) + "\n",
                           encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

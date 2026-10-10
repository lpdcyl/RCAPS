"""Validate and summarize paired three-seed structure ablations."""

from __future__ import annotations

import hashlib
import json
import ast
import argparse
from configparser import ConfigParser
from pathlib import Path
from statistics import mean, stdev

from rcaps.placement.partition import ROOT, scenario as physical_scenario, topology_groups
from rcaps.placement.topology import TopologyModel
from experiments.validation_2026.summarize_cross import validate_physical_topology

from .run import ARMS, HERE, LOADS, REFERENCE


METRICS = (
    "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
    "completion_fraction", "backlog_at_window_end",
    "distinct_routes", "routed_queries", "mean_route_gpu_count",
    "mean_gpu_queue_s_per_arrival",
    "shared_gpu_queue_s_per_arrival", "shared_gpu_busy_fraction",
    "mean_outbound_wait_s_per_arrival", "mean_link_propagation_s_per_arrival",
    "mean_cross_region_hops_per_route", "branch0_used_fraction",
    "branch1_used_fraction", "stitched_route_fraction",
)
SAFE_LOADS = {"single": 200.0, "multi": 80.0}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metadata_for(scenario: str, arm: str, model: TopologyModel) -> dict:
    if arm == "s2_prefix12":
        placement = load(ROOT / "rcaps/layouts" / scenario / "placement.json")
        prefix_length = placement["intervals"][str(placement["shared"])][1]
        state = {"shared": placement["shared"], "shared_length": prefix_length,
                 "paths": placement["branches"],
                 "lengths": {int(node): end - start
                             for node, (start, end) in placement["intervals"].items()
                             if int(node) != placement["shared"]}}
        spans = model.intervals(state)
        assigned = sum(end - start for start, end in spans.values())
        active_capacity = sum(model.capacity[node] for node in spans)
        return {"state": state,
                "capacity": {"active_gpu_count": len(spans),
                             "physical_gpu_count": len(model.types),
                             "assigned_layer_replicas": assigned,
                             "active_layer_capacity": active_capacity,
                             "pool_layer_capacity": sum(model.capacity.values()),
                             "active_capacity_utilization": assigned / active_capacity,
                             "pool_capacity_utilization": assigned /
                             sum(model.capacity.values()),
                             "branch_capacities": [sum(model.capacity[node] for node in path)
                                                   for path in state["paths"]],
                             "canonical_path_count": 2},
                "solution": str(ROOT / "rcaps/layouts" / scenario / "solution.ini"),
                "simulator_cluster": str(ROOT / "rcaps/layouts" / scenario /
                                         "simulator_cluster.ini")}
    directory = HERE / "layouts" / scenario / arm
    metadata = load(directory / "structure.json")
    metadata["solution"] = str(directory / "solution.ini")
    metadata["simulator_cluster"] = str(directory / "simulator_cluster.ini")
    return metadata


def result_path(scenario: str, seed: int, arm: str, *, safe: bool) -> Path:
    if safe:
        return (HERE / "runs_safe_200_80" / scenario / f"seed{seed}" /
                f"{arm}.json")
    if arm == "s2_prefix12":
        return REFERENCE / scenario / f"seed{seed}" / "rcaps.json"
    return HERE / "runs70b" / scenario / f"seed{seed}" / f"{arm}.json"


def check_record(scenario: str, seed: int, arm: str,
                 record: dict, metadata: dict, offered: float) -> None:
    if record["scenario"] != scenario or record["seed"] != seed:
        raise ValueError(f"Wrong scenario/seed for {arm}")
    if record["method"] != "queue_dag":
        raise ValueError(f"Wrong scheduler for {arm}")
    if record["duration_s"] != 1800 or record["warmup_s"] != 0:
        raise ValueError(f"Wrong window for {arm}")
    if record["offered_tokens_per_s"] != offered:
        raise ValueError(f"Wrong offered load for {arm}")
    for path_key, hash_key in (("solution", "solution_sha256"),
                               ("simulator_cluster", "sim_cluster_sha256")):
        current = hashlib.sha256(Path(metadata[path_key]).read_bytes()).hexdigest()
        if record[hash_key] != current:
            raise ValueError(f"Stale {arm} {path_key}")
    config = ConfigParser()
    config.read(metadata["simulator_cluster"])
    if len(ast.literal_eval(config["ComputeNodes"]["names"])) != 24:
        raise ValueError(f"{arm} does not have the same 24 physical GPUs")


def measured(record: dict, metadata: dict, regions: dict[int, int]) -> dict:
    arrivals = record["arrivals"]
    routes = record["route_counts"]
    state = metadata["state"]
    branches = [set(node + 2 for node in path) for path in state["paths"]]
    routed = sum(routes.values())
    crossings = route_gpu_count = branch0 = branch1 = stitched = 0
    for route_text, count in routes.items():
        nodes = [int(value) - 2 for value in route_text.split("-")]
        route_gpu_count += count * len(nodes)
        crossings += count * sum(regions[left] != regions[right]
                                 for left, right in zip(nodes, nodes[1:]))
        if len(branches) == 2:
            used0 = bool(set(node + 2 for node in nodes) & branches[0])
            used1 = bool(set(node + 2 for node in nodes) & branches[1])
            branch0 += count * used0
            branch1 += count * used1
            stitched += count * (used0 and used1)
    shared_key = f"Compute-{state['shared'] + 2}"
    two_suffixes = len(branches) == 2
    return {
        **{name: record[name] for name in (
            "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
            "completion_fraction", "backlog_at_window_end")},
        "distinct_routes": len(routes), "routed_queries": routed,
        "mean_route_gpu_count": route_gpu_count / routed if routed else None,
        "mean_gpu_queue_s_per_arrival": sum(record["gpu_queue_request_s"].values()) / arrivals,
        "shared_gpu_queue_s_per_arrival": (record["gpu_queue_request_s"].get(shared_key, 0) / arrivals
                                           if two_suffixes else None),
        "shared_gpu_busy_fraction": (record["gpu_busy_fraction"].get(shared_key, 0)
                                     if two_suffixes else None),
        "mean_outbound_wait_s_per_arrival": sum(record["outbound_wait_request_s"].values()) / arrivals,
        "mean_link_propagation_s_per_arrival": sum(record["link_propagation_request_s"].values()) / arrivals,
        "mean_cross_region_hops_per_route": crossings / routed if routed else None,
        "branch0_used_fraction": branch0 / routed if routed and len(branches) == 2 else None,
        "branch1_used_fraction": branch1 / routed if routed and len(branches) == 2 else None,
        "stitched_route_fraction": stitched / routed if routed and len(branches) == 2 else None,
    }


def stats(values: dict[int, float | None]) -> dict:
    ordered = sorted((seed, value) for seed, value in values.items()
                     if value is not None)
    observed = [value for _, value in ordered]
    return {"seed_ids": [seed for seed, _ in ordered],
            "by_seed": observed, "n": len(observed),
            "mean": mean(observed) if observed else None,
            "sd": stdev(observed) if len(observed) > 1 else None}


def collect(*, safe: bool = False) -> dict:
    scenarios = {}
    loads = SAFE_LOADS if safe else LOADS
    for scenario in loads:
        model = TopologyModel(physical_scenario(scenario)[0])
        regions = {node: index for index, group in enumerate(topology_groups(model))
                   for node in group}
        arms = ("s1_all24", "s2_prefix12") if safe else ARMS[scenario]
        metadata = {arm: metadata_for(scenario, arm, model) for arm in arms}
        reference_sim = Path(metadata["s2_prefix12"]["simulator_cluster"])
        physical_validation = {
            arm: validate_physical_topology(
                scenario, reference_sim, Path(metadata[arm]["simulator_cluster"]))
            for arm in arms}
        records = {}
        measured_by_arm = {arm: {} for arm in arms}
        missing_by_seed = {}
        for seed in (0, 1, 2):
            records[seed] = {}
            for arm in arms:
                path = result_path(scenario, seed, arm, safe=safe)
                if not path.exists():
                    continue
                record = load(path)
                check_record(scenario, seed, arm, record, metadata[arm],
                             loads[scenario])
                records[seed][arm] = record
                measured_by_arm[arm][seed] = measured(record, metadata[arm], regions)
            if "s2_prefix12" not in records[seed]:
                raise ValueError(f"Missing S2 reference: {scenario} seed{seed}")
            missing_by_seed[str(seed)] = sorted(set(arms) - set(records[seed]))
            fields = ("trace_sha256", "arrivals", "duration_s", "warmup_s",
                      "offered_tokens_per_s", "evaluation_protocol")
            for field in fields:
                if len({record[field] for record in records[seed].values()}) != 1:
                    raise ValueError(f"{scenario} seed{seed}: unequal {field}")
            for arm in ("s1_all24", "s1_lean"):
                if arm not in measured_by_arm:
                    continue
                if (seed in measured_by_arm[arm] and
                        measured_by_arm[arm][seed]["distinct_routes"] != 1):
                    raise ValueError(f"{scenario} seed{seed}: {arm} is not single path")
        outcomes = {arm: {metric: stats({seed: row[metric]
                                         for seed, row in measured_by_arm[arm].items()})
                          for metric in METRICS}
                    for arm in arms}
        baseline = "s1_all24" if safe else "s1_lean"
        comparisons = {}
        for left, right in ((baseline, "s2_prefix12"),
                            *((arm, "s2_prefix12") for arm in arms
                              if arm.startswith("s3_"))):
            effects = {}
            for metric in METRICS:
                paired = {seed: measured_by_arm[right][seed][metric] -
                          measured_by_arm[left][seed][metric]
                          for seed in set(measured_by_arm[left]) &
                          set(measured_by_arm[right])
                          if (measured_by_arm[left][seed][metric] is not None and
                              measured_by_arm[right][seed][metric] is not None)}
                left_mean = outcomes[left][metric]["mean"]
                right_mean = outcomes[right][metric]["mean"]
                effects[metric] = {"absolute": stats(paired),
                                   "ratio_of_means_percent": (
                                       100 * (right_mean / left_mean - 1)
                                       if left_mean not in (None, 0) and
                                       right_mean is not None else None)}
            comparisons[f"{right}_vs_{left}"] = effects
        scenarios[scenario] = {
            "offered_tokens_per_s": loads[scenario],
            "arms": {arm: {"capacity": metadata[arm]["capacity"],
                           "enabled_layout_edges": physical_validation[arm][
                               "enabled_layout_edges"]["rcaps"],
                           "shared_prefix_length": metadata[arm]["state"]["shared_length"]
                           if arm.startswith("s2_") or arm.startswith("s3_") else None,
                           "canonical_path_count": len(metadata[arm]["state"]["paths"])}
                     for arm in arms},
            "outcomes": outcomes,
            "comparisons": comparisons,
            "trace_sha256_by_seed": {str(seed): records[seed]["s2_prefix12"]["trace_sha256"]
                                     for seed in (0, 1, 2)},
            "arrivals_by_seed": {str(seed): records[seed]["s2_prefix12"]["arrivals"]
                                 for seed in (0, 1, 2)},
            "missing_cells_by_seed": missing_by_seed,
            "infeasible_fixed_branch_prefix_lengths": [10] if scenario == "single" else [],
        }
    return {"model": "LLaMa70B", "window_s": 1800, "warmup_s": 0,
            "seeds": [0, 1, 2], "scheduler": "QueueAwareDagScheduler",
            "scenarios": scenarios,
            "interpretation": "All comparisons are paired within each topology. S1 changes replication and per-request hop count in addition to route redundancy; route use and queue data are reported separately.",
            "statistical_significance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safe-load", action="store_true")
    args = parser.parse_args()
    output = HERE / ("summary_safe.json" if args.safe_load else "summary.json")
    output.write_text(json.dumps(collect(safe=args.safe_load), indent=2) + "\n",
                      encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

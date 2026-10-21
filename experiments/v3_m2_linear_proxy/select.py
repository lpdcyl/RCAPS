"""Select placements from one fixed pre-existing pool with two M2 proxies."""

from __future__ import annotations

import json
from pathlib import Path

from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from experiments.v3_joint_routing_candidate.capacity import workload_classes
from experiments.v3_joint_routing_candidate.joint import case_inputs
from rcaps.v3.placement import digest, measure, objective

from .diagnose import CASES, HERE, ROOT, SOURCE
from .model import evaluate


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_paths(case: str) -> list[Path]:
    """Pre-existing V3 layouts only; no outcome-dependent candidate generation."""
    scenario = "single" if case == "C1_single" else "multi"
    paths = [ROOT / "rcaps/v3_layouts" / scenario]
    paths.extend(sorted((SOURCE / "layouts" / case).iterdir()))
    paths.extend(sorted((ROOT / "experiments/v3_joint_routing_candidate" /
                         "capacity_joint/layouts" / case).iterdir()))
    paths.extend(ROOT / row["layout"] for row in
                 read(ROOT / "experiments/v3_joint_routing_candidate/plans" /
                      f"{case}.json")["layouts"])
    return [path for path in paths if (path / "placement.json").is_file()]


def run() -> dict:
    references = read(ROOT / "rcaps/v3/planning_inputs.json")
    result = {"development_seed": 100, "development_seconds": 300,
              "formal_seeds": [0, 1, 2], "pool_rule":
              "released V3, all six search-sensitivity layouts, all three capacity-search exported layouts, and three earlier joint-candidate layouts; duplicate deployment hashes collapsed",
              "cases": {}}
    for case, offered_loads in CASES.items():
        model, physical, template = case_inputs(case)
        reference = measure(model, references[case]["reference_state"])
        # The high-load training trace fixes workload classes and arrival rate
        # before candidate scores are inspected. Online validation uses the
        # original fixed-window protocol at both previously declared loads.
        offered = offered_loads[-1]
        trace = OnlineRequestFeeder(cluster_token_throughput=offered,
                                    start_time=0, duration=300, seed=100).trace
        classes = workload_classes(trace)
        rate = len(trace) / 300
        rows = []
        seen = set()
        for path in candidate_paths(case):
            placement = read(path / "placement.json")
            deployment = (digest(path / "solution.ini"),
                          digest(path / "simulator_cluster.ini"))
            if deployment != (placement["solution_sha256"],
                              placement["sim_cluster_sha256"]):
                raise ValueError(f"Layout changed: {path}")
            if deployment in seen:
                continue
            seen.add(deployment)
            state = placement["state"]
            old_metrics = measure(model, state)
            linear = evaluate(model, template, state, classes, rate)
            if not linear["success"]:
                # A candidate that cannot carry the given mean rate has an
                # infinite LP service score; preserve it in the record.
                linear_score = None
            else:
                linear_score = linear["minimum_service_seconds_per_request"]
            rows.append({"label": path.relative_to(ROOT).as_posix(),
                         "solution_sha256": deployment[0],
                         "sim_cluster_sha256": deployment[1],
                         "weighted_score": objective(old_metrics, reference),
                         "linear_score": linear_score,
                         "linear_max_utilization":
                             linear.get("max_resource_utilization")})
        baseline = f"rcaps/v3_layouts/{'single' if case == 'C1_single' else 'multi'}"
        old_floor = min(row["weighted_score"] for row in rows)
        old_ties = [row for row in rows
                    if row["weighted_score"] <= old_floor + 1e-9]
        old = min(old_ties, key=lambda row: (row["label"] != baseline,
                                             row["label"]))
        valid = [row for row in rows if row["linear_score"] is not None]
        if not valid:
            raise ValueError(f"No LP-feasible candidate for {case}")
        new_floor = min(row["linear_score"] for row in valid)
        new_ties = [row for row in valid
                    if row["linear_score"] <= new_floor + 1e-9]
        new = min(new_ties, key=lambda row: (row["label"] != baseline,
                                             row["label"]))
        result["cases"][case] = {
            "physical_sha256": digest(physical),
            "template_sha256": digest(template),
            "training_offered_tokens_per_s": offered,
            "training_arrivals": len(trace),
            "training_requests_per_s": rate,
            "workload_classes": [vars(item) for item in classes],
            "candidate_count": len(rows), "candidates": rows,
            "weighted_selected": old["label"],
            "linear_selected": new["label"]}
    path = HERE / "selection_manifest.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return result


if __name__ == "__main__":
    selection = run()
    for case, item in selection["cases"].items():
        print(case, item["candidate_count"], item["weighted_selected"],
              item["linear_selected"])

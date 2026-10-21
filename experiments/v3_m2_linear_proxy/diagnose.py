"""Retrospective, hash-checked ranking audit on existing V3 sensitivity runs.

All proxy inputs come from development seed 100. Existing seed 0/1/2 online
windows are read only. This audit is exploratory because those windows were
already inspected before the proxy was designed.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from statistics import mean

from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from experiments.v3_joint_routing_candidate.capacity import solve, workload_classes
from experiments.v3_joint_routing_candidate.joint import case_inputs
from rcaps.v3.placement import digest

from .model import evaluate


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "experiments/v3_search_sensitivity"
CASES = {"C1_single": (350, 700), "C1_multi": (160, 320)}
SEEDS = (0, 1, 2)
LABELS = ("beam64_budget500", "beam32_budget500", "beam128_budget500",
          "beam64_budget250", "beam64_budget1000", "beam128_budget1000")
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pairwise(rows: list[dict], predicted: str, actual: str) -> dict:
    same = reversed_order = ties = 0
    for left, right in itertools.combinations(rows, 2):
        forecast = left[predicted] - right[predicted]
        observed = left["online_mean"][actual] - right["online_mean"][actual]
        if abs(forecast) < 1e-7 or abs(observed) < 1e-7:
            ties += 1
        elif forecast * observed > 0:
            same += 1
        else:
            reversed_order += 1
    return {"concordant": same, "discordant": reversed_order, "ties": ties}


def run() -> dict:
    index = read(SOURCE / "formal_index.json")["jobs"]
    output = {"development_seed": 100, "formal_seeds": list(SEEDS),
              "source_index_sha256": digest(SOURCE / "formal_index.json"),
              "cases": {}}
    for case, loads in CASES.items():
        model, _, template = case_inputs(case)
        case_output = {}
        for offered in loads:
            trace = OnlineRequestFeeder(cluster_token_throughput=offered,
                                        start_time=0, duration=300,
                                        seed=100).trace
            classes = workload_classes(trace)
            rate = len(trace) / 300
            rows = []
            trace_hashes = {seed: set() for seed in SEEDS}
            deployment_seen = set()
            for label in LABELS:
                layout = SOURCE / "layouts" / case / label
                placement = read(layout / "placement.json")
                deployment = (digest(layout / "solution.ini"),
                              digest(layout / "simulator_cluster.ini"))
                if deployment != (placement["solution_sha256"],
                                  placement["sim_cluster_sha256"]):
                    raise ValueError(f"Deployment hash changed: {case}/{label}")
                if deployment in deployment_seen:
                    continue
                deployment_seen.add(deployment)
                state = placement["state"]
                linear = evaluate(model, template, state, classes, rate)
                if not linear["success"]:
                    raise ValueError(f"Linear proxy infeasible: {case}/{label}")
                capacity = solve(model, template, state, classes)
                if not capacity["success"]:
                    raise ValueError(f"Capacity LP failed: {case}/{label}")
                outcomes = []
                for seed in SEEDS:
                    job = index[f"{case}/{label}/{offered}/seed{seed}"]
                    if job["status"] not in ("passed", "reused"):
                        raise ValueError(f"Formal window failed: {case}/{label}/{seed}")
                    path = ROOT / job["source"]
                    if digest(path) != job["sha256"]:
                        raise ValueError(f"Formal result changed: {path}")
                    if deployment != (job["identity"]["solution_sha256"],
                                      job["identity"]["sim_cluster_sha256"]):
                        raise ValueError(f"Formal layout differs: {path}")
                    data = read(path)
                    if data["trace_sha256"] != job["trace_sha256"]:
                        raise ValueError(f"Trace identity differs: {path}")
                    trace_hashes[seed].add(data["trace_sha256"])
                    outcomes.append({metric: data[metric] for metric in METRICS})
                rows.append({"label": label, "static_weighted_score": placement["score"],
                             "capacity_requests_per_s": capacity["requests_per_s"],
                             "linear_service_seconds_per_request":
                                 linear["minimum_service_seconds_per_request"],
                             "max_resource_utilization": linear["max_resource_utilization"],
                             "online_mean": {metric: mean(row[metric] for row in outcomes)
                                             for metric in METRICS},
                             "online_by_seed": outcomes})
            if any(len(hashes) != 1 for hashes in trace_hashes.values()):
                raise ValueError(f"Formal request traces differ: {case}/{offered}")
            summary = {"offered_tokens_per_s": offered,
                       "development_arrivals": len(trace),
                       "development_requests_per_s": rate,
                       "distinct_deployments": len(rows),
                       "formal_trace_sha256": {str(k): next(iter(v))
                                                for k, v in trace_hashes.items()},
                       "rows": rows,
                       "pairwise_tpot": {
                           "weighted": pairwise(rows, "static_weighted_score", "tpot_p95_s"),
                           "linear": pairwise(rows, "linear_service_seconds_per_request",
                                              "tpot_p95_s")},
                       "pairwise_ttft": {
                           "weighted": pairwise(rows, "static_weighted_score", "ttft_p95_s"),
                           "linear": pairwise(rows, "linear_service_seconds_per_request",
                                              "ttft_p95_s")}}
            case_output[str(offered)] = summary
        output["cases"][case] = case_output
    HERE.mkdir(parents=True, exist_ok=True)
    destination = HERE / "ranking_audit.json"
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return output


if __name__ == "__main__":
    result = run()
    for case, loads in result["cases"].items():
        for offered, row in loads.items():
            print(case, offered, row["distinct_deployments"],
                  row["pairwise_tpot"], row["pairwise_ttft"])

"""Pair queue-predictor runs with the unchanged-scheduler RCAPS reference."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from experiments.validation_2026.hotspot_audit import (placement_state,
                                                       profile_values, spearman)
from experiments.validation_2026.summarize_cross import validate_physical_topology
from rcaps.placement.partition import scenario
from rcaps.placement.queue_predictor import predict
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end", "gpu_queue_per_arrival")
LOADS = {"single": 700.0, "multi": 320.0}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metrics(row: dict) -> dict[str, float]:
    return {**{key: row[key] for key in METRICS if key in row},
            "gpu_queue_per_arrival": sum(row["gpu_queue_request_s"].values()) /
                                     row["arrivals"]}


def stats(values: list[float]) -> dict:
    return {"values": values, "mean": mean(values), "sd": stdev(values)}


def summarize() -> dict:
    result = {}
    for name in ("single", "multi"):
        model = TopologyModel(scenario(name)[0])
        layout = HERE / "layouts" / name
        physical_check = validate_physical_topology(
            name, ROOT / "rcaps/layouts" / name / "simulator_cluster.ini",
            layout / "simulator_cluster.ini")
        counts = physical_check["enabled_layout_edges"]
        physical_check["enabled_layout_edges"] = {
            "baseline_rcaps": counts["helix"],
            "queue_predictor": counts["rcaps"]}
        if len(model.intervals(placement_state(layout))) != 24:
            raise AssertionError(f"{name}: new layout does not activate all 24 GPUs")
        solution_hash = hashlib.sha256((layout / "solution.ini").read_bytes()).hexdigest()
        cluster_hash = hashlib.sha256((layout / "simulator_cluster.ini").read_bytes()).hexdigest()
        prediction = read(layout / "queue_prediction.json")
        predicted_queue = {int(node): value for node, value in
                           prediction["gpu_queue_pressure"].items()}
        predicted_busy = {int(node): value for node, value in
                          prediction["gpu_utilization"].items()}
        baseline_prediction = predict(model, placement_state(ROOT / "rcaps/layouts" / name),
                                      LOADS[name])
        placement = read(layout / "placement.json")
        rows = []
        for seed in (0, 1, 2):
            baseline = read(ROOT / "experiments/validation_2026/runs70b" /
                            name / f"seed{seed}" / "rcaps.json")
            current = read(HERE / "runs70b" / name / f"seed{seed}" /
                           "rcaps_queue_predictor.json")
            for key in ("trace_sha256", "duration_s", "offered_tokens_per_s",
                        "warmup_s", "arrivals", "evaluation_protocol"):
                if baseline[key] != current[key]:
                    raise AssertionError(f"{name} seed{seed}: {key} differs")
            if current["solution_sha256"] != solution_hash or current["sim_cluster_sha256"] != cluster_hash:
                raise AssertionError(f"{name} seed{seed}: wrong exported layout")
            actual_queue = profile_values(current, "gpu_queue_request_s", model.types)
            actual_busy = profile_values(current, "gpu_busy_fraction", model.types)
            baseline_queue = profile_values(baseline, "gpu_queue_request_s", model.types)
            baseline_busy = profile_values(baseline, "gpu_busy_fraction", model.types)
            rows.append({"seed": seed, "trace_sha256": current["trace_sha256"],
                         "baseline": metrics(baseline), "queue_predictor": metrics(current),
                         "baseline_top5_queue_gpus": sorted(
                             baseline_queue, key=baseline_queue.get, reverse=True)[:5],
                         "new_top5_queue_gpus": sorted(
                             actual_queue, key=actual_queue.get, reverse=True)[:5],
                         "baseline_layout_queue_rank_spearman": spearman(
                             baseline_prediction.gpu_queue_pressure, baseline_queue),
                         "baseline_layout_busy_rank_spearman": spearman(
                             baseline_prediction.gpu_utilization, baseline_busy),
                         "queue_rank_spearman": spearman(predicted_queue, actual_queue),
                         "busy_rank_spearman": spearman(predicted_busy, actual_busy),
                         "route_count": len(current["route_counts"])})
        result[name] = {
            "physical_check": physical_check,
            "planning": {"accepted_steps": len(placement["trace"]) - 1,
                         "candidate_evaluations": placement["trace"][0]["candidate_evaluations"],
                         "planning_s": placement["trace"][0]["planning_s"]},
            "seeds": rows,
            "aggregates": {
                key: {method: stats([row[method][key] for row in rows])
                      for method in ("baseline", "queue_predictor")}
                for key in METRICS},
            "paired_deltas_new_minus_baseline": {
                key: stats([row["queue_predictor"][key] - row["baseline"][key]
                            for row in rows]) for key in METRICS},
            "prediction_rank_correlations": {
                key: stats([row[key] for row in rows])
                for key in ("baseline_layout_queue_rank_spearman",
                            "baseline_layout_busy_rank_spearman",
                            "queue_rank_spearman", "busy_rank_spearman")}}
    return result


if __name__ == "__main__":
    summary = summarize()
    target = HERE / "summary.json"
    target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(target)

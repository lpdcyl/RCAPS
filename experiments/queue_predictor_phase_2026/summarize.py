"""Audit paired phase-predictor outcomes and resource rankings."""

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
LOADS = {"single": 700.0, "multi": 320.0}
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end", "gpu_queue_per_arrival")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metrics(run: dict) -> dict:
    return {**{field: run[field] for field in FIELDS if field in run},
            "gpu_queue_per_arrival": sum(run["gpu_queue_request_s"].values()) / run["arrivals"]}


def stats(values: list[float]) -> dict:
    return {"values": values, "mean": mean(values), "sd": stdev(values)}


def summarize() -> dict:
    output = {}
    for name, load in LOADS.items():
        model = TopologyModel(scenario(name)[0])
        layout = HERE / "layouts" / name
        original_layout = ROOT / "rcaps/layouts" / name
        physical = validate_physical_topology(
            name, original_layout / "simulator_cluster.ini",
            layout / "simulator_cluster.ini")
        if len(model.intervals(placement_state(layout))) != 24:
            raise AssertionError(f"{name}: expected all 24 GPUs active")
        expected_solution = hashlib.sha256((layout / "solution.ini").read_bytes()).hexdigest()
        expected_cluster = hashlib.sha256((layout / "simulator_cluster.ini").read_bytes()).hexdigest()
        prediction = predict(model, placement_state(layout), load, service_mode="phase")
        rows = []
        for seed in (0, 1, 2):
            original = read(ROOT / "experiments/validation_2026/runs70b" /
                            name / f"seed{seed}" / "rcaps.json")
            phase = read(HERE / "runs70b" / name / f"seed{seed}" / "rcaps_queue_phase.json")
            for field in ("trace_sha256", "duration_s", "offered_tokens_per_s",
                          "warmup_s", "arrivals", "evaluation_protocol"):
                if original[field] != phase[field]:
                    raise AssertionError(f"{name} seed{seed}: {field} differs")
            if (phase["solution_sha256"] != expected_solution or
                    phase["sim_cluster_sha256"] != expected_cluster):
                raise AssertionError(f"{name} seed{seed}: layout hash differs")
            actual_queue = profile_values(phase, "gpu_queue_request_s", model.types)
            actual_busy = profile_values(phase, "gpu_busy_fraction", model.types)
            rows.append({
                "seed": seed,
                "trace_sha256": phase["trace_sha256"],
                "original": metrics(original),
                "phase": metrics(phase),
                "queue_rank_spearman": spearman(prediction.gpu_queue_pressure, actual_queue),
                "busy_rank_spearman": spearman(prediction.gpu_utilization, actual_busy),
            })
        placement = read(layout / "placement.json")
        output[name] = {
            "physical_check": physical,
            "planning": {
                "accepted_steps": len(placement["trace"]) - 1,
                "candidate_evaluations": placement["trace"][0]["candidate_evaluations"],
                "planning_s": placement["trace"][0]["planning_s"],
            },
            "seeds": rows,
            "aggregate": {field: {
                arm: stats([row[arm][field] for row in rows])
                for arm in ("original", "phase")
            } for field in FIELDS},
            "paired_delta_phase_minus_original": {
                field: stats([row["phase"][field] - row["original"][field]
                              for row in rows]) for field in FIELDS},
            "prediction_ranks": {
                field: stats([row[field] for row in rows])
                for field in ("queue_rank_spearman", "busy_rank_spearman")},
        }
    return output


if __name__ == "__main__":
    result = summarize()
    target = HERE / "summary.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, data in result.items():
        print(name, data["planning"])
        for field, arms in data["aggregate"].items():
            print(field, *(f"{arm}={values['mean']:.4f}" for arm, values in arms.items()),
                  f"delta={data['paired_delta_phase_minus_original'][field]['mean']:.4f}")
        print("queue rank", data["prediction_ranks"]["queue_rank_spearman"]["mean"])
    print(target)

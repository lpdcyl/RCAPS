"""Audit the final topology-conditioned placement against original Helix."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNS = Path(__file__).resolve().parent / "runs"
BASE = ROOT / "experiments/graph_pipeline/runs/long"
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completed_request_throughput_per_s", "completion_fraction",
          "backlog_at_window_start", "backlog_at_window_end",
          "first_tokens_in_window", "queries_with_tpot_samples")


def read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data["seed"], data["duration_s"], data["warmup_s"]) != (1, 1980, 180):
        raise ValueError(f"Wrong experiment window: {path}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gains(new: dict, old: dict) -> dict:
    return {
        "throughput_increase_percent": 100 * (
            new["output_throughput_tokens_per_s"] /
            old["output_throughput_tokens_per_s"] - 1),
        "ttft_p95_reduction_percent": 100 * (
            1 - new["ttft_p95_s"] / old["ttft_p95_s"]),
        "tpot_p95_reduction_percent": 100 * (
            1 - new["tpot_p95_s"] / old["tpot_p95_s"]),
    }


def audit(name: str) -> dict:
    if name == "single":
        candidate_path = RUNS / "single_ensemble/long_fixed_seed1_1800.json"
        crossover_path = RUNS / "single/helix_layout_dag_fixed_seed1_1800.json"
        generated_layout = RUNS / "single_final/solution.ini"
        evaluated_layout = RUNS / "single_ensemble/solution.ini"
        generated_sim = RUNS / "single_final/simulator_cluster.ini"
        evaluated_sim = RUNS / "single_ensemble/simulator_cluster.ini"
        mode = "path_ensemble_demand"
        offered = 400
    else:
        candidate_path = RUNS / "multi/long_seed1_1800.json"
        crossover_path = RUNS / "multi/helix_layout_dag_seed1_1800.json"
        generated_layout = RUNS / "multi_final/solution.ini"
        evaluated_layout = RUNS / "multi/solution.ini"
        generated_sim = RUNS / "multi_final/simulator_cluster.ini"
        evaluated_sim = RUNS / "multi/simulator_cluster.ini"
        mode = "canonical_critical_path_demand"
        offered = 160
    candidate, crossover, original = (
        read(candidate_path), read(crossover_path),
        read(BASE / f"{name}_helix_seed1_1800.json"))
    if sha256(generated_layout) != sha256(evaluated_layout):
        raise ValueError(f"Generated layout differs from evaluated layout: {name}")
    if sha256(generated_sim) != sha256(evaluated_sim):
        raise ValueError(f"Generated cluster differs from evaluated cluster: {name}")
    if name == "single":
        # An old placement was evaluated by both the original tail-draining
        # driver and the fixed-window driver. Window-limited metrics must match
        # exactly before these two driver outputs are shown in one comparison.
        old_driver = read(RUNS / "single/long_seed1_1800.json")
        fixed_driver = read(RUNS / "single/critical_layout_dag_fixed_seed1_1800.json")
        if any(old_driver[field] != fixed_driver[field] for field in FIELDS):
            raise ValueError("Tail-drained and fixed-window metrics differ")
    for item in (candidate, crossover, original):
        if (item["scenario"] != name or item["offered_tokens_per_s"] != offered or
                item["arrivals"] != candidate["arrivals"]):
            raise ValueError(f"Trace or load mismatch: {name}")
    if candidate["method"] != "graph" or crossover["method"] != "graph" or \
            original["method"] != "helix":
        raise ValueError(f"Unexpected scheduler/method: {name}")
    layout_gain = gains(candidate, crossover)
    system_gain = gains(candidate, original)
    return {
        "scenario": name, "seed": 1, "measurement_s": 1800,
        "offered_tokens_per_s": offered, "arrivals": candidate["arrivals"],
        "placement_demand_mode": mode,
        "generated_solution_sha256": sha256(generated_layout),
        "evaluated_solution_sha256": sha256(evaluated_layout),
        "generated_sim_cluster_sha256": sha256(generated_sim),
        "evaluated_sim_cluster_sha256": sha256(evaluated_sim),
        "source_files": {"candidate": str(candidate_path),
                         "same_scheduler_control": str(crossover_path),
                         "original_helix": str(BASE / f"{name}_helix_seed1_1800.json")},
        "candidate": {field: candidate[field] for field in FIELDS},
        "same_scheduler_control": {field: crossover[field] for field in FIELDS},
        "original_helix": {field: original[field] for field in FIELDS},
        "placement_effect_same_scheduler": layout_gain,
        "system_effect_against_original_helix": system_gain,
        "placement_three_metrics_pass": all(value > 0 for value in layout_gain.values()),
        "system_three_metrics_pass": all(value > 0 for value in system_gain.values()),
    }


def main() -> None:
    report = {name: audit(name) for name in ("single", "multi")}
    report["all_placement_metrics_pass"] = all(
        report[name]["placement_three_metrics_pass"] for name in ("single", "multi"))
    report["all_system_metrics_pass"] = all(
        report[name]["system_three_metrics_pass"] for name in ("single", "multi"))
    output = RUNS / "comparison_final_seed1_1800.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

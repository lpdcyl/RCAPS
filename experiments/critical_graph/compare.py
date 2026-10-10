"""Audit the fixed 1800-second single-seed comparison against original Helix."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "experiments/graph_pipeline/runs/long"
RUNS = ROOT / "experiments/critical_graph/runs"
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completed_request_throughput_per_s", "e2e_p95_s",
          "completion_fraction", "backlog_at_window_start", "backlog_at_window_end")


def read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["seed"] != 1 or data["duration_s"] != 1980 or data["warmup_s"] != 180:
        raise ValueError(f"Wrong fixed-window protocol in {path}")
    return data


def compare(scenario: str) -> dict:
    baseline = read(BASE / f"{scenario}_helix_seed1_1800.json")
    candidate = read(RUNS / scenario / "long_seed1_1800.json")
    expected = 400 if scenario == "single" else 160
    if (baseline["scenario"] != candidate["scenario"] or
            baseline["offered_tokens_per_s"] != candidate["offered_tokens_per_s"] or
            baseline["offered_tokens_per_s"] != expected or
            baseline["arrivals"] != candidate["arrivals"]):
        raise ValueError(f"Trace or load mismatch for {scenario}")
    def changes(new: dict, old: dict) -> dict:
        return {
            "output_throughput_percent": 100 * (
                new["output_throughput_tokens_per_s"] /
                old["output_throughput_tokens_per_s"] - 1),
            "p95_ttft_reduction_percent": 100 * (
                1 - new["ttft_p95_s"] / old["ttft_p95_s"]),
            "p95_tpot_reduction_percent": 100 * (
                1 - new["tpot_p95_s"] / old["tpot_p95_s"]),
        }
    gain = changes(candidate, baseline)
    record = {"scenario": scenario, "seed": 1, "measurement_s": 1800,
            "arrivals_in_window": baseline["arrivals"],
            "offered_tokens_per_s": expected,
            "helix": {field: baseline[field] for field in FIELDS},
            "critical_graph": {field: candidate[field] for field in FIELDS},
            "against_helix": gain,
            "three_target_metrics_pass": all(value > 0 for value in gain.values())}
    crossover = RUNS / scenario / "helix_layout_dag_seed1_1800.json"
    if crossover.exists():
        shared_scheduler = read(crossover)
        if (shared_scheduler["arrivals"] != baseline["arrivals"] or
                shared_scheduler["offered_tokens_per_s"] != expected):
            raise ValueError(f"Crossover trace mismatch for {scenario}")
        record["helix_layout_dag_scheduler"] = {
            field: shared_scheduler[field] for field in FIELDS}
        record["placement_effect_same_scheduler"] = changes(candidate, shared_scheduler)
    return record


def main() -> None:
    summary = {scenario: compare(scenario) for scenario in ("single", "multi")}
    summary["all_target_metrics_pass"] = all(
        summary[scenario]["three_target_metrics_pass"]
        for scenario in ("single", "multi"))
    path = RUNS / "comparison_seed1_1800.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Audit full-window effects of the two topology-conditioned refinements."""

from __future__ import annotations

import json
from pathlib import Path


RUNS = Path(__file__).resolve().parent / "runs"
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completed_request_throughput_per_s", "completion_fraction",
          "backlog_at_window_start", "backlog_at_window_end",
          "first_tokens_in_window", "queries_with_tpot_samples")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_pair(before: dict, after: dict, name: str) -> None:
    for field in ("scenario", "method", "offered_tokens_per_s", "duration_s",
                  "warmup_s", "seed", "arrivals"):
        if before[field] != after[field]:
            raise ValueError(f"{name}: {field} mismatch")


def changes(after: dict, before: dict) -> dict:
    return {field + "_change_percent": 100 * (after[field] / before[field] - 1)
            for field in ("output_throughput_tokens_per_s", "ttft_p95_s",
                          "tpot_p95_s")}


def main() -> None:
    single_before = read(RUNS / "single/long_seed1_1800.json")
    single_after = read(RUNS / "single_ensemble/long_fixed_seed1_1800.json")
    multi_before = read(RUNS / "multi_coarse/long_fixed_seed1_1800.json")
    multi_after = read(RUNS / "multi/long_seed1_1800.json")
    verify_pair(single_before, single_after, "single")
    verify_pair(multi_before, multi_after, "multi")
    for label, old_path, fixed_path in (
        ("single", RUNS / "single/long_seed1_1800.json",
         RUNS / "single/critical_layout_dag_fixed_seed1_1800.json"),
        ("multi", RUNS / "multi/pilot_final_seed1_420.json",
         RUNS / "multi_final/pilot_fixed_seed1_420.json"),
    ):
        old, fixed = read(old_path), read(fixed_path)
        verify_pair(old, fixed, label + " protocol control")
        if any(old[field] != fixed[field] for field in FIELDS):
            raise ValueError(f"{label}: fixed-window/tail-drain metrics differ")
    report = {}
    for label, before, after in (("single", single_before, single_after),
                                 ("multi", multi_before, multi_after)):
        report[label] = {
            "scenario": label, "seed": 1, "measurement_s": 1800,
            "from": "canonical-only placement" if label == "single" else "coarse partition",
            "to": "path-ensemble refinement" if label == "single" else "canonical critical-path refinement",
            "before": {field: before[field] for field in FIELDS},
            "after": {field: after[field] for field in FIELDS},
            "effect": changes(after, before),
            "protocol_equivalence_control_pass": True,
        }
    output = RUNS / "ablation_final_seed1_1800.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

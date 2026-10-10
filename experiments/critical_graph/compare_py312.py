"""Audit the independent Python 3.12 full-window placement crossover."""

from __future__ import annotations

import json
from pathlib import Path


RUNS = Path(__file__).resolve().parent / "runs"


def main() -> None:
    candidate = json.loads((RUNS / "single_final/long_py312_seed1_1800.json").read_text(
        encoding="utf-8"))
    repeat = json.loads((RUNS / "single_final/long_py312_agg_repeat_seed1_1800.json").read_text(
        encoding="utf-8"))
    control = json.loads((RUNS / "single_final/helix_layout_dag_py312_seed1_1800.json").read_text(
        encoding="utf-8"))
    if candidate != repeat:
        raise ValueError("Repeated Python 3.12 candidate run differs")
    fields = ("scenario", "method", "offered_tokens_per_s", "duration_s",
              "warmup_s", "seed", "arrivals", "evaluation_protocol",
              "python_version", "numpy_version", "trace_sha256")
    if any(candidate[field] != control[field] for field in fields):
        raise ValueError("Python 3.12 comparison conditions or traces differ")
    if candidate["python_version"] != "3.12.14":
        raise ValueError("Unexpected Python version")
    gain = {
        "throughput_increase_percent": 100 * (
            candidate["output_throughput_tokens_per_s"] /
            control["output_throughput_tokens_per_s"] - 1),
        "ttft_p95_reduction_percent": 100 * (
            1 - candidate["ttft_p95_s"] / control["ttft_p95_s"]),
        "tpot_p95_reduction_percent": 100 * (
            1 - candidate["tpot_p95_s"] / control["tpot_p95_s"]),
    }
    result = {"protocol": {field: candidate[field] for field in fields},
              "candidate": {key: candidate[key] for key in
                            ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")},
              "helix_layout_same_scheduler": {key: control[key] for key in
                                               ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")},
              "placement_effect": gain,
              "three_target_metrics_pass": all(value > 0 for value in gain.values()),
              "candidate_repeat_exact_match": True}
    output = RUNS / "comparison_py312_seed1_1800.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

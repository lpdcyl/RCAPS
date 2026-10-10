"""Audit fixed-horizon comparisons without mixing tail-drained results."""

from __future__ import annotations

import json
from pathlib import Path


RUNS = Path(__file__).resolve().parent / "runs"
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completed_request_throughput_per_s", "completion_fraction",
          "backlog_at_window_start", "backlog_at_window_end",
          "first_tokens_in_window", "queries_with_tpot_samples")


def read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data["evaluation_protocol"] != "fixed_window_no_tail_drain" or
            data["seed"] != 1 or data["duration_s"] != 1980 or
            data["warmup_s"] != 180):
        raise ValueError(f"Protocol mismatch: {path}")
    return data


def changes(new: dict, old: dict) -> dict:
    return {
        "output_throughput_percent": 100 * (new["output_throughput_tokens_per_s"] /
                                           old["output_throughput_tokens_per_s"] - 1),
        "p95_ttft_reduction_percent": 100 * (1 - new["ttft_p95_s"] / old["ttft_p95_s"]),
        "p95_tpot_reduction_percent": 100 * (1 - new["tpot_p95_s"] / old["tpot_p95_s"]),
    }


def scenario(name: str) -> dict:
    directory = RUNS / name
    files = {
        "critical_layout_dag": "critical_layout_dag_fixed_seed1_1800.json",
        "helix_layout_dag": "helix_layout_dag_fixed_seed1_1800.json",
        "original_helix": "helix_fixed_seed1_1800.json",
    }
    available = {label: read(directory / file) for label, file in files.items()
                 if (directory / file).exists()}
    if not available:
        return {}
    reference = next(iter(available.values()))
    offered = 400 if name == "single" else 160
    if any(data["scenario"] != name or data["offered_tokens_per_s"] != offered or
           data["arrivals"] != reference["arrivals"] for data in available.values()):
        raise ValueError(f"Trace/load mismatch: {name}")
    digests = {data["trace_sha256"] for data in available.values()
               if "trace_sha256" in data}
    if len(digests) > 1:
        raise ValueError(f"Request trace digest mismatch: {name}")
    result = {"scenario": name, "seed": 1, "measurement_s": 1800,
              "arrivals": reference["arrivals"], "offered_tokens_per_s": offered,
              "methods": {label: {field: data[field] for field in FIELDS}
                          for label, data in available.items()}}
    if "critical_layout_dag" in available and "helix_layout_dag" in available:
        result["placement_effect_same_scheduler"] = changes(
            available["critical_layout_dag"], available["helix_layout_dag"])
    if "critical_layout_dag" in available and "original_helix" in available:
        result["against_original_helix"] = changes(
            available["critical_layout_dag"], available["original_helix"])
    return result


def main() -> None:
    report = {name: scenario(name) for name in ("single", "multi")}
    path = RUNS / "comparison_fixed_seed1_1800.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

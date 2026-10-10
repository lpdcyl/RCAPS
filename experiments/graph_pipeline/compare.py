"""Summarize the held-out single-seed comparison and crossover controls."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "experiments/graph_pipeline/runs"
BASE = ROOT / "experiments/archive/slo_placement/runs"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(scenario):
    if scenario == "single":
        baseline = read(BASE / "baseline_seed1_400_600.json")
    else:
        baseline = read(BASE / "distributed/baseline_seed1_160_600.json")
    candidate = read(RUNS / f"{scenario}_seed1_600.json")
    crossover = RUNS / f"{scenario}_crossover_seed1_600.json"
    crossover = read(crossover) if crossover.exists() else None
    keys = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
            "e2e_p95_s", "completion_fraction", "backlog_at_window_end")
    result = {"scenario": scenario,
              "baseline": {key: baseline[key] for key in keys},
              "candidate": {key: candidate[key] for key in keys},
              "crossover": {key: crossover[key] for key in keys} if crossover else None,
              "seed": candidate["seed"], "duration_s": candidate["duration_s"],
              "warmup_s": candidate["warmup_s"]}
    for name, reference in (("against_helix", baseline), ("placement_only", crossover)):
        if reference is None:
            continue
        result[name] = {
            "throughput_gain_percent": 100 * (candidate[keys[0]] / reference[keys[0]] - 1),
            "ttft_reduction_percent": 100 * (1 - candidate[keys[1]] / reference[keys[1]]),
            "tpot_reduction_percent": 100 * (1 - candidate[keys[2]] / reference[keys[2]]),
        }
        result[name]["all_three_pass"] = all(value > 0 for value in result[name].values())
    return result


def main():
    results = [summarize(name) for name in ("single", "multi")]
    target = RUNS / "comparison_seed1_600.json"
    target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

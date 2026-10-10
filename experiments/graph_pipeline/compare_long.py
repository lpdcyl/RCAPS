"""Compare all completed 1800-second measurement windows with exact trace checks."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "experiments/graph_pipeline/runs/long"
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completed_request_throughput_per_s", "e2e_p95_s",
           "completion_fraction", "backlog_at_window_start", "backlog_at_window_end",
           "first_tokens_in_window", "queries_with_tpot_samples")


def read(name):
    path = RUNS / f"{name}_seed1_1800.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["seed"] == 1
    assert result["duration_s"] == 1980 and result["warmup_s"] == 180
    return result


def compare(candidate, baseline):
    return {
        "throughput_gain_percent": 100 * (candidate[METRICS[0]] / baseline[METRICS[0]] - 1),
        "ttft_reduction_percent": 100 * (1 - candidate[METRICS[1]] / baseline[METRICS[1]]),
        "tpot_reduction_percent": 100 * (1 - candidate[METRICS[2]] / baseline[METRICS[2]]),
    }


def main():
    output = {}
    for scenario in ("single", "multi"):
        helix = read(f"{scenario}_helix")
        refined = read(f"{scenario}_refined")
        assert helix["arrivals"] == refined["arrivals"], "The online traces differ"
        record = {"offered_tokens_per_s": helix["offered_tokens_per_s"],
                  "arrivals_in_window": helix["arrivals"],
                  "helix": {key: helix[key] for key in METRICS},
                  "refined": {key: refined[key] for key in METRICS},
                  "against_helix": compare(refined, helix)}
        if scenario == "multi":
            initial = read("multi_initial")
            assert initial["arrivals"] == helix["arrivals"]
            record["initial"] = {key: initial[key] for key in METRICS}
            record["refinement_gain"] = compare(refined, initial)
        output[scenario] = record
    output["all_target_metrics_pass"] = all(
        all(value > 0 for value in output[name]["against_helix"].values())
        for name in ("single", "multi"))
    target = RUNS / "comparison_seed1_1800.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

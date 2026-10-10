"""Compare the primary method with any registered baseline on paired traces."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from .registry import MAIN_METHOD, METHODS
from .run import DEFAULT_RESULTS, output_file


METRICS = {
    "output_throughput_tokens_per_s": "higher",
    "ttft_p95_s": "lower",
    "tpot_p95_s": "lower",
}
MATCH_FIELDS = ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                "warmup_s", "evaluation_protocol", "trace_sha256",
                "query_samples_schema", "python_version", "numpy_version",
                "arrivals")


def read_record(results_dir: Path, scenario: str, seed: int,
                method: str) -> dict:
    path = output_file(results_dir, scenario, seed, method)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("system") != method:
        raise ValueError(f"Method identity mismatch: {path}")
    return record


def common_cohort(candidate: dict, reference: dict) -> dict:
    """Compare observed latency on exactly the same request IDs."""
    left = candidate["query_samples"]
    right = reference["query_samples"]
    if set(left) != set(right) or len(left) != candidate["arrivals"]:
        raise ValueError("Paired runs have different query identifiers")
    for uid in left:
        for field in ("arrival_s", "input_tokens", "output_tokens"):
            same = (math.isclose(left[uid][field], right[uid][field],
                                 rel_tol=0, abs_tol=1e-9)
                    if field == "arrival_s" else
                    left[uid][field] == right[uid][field])
            if not same:
                raise ValueError(f"Paired query {uid} differs in {field}")
    result = {"seed": candidate["seed"], "arrivals": len(left),
              "both_completed": sum(left[uid]["completed"] and
                                    right[uid]["completed"] for uid in left)}
    for field in ("ttft_s", "tpot_s"):
        ids = [uid for uid in left if left[uid][field] is not None and
               right[uid][field] is not None]
        result[field] = {
            "both_observed": len(ids),
            "main_p95_s": float(np.percentile([left[uid][field] for uid in ids], 95))
            if ids else None,
            "baseline_p95_s": float(np.percentile([right[uid][field] for uid in ids], 95))
            if ids else None,
        }
    return result


def paired_summary(results_dir: Path, scenario: str, seeds: list[int],
                   baseline: str, main_method: str = MAIN_METHOD) -> dict:
    if main_method == baseline:
        raise ValueError("The two compared methods must differ")
    pairs = [(read_record(results_dir, scenario, seed, main_method),
              read_record(results_dir, scenario, seed, baseline)) for seed in seeds]
    for candidate, reference in pairs:
        if any(candidate.get(key) != reference.get(key) for key in MATCH_FIELDS):
            raise ValueError(f"Unpaired {main_method}/{baseline} run: "
                             f"{scenario}, seed {candidate['seed']}")
    metrics = {}
    for key, direction in METRICS.items():
        values = [(candidate.get(key), reference.get(key))
                  for candidate, reference in pairs]
        if any(a is None or b is None or b <= 0 for a, b in values):
            raise ValueError(f"Missing or invalid paired metric: {key}")
        gains = [100 * (a / b - 1 if direction == "higher" else 1 - a / b)
                 for a, b in values]
        metrics[key] = {
            "main_method_mean": mean(a for a, _ in values),
            "baseline_mean": mean(b for _, b in values),
            "paired_improvement_percent_mean": mean(gains),
            "paired_improvement_percent_sample_sd": (stdev(gains)
                                                     if len(gains) > 1 else None),
            "paired_improvement_percent_range": [min(gains), max(gains)],
            "paired_improvement_percent_by_seed": dict(zip(seeds, gains)),
        }
    cohorts = [common_cohort(candidate, reference)
               for candidate, reference in pairs]
    populations = [{
        "seed": candidate["seed"],
        "arrivals": candidate["arrivals"],
        "main_first_token_samples": candidate["first_tokens_in_window"],
        "baseline_first_token_samples": reference["first_tokens_in_window"],
        "main_tpot_samples": candidate["queries_with_tpot_samples"],
        "baseline_tpot_samples": reference["queries_with_tpot_samples"],
        "main_completion_fraction": candidate["completion_fraction"],
        "baseline_completion_fraction": reference["completion_fraction"],
        "main_backlog_at_end": candidate["backlog_at_window_end"],
        "baseline_backlog_at_end": reference["backlog_at_window_end"],
    } for candidate, reference in pairs]
    return {"scenario": scenario, "main_method": main_method,
            "baseline": baseline, "seeds": seeds,
            "metrics": metrics, "measurement_population_by_seed": populations,
            "common_cohort_by_seed": cohorts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--scenarios", nargs="+", choices=("single", "multi"),
                        default=["single", "multi"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--main-method", choices=sorted(METHODS),
                        default=MAIN_METHOD)
    parser.add_argument("--baselines", nargs="+",
                        choices=sorted(METHODS),
                        default=[name for name, spec in METHODS.items()
                                 if spec.role == "baseline"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = [paired_summary(args.results_dir, scenario, args.seeds, baseline,
                             args.main_method)
              for scenario in args.scenarios for baseline in args.baselines]
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()

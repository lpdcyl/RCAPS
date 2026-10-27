"""Paired seed-level uncertainty for historical and new RCAPS comparisons.

The inference unit is a request-generation seed, not an individual request or
token. Confidence intervals describe variation over these simulator seeds only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from scipy.stats import binomtest, t

from .registry import MAIN_METHOD
from .run import DEFAULT_RESULTS, ROOT, output_file


METRICS = {
    "output_throughput_tokens_per_s": "higher",
    "ttft_p95_s": "lower",
    "tpot_p95_s": "lower",
}
MATCH_FIELDS = ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                "warmup_s", "trace_sha256", "evaluation_protocol",
                "python_version", "numpy_version", "arrivals")


def record_path(source: str, directory: Path, scenario: str, seed: int,
                method: str) -> Path:
    if source == "historical":
        name = "paper_integrated" if method == "rcaps" else "paper_helix"
        return directory / f"seed{seed}" / scenario / f"{name}.json"
    return output_file(directory, scenario, seed, method)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm correction across the six predeclared scenario-metric cells."""
    adjusted = [0.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)),
                                    key=lambda item: p_values[item])):
        previous = max(previous, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = previous
    return adjusted


def summarize(source: str, directory: Path, seeds: list[int]) -> dict:
    if len(seeds) != len(set(seeds)) or len(seeds) < 2:
        raise ValueError("Provide at least two distinct seeds")
    main_method = "rcaps" if source == "historical" else MAIN_METHOD
    cells = []
    for scenario in ("single", "multi"):
        paired = []
        for seed in seeds:
            main_path = record_path(source, directory, scenario, seed, main_method)
            base_path = record_path(source, directory, scenario, seed, "helix")
            main, base = read(main_path), read(base_path)
            if any(main.get(key) != base.get(key) for key in MATCH_FIELDS):
                raise ValueError(f"Protocol or trace mismatch: {scenario} seed {seed}")
            if source == "historical" and main.get("gurobi_version") != base.get("gurobi_version"):
                raise ValueError(f"Gurobi version mismatch: {scenario} seed {seed}")
            if main["seed"] != seed or main["scenario"] != scenario:
                raise ValueError(f"Unexpected record: {main_path}")
            paired.append((seed, main, base, main_path, base_path))
        for metric, direction in METRICS.items():
            effects = []
            raw = []
            for seed, main, base, main_path, base_path in paired:
                a, b = main.get(metric), base.get(metric)
                if a is None or b is None or b <= 0:
                    raise ValueError(f"Missing metric {metric}: {scenario} seed {seed}")
                effect = 100 * (a / b - 1 if direction == "higher" else 1 - a / b)
                effects.append(effect)
                raw.append({
                    "seed": seed, main_method: a, "helix": b,
                    "improvement_percent": effect,
                    f"first_tokens_{main_method}": main["first_tokens_in_window"],
                    "first_tokens_helix": base["first_tokens_in_window"],
                    f"tpot_samples_{main_method}": main["queries_with_tpot_samples"],
                    "tpot_samples_helix": base["queries_with_tpot_samples"],
                    f"completion_fraction_{main_method}": main["completion_fraction"],
                    "completion_fraction_helix": base["completion_fraction"],
                    "main_record": display_path(main_path),
                    "base_record": display_path(base_path),
                    "main_sha256": hashlib.sha256(main_path.read_bytes()).hexdigest(),
                    "base_sha256": hashlib.sha256(base_path.read_bytes()).hexdigest(),
                })
            n = len(effects)
            average, sd = mean(effects), stdev(effects)
            radius = t.ppf(0.975, n - 1) * sd / n**0.5
            positive = sum(effect > 0 for effect in effects)
            n_nonzero = sum(effect != 0 for effect in effects)
            cells.append({
                "scenario": scenario, "metric": metric, "n_seeds": n,
                "mean_improvement_percent": average,
                "sample_sd_percent": sd,
                "t95_ci_percent": [average - radius, average + radius],
                "positive_seeds": positive,
                "exact_one_sided_sign_p": binomtest(positive, n_nonzero, 0.5,
                                                    alternative="greater").pvalue
                if n_nonzero else 1.0,
                "paired_records": raw,
            })
    adjusted = holm_adjust([cell["exact_one_sided_sign_p"] for cell in cells])
    for cell, value in zip(cells, adjusted):
        cell["holm_adjusted_sign_p"] = value
    return {
        "source": source, "main_method": main_method,
        "baseline": "helix", "seeds": seeds,
        "inference_unit": "request-generation seed",
        "scope": "fixed-layout Helix event simulation; no hardware uncertainty",
        "tests": "six predeclared scenario-metric cells; one-sided exact sign test with Holm correction",
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("historical", "benchmark"),
                        default="benchmark")
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    directory = args.results_dir or (ROOT / "experiments" / "multiseed" / "runs"
                                      if args.source == "historical" else DEFAULT_RESULTS)
    report = summarize(args.source, directory.resolve(), args.seeds)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    for cell in report["cells"]:
        lo, hi = cell["t95_ci_percent"]
        print(f"{cell['scenario']:6} {cell['metric']:32} "
              f"{cell['mean_improvement_percent']:+.2f}% "
              f"CI [{lo:+.2f}, {hi:+.2f}] "
              f"sign {cell['positive_seeds']}/{cell['n_seeds']} "
              f"Holm p={cell['holm_adjusted_sign_p']:.4f}")


if __name__ == "__main__":
    main()

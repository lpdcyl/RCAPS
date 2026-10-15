"""Audit paired identities and report the V2 placement/routing interaction."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def path_for(scenario: str, seed: int, cell: str) -> Path:
    if cell == "A":
        paths = list((HERE / "runs/1800s").rglob(
            f"{scenario}/seed{seed}/fixed_static.json"))
        if len(paths) != 1:
            raise ValueError(f"Expected one A result, got {paths}")
        return paths[0]
    if cell == "C":
        return (ROOT / "experiments/v2_core_ablations/runs" / scenario /
                f"seed{seed}/rcaps_v2_static_dag.json")
    name = "rcaps_v2_fixed_structure.json" if cell == "B" else "rcaps_v2.json"
    return ROOT / "experiments/v2_method_ablation/runs" / scenario / f"seed{seed}" / name


def report(scenario: str) -> dict:
    rows = []
    for seed in range(3):
        paths = {cell: path_for(scenario, seed, cell) for cell in "ABCD"}
        records = {cell: json.loads(path.read_text(encoding="utf-8"))
                   for cell, path in paths.items()}
        if len({record["trace_sha256"] for record in records.values()}) != 1:
            raise ValueError(f"Trace mismatch at seed {seed}")
        for x, y in (("A", "B"), ("C", "D")):
            for key in ("solution_sha256", "sim_cluster_sha256"):
                if records[x][key] != records[y][key]:
                    raise ValueError(f"Placement mismatch at seed {seed}: {x}/{y} {key}")
        for record in records.values():
            if (record["duration_s"] != 1800 or record["warmup_s"] != 0 or
                    record["seed"] != seed or
                    record["offered_tokens_per_s"] !=
                    (700.0 if scenario == "single" else 320.0)):
                raise ValueError(f"Protocol mismatch at seed {seed}")
        rows.append({"seed": seed, "paths": {k: str(v.relative_to(ROOT))
                                              for k, v in paths.items()},
                     "trace_sha256": records["A"]["trace_sha256"],
                     "metrics": {cell: {key: records[cell][key] for key in METRICS}
                                 for cell in "ABCD"}})
    aggregate = {}
    for cell in "ABCD":
        aggregate[cell] = {key: {"mean": mean(row["metrics"][cell][key]
                                              for row in rows),
                                 "sample_sd": stdev(row["metrics"][cell][key]
                                                    for row in rows)}
                           for key in METRICS}
    effects = {}
    for key in METRICS:
        fixed = [row["metrics"]["B"][key] - row["metrics"]["A"][key]
                 for row in rows]
        adaptive = [row["metrics"]["D"][key] - row["metrics"]["C"][key]
                    for row in rows]
        interaction = [y - x for x, y in zip(fixed, adaptive)]
        effects[key] = {label: {"mean": mean(values), "sample_sd": stdev(values)}
                        for label, values in (("fixed_dynamic_minus_static", fixed),
                                              ("adaptive_dynamic_minus_static", adaptive),
                                              ("interaction", interaction))}
    return {"scenario": scenario, "cells": {
        "A": "fixed structure + StaticCostDagScheduler",
        "B": "fixed structure + QueueAwareDagScheduler",
        "C": "adaptive structure + StaticCostDagScheduler",
        "D": "adaptive structure + QueueAwareDagScheduler"},
        "protocol": "1800 s, zero warmup, seeds 0/1/2, same trace within each seed",
        "rows": rows, "aggregate": aggregate, "effects": effects}


if __name__ == "__main__":
    output = report("multi")
    path = HERE / "summary_multi.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(path)

"""Run exactly one held-out window; safe to parallelize across unique cells."""

from __future__ import annotations

import argparse
import json

from rcaps.v3.placement import validate as validate_layout

from .joint import (CASES, HERE, ROOT, VALIDATION_SECONDS, case_inputs,
                    read, result_path, reused_formal, run_cell)
from .joint_capacity import BASE, run_guided


def run(case: str, arm: str, seed: int, mode: str):
    if arm == "capacity_joint":
        chosen = read(BASE / "plans" / f"{case}_selected.json")["winner"]
        candidate = next(row for row in read(BASE / "plans" /
                                             f"{case}.json")["capacity_ranked"]
                         if row["layout"] == chosen)
        row, path = run_guided(case, candidate, seed, VALIDATION_SECONDS,
                               mode, CASES[case][1])
    else:
        released = next(row for row in read(HERE / "plans" / f"{case}.json")["layouts"]
                        if row["label"] == "released_v3")
        model, _, _ = case_inputs(case)
        state = read(ROOT / released["layout"] / "placement.json")["state"]
        edges = frozenset(validate_layout(model, state)["dag"].edges)
        reused = (reused_formal(case, released, "full", seed, edges)
                  if mode == "uniform" else None)
        if reused is None:
            row = run_cell(case, released, "full", seed,
                           VALIDATION_SECONDS, edges, mode)
            path = result_path(case, released, "full", seed,
                               VALIDATION_SECONDS, mode, edges)
        else:
            row, path = reused
    if row["status"] != "completed":
        raise RuntimeError(f"Window failed: {path}: {row.get('error')}")
    return {"case": case, "arm": arm, "seed": seed, "mode": mode,
            "path": str(path), "status": row["status"],
            "trace_sha256": row["trace_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--arm", choices=("capacity_joint", "released_v3"), required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--mode", choices=("uniform", "burst"), required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.arm, args.seed, args.mode),
                     ensure_ascii=False))

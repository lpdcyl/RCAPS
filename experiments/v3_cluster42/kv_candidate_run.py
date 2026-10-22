"""Run capacity-admitted candidate layouts in a fixed simulation window."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import traceback
import time
from pathlib import Path

from experiments.v3_cluster42.run import BASE, HERE, PHYSICAL, PROFILE, digest

ROOT = HERE / "kv_candidate"


def run_helix(seed: int, duration: int, output: Path):
    from benchmarks.fixed_window import run
    from rcaps.v3.topology import TopologyModel
    if output.exists():
        return json.loads(output.read_text(encoding="utf-8"))
    layout = BASE / "layout_llama70b/ilp"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = run("single", "helix", 2150.0, duration, 0, seed,
                     layout / "ilp_sol.ini", layout / "simulator_cluster.ini",
                     profile_resources=True, compact=True, record_query_samples=True,
                     physical_cluster=PHYSICAL, machine_profile=PROFILE,
                     machine_counts=TopologyModel(PHYSICAL).machine_counts)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def run_one(name: str, seed: int, duration: int, output: Path, mode: str = "full"):
    from benchmarks.fixed_window import run
    from experiments.v3_cluster42.kv_admission import (KVAdmittedV3, KVAdmittedGated,
                                                       install_completion_wakeup)
    from experiments.v3_pathspace_ablation.run import canonical_edges
    from rcaps.v3.placement import validate
    from rcaps.v3.topology import TopologyModel

    if output.exists():
        return json.loads(output.read_text(encoding="utf-8"))
    layout = ROOT / name
    counters = {}
    started = time.perf_counter()
    state = json.loads((layout / "placement.json").read_text())["state"]
    allowed = None
    if mode == "gated":
        model = TopologyModel(PHYSICAL)
        allowed = canonical_edges(state, validate(model, state)["dag"])
        allowed = frozenset((a if isinstance(a, str) else a + 2,
                             b if isinstance(b, str) else b + 2)
                            for a, b in allowed)

    def factory(simulator):
        scheduler = (KVAdmittedGated(simulator, allowed_edges=allowed)
                     if mode == "gated" else KVAdmittedV3(simulator))
        install_completion_wakeup(simulator, scheduler)
        counters["scheduler"] = scheduler
        return scheduler

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            result = run(
                "single", "queue_dag", 2150.0, duration, 0, seed,
                layout / "solution.ini", layout / "simulator_cluster.ini",
                profile_resources=False, compact=True, record_query_samples=False,
                physical_cluster=PHYSICAL, machine_profile=PROFILE,
                machine_counts=TopologyModel(PHYSICAL).machine_counts,
                scheduler_factory=factory)
        except Exception as error:
            failure = {"candidate": name, "seed": seed, "duration_s": duration,
                       "error": repr(error), "traceback": traceback.format_exc()}
            output.with_suffix(".failure.json").write_text(
                json.dumps(failure, indent=2) + "\n", encoding="utf-8")
            raise
    scheduler = counters["scheduler"]
    result.update({"candidate": name, "mode": mode,
                   "kv_admission": scheduler.kv_admission,
                   "wall_time_s": time.perf_counter() - started,
                   "peak_reserved_kv_units": scheduler.peak_reserved,
                   "active_gpus": json.loads((layout / "placement.json").read_text())["active_gpus"],
                   "scheduler_sha256": digest(HERE / "kv_admission.py"),
                   "layout_sha256": digest(layout / "placement.json"),
                   "pythonhashseed": os.environ.get("PYTHONHASHSEED")})
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"), required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--mode", choices=("full", "gated"), default="full")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("PYTHONHASHSEED=0 required")
    names = [row["name"] for row in json.loads((ROOT / "shortlist.json").read_text())]
    if args.candidate:
        if args.candidate not in names and args.candidate != "helix":
            raise SystemExit(f"Unknown candidate: {args.candidate}")
        names = [args.candidate]
    seeds, duration = (([100], 180) if args.phase == "smoke" else ([0, 1, 2], 1800))
    if args.seed is not None:
        seeds = [args.seed]
    for name in names:
        for seed in seeds:
            suffix = "_gated" if args.mode == "gated" and name != "helix" else ""
            output = ROOT / "runs" / args.phase / f"{name}{suffix}_seed{seed}.json"
            try:
                row = (run_helix(seed, duration, output) if name == "helix"
                       else run_one(name, seed, duration, output, args.mode))
                print(json.dumps({k: row.get(k) for k in ("candidate", "seed",
                    "active_gpus", "output_throughput_tokens_per_s",
                    "ttft_p95_s", "tpot_p95_s", "backlog_at_window_end",
                    "trace_sha256", "kv_admission")}), flush=True)
            except Exception as error:
                print(f"FAILED {name} seed={seed}: {error!r}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()

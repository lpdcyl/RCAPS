"""Reproduce six gated-pathspace formal cells with current frozen inputs."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

import numpy as np

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_cycle_pricing.run import physical_input, scheduler_factory
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.topology import TopologyModel

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
AUDIT = HERE / "audit.json"
SOURCES = ["work3_sparse_replication/protocol.json",
           "work3_sparse_replication/run.py",
           "work3_sparse_replication/report.py",
           "experiments/v3_gated_pathspace/protocol.json",
           "experiments/v3_gated_pathspace/scheduler.py",
           "experiments/v3_cycle_pricing/run.py",
           "experiments/v3_pathspace_ablation/run.py",
           "benchmarks/fixed_window.py", "benchmarks/accumulator.py",
           "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
           "rcaps/v3/online_scheduler.py", "rcaps/v3/scheduler.py"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def identity():
    files = list(SOURCES)
    for case in PROTOCOL["loads"]:
        physical, topology = physical_input(case)
        files += [physical.relative_to(ROOT).as_posix(),
                  f"rcaps/v3_layouts/{topology}/solution.ini",
                  f"rcaps/v3_layouts/{topology}/simulator_cluster.ini"]
        for seed in PROTOCOL["seeds"]:
            files.append(f"benchmarks/runs/{topology}/seed{seed}/rcaps_v3.json")
    return {name: digest(ROOT / name) for name in sorted(files)}


def freeze():
    data = {"protocol": PROTOCOL, "sources_sha256": identity(),
            "environment": {"python": sys.version.split()[0],
                            "numpy": np.__version__,
                            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                            "MPLBACKEND": os.environ.get("MPLBACKEND")}}
    if AUDIT.exists():
        if json.loads(AUDIT.read_text(encoding="utf-8")) != data:
            raise ValueError("Source or environment changed after registration")
    else:
        write(AUDIT, data)
    return data


def run_one(case, seed):
    freeze()
    output = HERE / "runs" / case / f"gated_seed{seed}.json"
    if output.exists():
        result = json.loads(output.read_text(encoding="utf-8"))
        if result["audit_sha256"] != digest(AUDIT):
            raise ValueError("Existing window identity mismatch")
        return str(output)
    physical, topology = physical_input(case)
    deployment = ROOT / "rcaps" / "v3_layouts" / topology
    canonical = scheduler_factory(case, "canonical").keywords["allowed_edges"]
    holder = {}

    def factory(sim):
        holder["scheduler"] = SlowLinkGatedScheduler(sim, allowed_edges=canonical)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            result = fixed_window_run(
                topology, "queue_dag", PROTOCOL["loads"][case],
                PROTOCOL["duration_s"], 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory)
            result.update({"case": case, "cell": "gated", "audit_sha256": digest(AUDIT),
                           "allowed_edges": len(holder["scheduler"].allowed_edges),
                           "route_hops": {str(uid): list(value) for uid, value in
                                          holder["scheduler"].route_records.items()}})
            write(output, result)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "seed": seed, "error": repr(error),
                   "traceback": traceback.format_exc()})
            raise
    return str(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
        raise SystemExit("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg")
    freeze()
    if args.phase == "freeze":
        print(AUDIT)
    elif args.phase == "report":
        from work3_sparse_replication.report import report
        print(report())
    else:
        jobs = [(case, seed) for case in PROTOCOL["loads"]
                for seed in PROTOCOL["seeds"]]
        failed = []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_one, *job): job for job in jobs}
            for future in as_completed(futures):
                try:
                    print("done", future.result(), flush=True)
                except Exception as error:
                    print("failed", futures[future], repr(error), flush=True)
                    failed.append(futures[future])
        if failed:
            raise RuntimeError(f"{len(failed)} replication windows failed")


if __name__ == "__main__":
    main()

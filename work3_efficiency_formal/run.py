"""Held-out long-window GPU work test of the unchanged sparse gate."""

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
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.topology import TopologyModel
from work3_transfer.run import allowed_edges

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
AUDIT = HERE / "audit.json"
SOURCES = ["work3_efficiency_formal/protocol.json",
           "work3_efficiency_formal/run.py",
           "work3_efficiency_formal/report.py",
           "work3_transfer/run.py",
           "experiments/v3_gated_pathspace/scheduler.py",
           "experiments/v3_pathspace_ablation/run.py",
           "experiments/m2_multistage_candidate/placement.py",
           "benchmarks/fixed_window.py", "benchmarks/accumulator.py",
           "benchmarks/resource_profile.py",
           "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
           "rcaps/v3/online_scheduler.py", "rcaps/v3/scheduler.py"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def identity():
    names = list(SOURCES)
    for case in PROTOCOL["cases"]:
        names += [f"rcaps/v3/pools/{case}/physical.ini",
                  f"rcaps/v3_layouts/{case}/placement.json",
                  f"rcaps/v3_layouts/{case}/solution.ini",
                  f"rcaps/v3_layouts/{case}/simulator_cluster.ini"]
        for seed in PROTOCOL["seeds"]:
            names.append(f"experiments/m2_multistage_candidate/runs/formal/{case}/seed{seed}/single_a100.json")
    return {name: digest(ROOT / name) for name in sorted(names)}


def freeze():
    data = {"protocol": PROTOCOL, "sources_sha256": identity(),
            "environment": {"python": sys.version.split()[0],
                            "numpy": np.__version__,
                            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                            "MPLBACKEND": os.environ.get("MPLBACKEND")}}
    if AUDIT.exists():
        if json.loads(AUDIT.read_text(encoding="utf-8")) != data:
            raise ValueError("Formal source or environment drift")
    else:
        write(AUDIT, data)
    return data


def run_one(case, seed):
    freeze()
    output = HERE / "runs" / case / f"gated_seed{seed}.json"
    if output.exists():
        row = json.loads(output.read_text(encoding="utf-8"))
        if row["audit_sha256"] != digest(AUDIT):
            raise ValueError("Existing result identity differs")
        return str(output)
    physical = ROOT / "rcaps" / "v3" / "pools" / case / "physical.ini"
    layout = ROOT / "rcaps" / "v3_layouts" / case
    machine_counts = TopologyModel(physical).machine_counts
    canonical = allowed_edges(case)
    holder = {}

    def factory(sim):
        holder["scheduler"] = SlowLinkGatedScheduler(sim, allowed_edges=canonical)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window_run(
                "single", "queue_dag", PROTOCOL["offered_tokens_per_s"][case],
                PROTOCOL["duration_s"], 0, seed,
                layout / "solution.ini", layout / "simulator_cluster.ini",
                compact=True, record_query_samples=True, profile_resources=True,
                physical_cluster=physical, machine_counts=machine_counts,
                scheduler_factory=factory)
            row.update({"case": case, "cell": "gated",
                        "audit_sha256": digest(AUDIT),
                        "allowed_edges": len(holder["scheduler"].allowed_edges)})
            write(output, row)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "seed": seed,
                   "error": repr(error), "traceback": traceback.format_exc()})
            raise
    return str(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
        raise SystemExit("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg")
    freeze()
    if args.phase == "freeze":
        print(AUDIT)
    elif args.phase == "report":
        from work3_efficiency_formal.report import report
        print(report())
    else:
        jobs = [(case, seed) for case in PROTOCOL["cases"]
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
            raise RuntimeError(f"{len(failed)} formal windows failed")


if __name__ == "__main__":
    main()

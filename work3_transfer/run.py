"""Paired untuned transfer of V3 and the old sparse-edge gate to C2/C3."""

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
from experiments.m2_multistage_candidate.placement import validate
from experiments.v3_pathspace_ablation.run import canonical_edges
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
AUDIT = HERE / "audit.json"
SOURCES = ["work3_transfer/protocol.json", "work3_transfer/run.py",
           "work3_transfer/report.py",
           "experiments/v3_gated_pathspace/scheduler.py",
           "experiments/v3_pathspace_ablation/run.py",
           "experiments/m2_multistage_candidate/placement.py",
           "benchmarks/fixed_window.py", "benchmarks/accumulator.py",
           "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
           "rcaps/v3/online_scheduler.py", "rcaps/v3/scheduler.py"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def frozen_identity():
    names = list(SOURCES)
    for case in PROTOCOL["cases"]:
        names += [f"rcaps/v3/pools/{case}/physical.ini",
                  f"rcaps/v3_layouts/{case}/placement.json",
                  f"rcaps/v3_layouts/{case}/solution.ini",
                  f"rcaps/v3_layouts/{case}/simulator_cluster.ini"]
    return {name: digest(ROOT / name) for name in sorted(names)}


def freeze():
    data = {"protocol": PROTOCOL, "sources_sha256": frozen_identity(),
            "environment": {"python": sys.version.split()[0],
                            "numpy": np.__version__,
                            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                            "MPLBACKEND": os.environ.get("MPLBACKEND")}}
    if AUDIT.exists():
        if json.loads(AUDIT.read_text(encoding="utf-8")) != data:
            raise ValueError("Source or environment drift")
    else:
        write(AUDIT, data)
    return data


def allowed_edges(case):
    physical = ROOT / "rcaps" / "v3" / "pools" / case / "physical.ini"
    layout = ROOT / "rcaps" / "v3_layouts" / case
    state = json.loads((layout / "placement.json").read_text(encoding="utf-8"))["state"]
    checked = validate(TopologyModel(physical), state)
    return frozenset((a if isinstance(a, str) else a + 2,
                      b if isinstance(b, str) else b + 2)
                     for a, b in canonical_edges(state, checked["dag"]))


def run_one(case, cell, seed):
    freeze()
    output = HERE / "runs" / case / f"{cell}_seed{seed}.json"
    if output.exists():
        data = json.loads(output.read_text(encoding="utf-8"))
        if data["audit_sha256"] != digest(AUDIT):
            raise ValueError("Existing result identity differs")
        return str(output)
    physical = ROOT / "rcaps" / "v3" / "pools" / case / "physical.ini"
    layout = ROOT / "rcaps" / "v3_layouts" / case
    machine_counts = TopologyModel(physical).machine_counts
    if cell == "v3":
        factory = GraphModeledQueueAwareDagScheduler
    elif cell == "gated":
        factory = partial(SlowLinkGatedScheduler, allowed_edges=allowed_edges(case))
    else:
        raise ValueError(cell)
    holder = {}

    def create(sim):
        holder["scheduler"] = factory(sim)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            data = fixed_window_run(
                "single", "queue_dag", PROTOCOL["offered_tokens_per_s"][case],
                PROTOCOL["duration_s"], 0, seed,
                layout / "solution.ini", layout / "simulator_cluster.ini",
                compact=True, record_query_samples=True, profile_resources=True,
                physical_cluster=physical, machine_counts=machine_counts,
                scheduler_factory=create)
            data.update({"case": case, "cell": cell,
                         "audit_sha256": digest(AUDIT),
                         "allowed_edges": len(getattr(holder["scheduler"],
                                                      "allowed_edges", []) or [])})
            write(output, data)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "cell": cell, "seed": seed,
                   "error": repr(error), "traceback": traceback.format_exc()})
            raise
    return str(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "development", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
        raise SystemExit("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg")
    freeze()
    if args.phase == "freeze":
        print(AUDIT)
    elif args.phase == "report":
        from work3_transfer.report import report
        print(report())
    else:
        jobs = [(case, cell, seed) for case in PROTOCOL["cases"]
                for seed in PROTOCOL["seeds"] for cell in PROTOCOL["methods"]]
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
            raise RuntimeError(f"{len(failed)} transfer windows failed")


if __name__ == "__main__":
    main()

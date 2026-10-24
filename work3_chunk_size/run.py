"""Fresh-seed paired screen for 2 and 4 MiB slow-link chunk sizes."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_cycle_pricing.run import physical_input, scheduler_factory
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.topology import TopologyModel
from work3_selective_chunk.chunking import SlowLinkPromptTransferChunkHook

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
AUDIT = HERE / "audit.json"
SOURCES = (
    "work3_chunk_size/protocol.json", "work3_chunk_size/run.py", "work3_chunk_size/report.py",
    "work3_selective_chunk/chunking.py", "experiments/v3_phase_link_diagnosis/chunking.py",
    "experiments/v3_gated_pathspace/scheduler.py", "experiments/v3_cycle_pricing/run.py",
    "experiments/v3_pathspace_ablation/run.py", "benchmarks/fixed_window.py",
    "benchmarks/accumulator.py", "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
    "rcaps/v3/online_scheduler.py", "rcaps/v3/scheduler.py",
    "rcaps/v3_layouts/multi/solution.ini", "rcaps/v3_layouts/multi/simulator_cluster.ini",
    "work3_selective_chunk/formal/runs/C1_multi/gate_seed201.json",
    "work3_selective_chunk/formal/runs/C1_multi/chunk_slow_seed201.json",
    "work3_selective_chunk/formal/runs/C1_multi/gate_seed203.json",
    "work3_selective_chunk/formal/runs/C1_multi/chunk_slow_seed203.json",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def freeze() -> dict:
    physical, topology = physical_input(PROTOCOL["case"])
    if topology != "multi":
        raise ValueError("Unexpected topology")
    names = list(SOURCES) + [physical.relative_to(ROOT).as_posix()]
    data = {"protocol": PROTOCOL,
            "sources_sha256": {name: digest(ROOT / name) for name in sorted(names)},
            "environment": {"python": sys.version.split()[0], "numpy": np.__version__,
                            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                            "MPLBACKEND": os.environ.get("MPLBACKEND")}}
    if AUDIT.exists():
        if json.loads(AUDIT.read_text(encoding="utf-8")) != data:
            raise ValueError("Registered source/protocol/environment changed")
    else:
        write(AUDIT, data)
    return data


def run_one(seed: int, cell: str) -> str:
    freeze()
    output = HERE / "runs" / "development" / f"{cell}_seed{seed}.json"
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        if old["audit_sha256"] != digest(AUDIT):
            raise ValueError("Existing result identity differs")
        return str(output)
    physical, topology = physical_input(PROTOCOL["case"])
    deployment = ROOT / "rcaps" / "v3_layouts" / topology
    canonical = scheduler_factory(PROTOCOL["case"], "canonical").keywords["allowed_edges"]
    size = PROTOCOL["cells"][cell]
    hook = None if size is None else SlowLinkPromptTransferChunkHook(
        size, PROTOCOL["slow_link_threshold_Bps"])
    holder = {}

    def factory(simulator):
        holder["scheduler"] = SlowLinkGatedScheduler(simulator, allowed_edges=canonical)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                topology, "queue_dag", PROTOCOL["offered_tokens_per_s"],
                PROTOCOL["duration_s"], PROTOCOL["warmup_s"], seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory, phase_link_probe=hook)
            row.update({"case": PROTOCOL["case"], "cell": cell,
                        "audit_sha256": digest(AUDIT),
                        "allowed_edges": len(holder["scheduler"].allowed_edges),
                        "chunk_bytes": size})
            write(output, row)
        except Exception as error:
            traceback.print_exc(file=log)
            write(output.with_suffix(".failure.json"),
                  {"seed": seed, "cell": cell, "error": repr(error),
                   "traceback": traceback.format_exc()})
            raise
    return str(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "development", "report"), required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
        raise SystemExit("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg")
    freeze()
    if args.phase == "freeze":
        print(AUDIT)
    elif args.phase == "report":
        from work3_chunk_size.report import report
        print(report())
    else:
        jobs = [(seed, cell) for seed in PROTOCOL["development_seeds"]
                for cell in PROTOCOL["cells"]]
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
            raise RuntimeError(f"{len(failed)} development windows failed")


if __name__ == "__main__":
    main()

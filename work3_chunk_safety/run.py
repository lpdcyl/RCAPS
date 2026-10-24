"""Paired 60-second no-op transfer check on C1 single, C2 and C3."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_cycle_pricing.run import physical_input, scheduler_factory
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.topology import TopologyModel
from work3_selective_chunk.chunking import SlowLinkPromptTransferChunkHook
from work3_transfer.run import allowed_edges as other_canonical

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
AUDIT = HERE / "audit.json"
SOURCES = (
    "work3_chunk_safety/protocol.json", "work3_chunk_safety/run.py",
    "work3_chunk_safety/report.py", "work3_selective_chunk/chunking.py",
    "experiments/v3_phase_link_diagnosis/chunking.py",
    "experiments/v3_gated_pathspace/scheduler.py", "experiments/v3_cycle_pricing/run.py",
    "experiments/v3_pathspace_ablation/run.py", "work3_transfer/run.py",
    "benchmarks/fixed_window.py", "benchmarks/accumulator.py",
    "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
    "rcaps/v3/online_scheduler.py", "rcaps/v3/scheduler.py",
    "work3_chunk_size/formal/analysis.json",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    part.replace(path)


def config(case: str):
    if case == "C1_single":
        physical, topology = physical_input(case)
        canonical = scheduler_factory(case, "canonical").keywords["allowed_edges"]
    else:
        physical = ROOT / "rcaps" / "v3" / "pools" / case / "physical.ini"
        topology = case
        canonical = other_canonical(case)
    deployment = ROOT / "rcaps" / "v3_layouts" / topology
    scenario = "single"
    return physical, deployment, scenario, canonical


def freeze() -> dict:
    names = list(SOURCES)
    for case in PROTOCOL["cases"]:
        physical, deployment, _, _ = config(case)
        names.extend((physical.relative_to(ROOT).as_posix(),
                      (deployment / "solution.ini").relative_to(ROOT).as_posix(),
                      (deployment / "simulator_cluster.ini").relative_to(ROOT).as_posix()))
    data = {"protocol": PROTOCOL,
            "sources_sha256": {name: digest(ROOT / name) for name in sorted(set(names))},
            "environment": {"python": sys.version.split()[0], "numpy": np.__version__,
                            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                            "MPLBACKEND": os.environ.get("MPLBACKEND")}}
    if AUDIT.exists():
        if json.loads(AUDIT.read_text(encoding="utf-8")) != data:
            raise ValueError("Frozen safety protocol/source/environment changed")
    else:
        write(AUDIT, data)
    return data


def run_one(case: str, cell: str) -> str:
    freeze()
    output = HERE / "runs" / case / f"{cell}_seed{PROTOCOL['seed']}.json"
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        if old["audit_sha256"] != digest(AUDIT):
            raise ValueError("Existing safety result identity differs")
        return str(output)
    physical, deployment, scenario, canonical = config(case)
    holder = {}

    def factory(simulator):
        holder["scheduler"] = SlowLinkGatedScheduler(simulator, allowed_edges=canonical)
        return holder["scheduler"]

    hook = None if cell == "gate" else SlowLinkPromptTransferChunkHook(
        PROTOCOL["chunk_bytes"], PROTOCOL["slow_link_threshold_Bps"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", PROTOCOL["offered_tokens_per_s"][case],
                PROTOCOL["duration_s"], PROTOCOL["warmup_s"], PROTOCOL["seed"],
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory, phase_link_probe=hook)
            row.update({"case": case, "cell": cell, "audit_sha256": digest(AUDIT),
                        "allowed_edges": len(holder["scheduler"].allowed_edges)})
            write(output, row)
        except Exception as error:
            traceback.print_exc(file=log)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "cell": cell, "error": repr(error),
                   "traceback": traceback.format_exc()})
            raise
    return str(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "run", "report"), required=True)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
        raise SystemExit("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg")
    freeze()
    if args.phase == "freeze":
        print(AUDIT)
    elif args.phase == "report":
        from work3_chunk_safety.report import report
        print(report())
    else:
        for case in PROTOCOL["cases"]:
            for cell in ("gate", "chunk_4MiB"):
                print("done", run_one(case, cell), flush=True)


if __name__ == "__main__":
    main()

"""Frozen-input, paired simulation for admission-time link pricing."""

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

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_cycle_pricing.run import physical_input, scheduler_factory
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.topology import TopologyModel
from work3_link_price.scheduler import PricedGatedScheduler


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
AUDIT = HERE / "audits" / "v1.json"
DEPENDENCIES = (
    "work3_link_price/__init__.py", "work3_link_price/protocol.json",
    "work3_link_price/scheduler.py", "work3_link_price/run.py",
    "work3_link_price/report.py",
    "experiments/v3_m3_interference/scheduler.py",
    "experiments/v3_gated_pathspace/scheduler.py",
    "experiments/v3_cycle_pricing/scheduler.py",
    "experiments/v3_cycle_pricing/run.py",
    "experiments/v3_pathspace_ablation/run.py",
    "rcaps/v3/routing.py", "rcaps/v3/queue_cost.py",
    "rcaps/v3/online_scheduler.py", "rcaps/v3/scheduler.py",
    "benchmarks/fixed_window.py", "benchmarks/accumulator.py",
    "rcaps/v3_layouts/single/solution.ini",
    "rcaps/v3_layouts/single/simulator_cluster.ini",
    "rcaps/v3_layouts/multi/solution.ini",
    "rcaps/v3_layouts/multi/simulator_cluster.ini",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def sources() -> dict:
    paths = list(DEPENDENCIES)
    for case in PROTOCOL["topologies"]:
        physical, _ = physical_input(case)
        paths.append(physical.relative_to(ROOT).as_posix())
    return {name: digest(ROOT / name) for name in sorted(paths)}


def freeze() -> dict:
    if AUDIT.exists():
        return check_frozen()
    import numpy
    data = {"protocol": PROTOCOL, "sources_sha256": sources(),
            "environment": {"python": sys.version.split()[0],
                            "numpy": numpy.__version__,
                            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                            "MPLBACKEND": os.environ.get("MPLBACKEND")}}
    write(AUDIT, data)
    return data


def check_frozen() -> dict:
    data = json.loads(AUDIT.read_text(encoding="utf-8"))
    if data["protocol"] != PROTOCOL or data["sources_sha256"] != sources():
        raise ValueError("Registered source or protocol drift; create a new revision")
    import numpy
    if data["environment"] != {"python": sys.version.split()[0],
                               "numpy": numpy.__version__,
                               "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                               "MPLBACKEND": os.environ.get("MPLBACKEND")}:
        raise ValueError("Registered execution environment drift")
    return data


def builder(case: str, method: str):
    if method == "v3":
        from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler
        return RecordedV3Scheduler
    canonical = scheduler_factory(case, "canonical").keywords["allowed_edges"]
    if method == "gated":
        return partial(SlowLinkGatedScheduler, allowed_edges=canonical)
    if method == "priced":
        return partial(PricedGatedScheduler, canonical_edges=canonical)
    if method == "priced_off":
        return partial(PricedGatedScheduler, canonical_edges=canonical,
                       externality=False)
    raise ValueError(method)


def run_one(case: str, method: str, seed: int, duration: int,
            phase: str) -> str:
    check_frozen()
    output = HERE / "runs" / "v1" / phase / case / f"{method}_seed{seed}.json"
    if output.exists():
        row = json.loads(output.read_text(encoding="utf-8"))
        if row["audit_sha256"] != digest(AUDIT) or row["trace_sha256"] is None:
            raise ValueError(f"Existing result has another identity: {output}")
        return str(output)
    physical, topology = physical_input(case)
    deployment = ROOT / "rcaps" / "v3_layouts" / topology
    holder = {}
    base_factory = builder(case, method)

    def factory(simulator):
        holder["scheduler"] = base_factory(simulator)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window_run(
                topology, "queue_dag", PROTOCOL["offered_tokens_per_s"][case],
                duration, 0, seed, deployment / "solution.ini",
                deployment / "simulator_cluster.ini", profile_resources=True,
                compact=True, record_query_samples=True, physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory)
            scheduler = holder["scheduler"]
            row.update({"case": case, "cell": method, "phase": phase,
                        "audit_sha256": digest(AUDIT),
                        "source_sha256": sources(),
                        "route_hops": {str(uid): list(value) for uid, value in
                                       getattr(scheduler, "route_records", {}).items()},
                        "link_price_count": len(getattr(scheduler, "route_prices", [])),
                        "link_price_sum": sum(getattr(scheduler, "route_prices", [])),
                        "allowed_edges": len(getattr(scheduler, "allowed_edges", []) or [])})
            write(output, row)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "cell": method, "seed": seed,
                   "error": repr(error), "traceback": traceback.format_exc()})
            raise
    return str(output)


def jobs(phase: str):
    if phase == "smoke":
        return [(case, method, PROTOCOL["smoke_seed"],
                 PROTOCOL["smoke_duration_s"], phase)
                for case in PROTOCOL["topologies"]
                for method in ("gated", "priced_off", "priced")]
    return [(case, method, seed, PROTOCOL["development_duration_s"], phase)
            for seed in PROTOCOL["development_seeds"]
            for case in PROTOCOL["topologies"]
            for method in (("gated", "priced", "v3") if case == "C1_multi"
                           else ("gated", "priced"))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "smoke", "development", "report"),
                        required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.phase == "freeze":
        if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
            raise SystemExit("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg")
        print(json.dumps(freeze()["environment"], ensure_ascii=False))
        return
    check_frozen()
    if args.phase == "report":
        from work3_link_price.report import report
        print(report())
        return
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(args.phase)}
        failed = []
        for future in as_completed(futures):
            job = futures[future]
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", job[:3], repr(error), flush=True)
                failed.append(job)
        if failed:
            raise RuntimeError(f"{len(failed)} simulation windows failed")


if __name__ == "__main__":
    main()

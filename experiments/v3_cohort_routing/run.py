"""Decode-cohort pricing: development selection, formal windows and report.

Phases:
  parity  seed 100, 60 s: cohort_tokens = 0 must reproduce frozen V3.
  dev     seed 100, 300 s: step (1 token) and lifetime (154 tokens) cohort
          prices on both topologies; selection by protocol_dev.json.
  formal  seeds 0/1/2, 1800 s: the variant named in protocol.json.
  report  paired analysis against released V3 and canonical-route windows.

Every run carries a passive decode-batch probe. Frozen code, layouts and
released runs are read only.
"""

from __future__ import annotations

import argparse
import os
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

from experiments.v3_cycle_pricing.run import (
    CASES, DEV_SEED, FORMAL_SEEDS, LOADS, ROOT, digest, physical_input, read, rel, write)
from pathlib import Path

HERE = Path(__file__).resolve().parent


def factory_for(cell: str):
    from experiments.v3_cohort_routing import scheduler as cohort
    from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler
    if cell == "v3":
        return RecordedV3Scheduler
    if cell == "zero":
        return type("ZeroCohortScheduler", (cohort.StepCohortScheduler,), {"cohort_tokens": 0.0})
    return {"step": cohort.StepCohortScheduler,
            "lifetime": cohort.LifetimeCohortScheduler}[cell]


def run_one(case: str, cell: str, seed: int, duration: int, output: Path,
            builder=None, here: Path = HERE) -> str:
    """Run one window; ``builder(case, cell)`` returns the scheduler class."""
    if output.exists():
        return rel(output)
    import contextlib
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    physical, topology = physical_input(case)
    deployment = ROOT / "rcaps/v3_layouts" / topology
    base = (builder or (lambda _case, name: factory_for(name)))(case, cell)
    holder = {}
    stats = defaultdict(lambda: [0, 0, 0])  # decode executions, decode requests, single

    def factory(simulator):
        for node in simulator.compute_nodes.values():
            original = node.start_execution

            def start_execution(requests, _original=original, _uid=node.node_uid):
                decodes = sum(r.phase == RequestPhase.Increment for r in requests)
                if decodes:
                    record = stats[_uid]
                    record[0] += 1
                    record[1] += decodes
                    record[2] += decodes == 1
                return _original(requests)

            node.start_execution = start_execution
        holder["scheduler"] = base(simulator)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window.run(
                topology, "queue_dag", LOADS[case], duration, 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "cell": cell, "seed": seed, "error": repr(error),
                   "traceback": traceback.format_exc()})
            raise
    records = getattr(holder["scheduler"], "route_records", {})
    executions = sum(s[0] for s in stats.values())
    row.update({"case": case, "cell": cell, "seed": seed, "duration_s": duration,
                "cohort_tokens": getattr(holder["scheduler"], "cohort_tokens", None),
                "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                "scheduler_sha256": digest(here / "scheduler.py"),
                "solution_sha256": digest(deployment / "solution.ini"),
                "sim_cluster_sha256": digest(deployment / "simulator_cluster.ini"),
                "physical_sha256": digest(physical),
                "route_hops": {str(uid): {"hops": h, "partial_hops": p}
                               for uid, (h, p) in records.items()},
                "decode_batches": {
                    "executions": executions,
                    "mean_batch": sum(s[1] for s in stats.values()) / max(1, executions),
                    "single_share": sum(s[2] for s in stats.values()) / max(1, executions),
                    "per_gpu": {str(uid): s for uid, s in sorted(stats.items())}}})
    write(output, row)
    return rel(output)


def jobs(phase: str) -> list:
    if phase == "parity":
        return [(case, cell, DEV_SEED, 60, HERE / "runs/parity" / case / f"{cell}.json")
                for case in CASES for cell in ("v3", "zero")]
    if phase == "dev":
        return [(case, cell, DEV_SEED, 300, HERE / "runs/dev" / case / f"{cell}_seed{DEV_SEED}.json")
                for case in CASES for cell in ("step", "lifetime")]
    cell = read(HERE / "protocol.json")["selected_variant"]
    return [(case, cell, seed, 1800, HERE / "runs/formal" / case / f"{cell}_seed{seed}.json")
            for case in CASES for seed in FORMAL_SEEDS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("parity", "dev", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "report":
        from experiments.v3_cohort_routing.report import main as report
        report()
        return
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(args.phase)}
        for future in as_completed(futures):
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", futures[future][:3], repr(error), flush=True)


if __name__ == "__main__":
    main()

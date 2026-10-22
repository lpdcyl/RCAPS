"""Paired work-three development windows and passive mechanism probes."""

from __future__ import annotations

import argparse
import contextlib
import os
import traceback
from collections import defaultdict
from functools import partial
from pathlib import Path

from experiments.v3_cycle_pricing.run import (
    ROOT, digest, physical_input, read, rel, scheduler_factory, write)
from experiments.v3_cluster42.kv_admission import install_completion_wakeup
from experiments.v3_dynamic_pathspace.scheduler import (
    KVCanonical, KVDynamic, KVFull, KVLinkDynamic, KVStatic)

HERE = Path(__file__).resolve().parent
HIGH = {"C1_single": 700.0, "C1_multi": 320.0}
CONDITIONS = {**HIGH, "C1_single_low": 350.0, "C1_single_idle": 100.0}
CELLS = ("full", "canonical", "static", "dynamic", "dynamic_no_batch")


def builder(condition: str, cell: str):
    if cell == "full":
        return KVFull
    case = "C1_single" if condition.startswith("C1_single_") else condition
    canonical = scheduler_factory(case, "canonical").keywords["allowed_edges"]
    if cell == "canonical":
        return partial(KVCanonical, allowed_edges=canonical)
    if cell == "static":
        return partial(KVStatic, allowed_edges=canonical)
    if cell == "dynamic":
        return partial(KVDynamic, allowed_edges=canonical)
    if cell == "dynamic_no_batch":
        return partial(KVDynamic, allowed_edges=canonical, protect_batches=False)
    if cell == "dynamic_link":
        return partial(KVLinkDynamic, allowed_edges=canonical)
    if cell == "dynamic_link_no_batch":
        return partial(KVLinkDynamic, allowed_edges=canonical, protect_batches=False)
    raise ValueError(cell)


def run_one(condition: str, cell: str, seed: int, duration: int, phase: str) -> str:
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    case = "C1_single" if condition.startswith("C1_single_") else condition
    physical, topology = physical_input(case)
    deployment = ROOT / "rcaps/v3_layouts" / topology
    output = HERE / "runs" / phase / condition / f"{cell}_seed{seed}.json"
    identity = {
        "condition": condition, "cell": cell, "seed": seed,
        "duration_s": duration, "offered_tokens_per_s": CONDITIONS[condition],
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "scheduler_sha256": digest(HERE / "scheduler.py"),
        "solution_sha256": digest(deployment / "solution.ini"),
        "sim_cluster_sha256": digest(deployment / "simulator_cluster.ini"),
        "physical_sha256": digest(physical),
    }
    if output.exists():
        previous = read(output)
        if all(previous.get(key) == value for key, value in identity.items()):
            return rel(output)
        raise ValueError(f"Existing window identity differs: {output}")

    holder = {}
    batches = defaultdict(lambda: [0, 0, 0])
    base = builder(condition, cell)

    def factory(simulator):
        for node in simulator.compute_nodes.values():
            original = node.start_execution

            def record(requests, _original=original, _uid=node.node_uid):
                count = sum(r.phase == RequestPhase.Increment for r in requests)
                if count:
                    batch = batches[_uid]
                    batch[0] += 1
                    batch[1] += count
                    batch[2] += count == 1
                return _original(requests)

            node.start_execution = record
        scheduler = base(simulator)
        holder["scheduler"] = scheduler
        install_completion_wakeup(simulator, scheduler)
        return scheduler

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window.run(
                topology, "queue_dag", CONDITIONS[condition], duration, 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory)
            scheduler = holder["scheduler"]
            executions = sum(item[0] for item in batches.values())
            busy = row["gpu_busy_fraction"]
            capacities = {str(uid): node.kv_cache.max_capacity
                          for uid, node in scheduler.simulator.compute_nodes.items()
                          if node.kv_cache is not None}
            peak = {str(uid): amount for uid, amount in scheduler.peak_reserved.items()}
            row.update({
                **identity, "phase": phase,
                "kv_admission": scheduler.kv_admission,
                "kv_peak_reserved": peak,
                "kv_capacity": capacities,
                "kv_peak_fraction": max(
                    (amount / capacities[uid] for uid, amount in peak.items()),
                    default=0.0),
                "gpu_seconds_per_output_token": sum(busy.values()) /
                row["output_throughput_tokens_per_s"],
                "decode_batches": {
                    "executions": executions,
                    "mean_batch": sum(item[1] for item in batches.values()) / max(1, executions),
                    "single_share": sum(item[2] for item in batches.values()) / max(1, executions),
                    "per_gpu": {str(uid): data for uid, data in sorted(batches.items())}},
                "route_hops": {str(uid): {"hops": hops, "partial_hops": partial}
                                for uid, (hops, partial) in scheduler.route_records.items()},
                "gate_counts": dict(getattr(scheduler, "gate_counts", {})),
                "gate_by_edge": {edge: dict(counts)
                                  for edge, counts in getattr(scheduler, "gate_by_edge", {}).items()},
            })
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Incomplete per-query samples")
            write(output, row)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"), {
                **identity, "error": repr(error), "traceback": traceback.format_exc()})
            raise
    return rel(output)


def jobs(phase: str):
    if phase == "dev_link":
        return [(case, cell, 100, 300, phase)
                for case in HIGH for cell in ("static", "dynamic_link",
                                              "dynamic_link_no_batch")]
    if phase == "smoke":
        return [(case, cell, 100, 60, phase)
                for case in HIGH for cell in CELLS]
    if phase == "dev":
        return [(case, cell, 100, 300, phase)
                for case in HIGH for cell in CELLS] + [
                ("C1_single_low", cell, 100, 300, phase)
                for cell in ("static", "dynamic")]
    if phase == "formal":
        if not (HERE / "protocol.json").exists():
            raise ValueError("Freeze protocol.json before formal runs")
        return [(case, cell, seed, 1800, phase)
                for case in HIGH for cell in ("full", "canonical", "static", "dynamic")
                for seed in (0, 1, 2)]
    raise ValueError(phase)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "dev", "dev_link", "formal"), required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before simulation")
    if args.workers == 1:
        for job in jobs(args.phase):
            try:
                print("done", run_one(*job), flush=True)
            except Exception as error:
                print("failed", job[:3], repr(error), flush=True)
        return
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(args.phase)}
        for future in as_completed(futures):
            job = futures[future]
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", job[:3], repr(error), flush=True)


if __name__ == "__main__":
    main()

"""Passive decode-batch probe: does path diversity fragment decode batches?

Wraps ``ComputeNode.start_execution`` to count, per GPU, how many layer
executions ran and how many decode requests each carried. Scheduling and
simulated time are unchanged. Development seed 100 only; not a formal result.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

from experiments.v3_cycle_pricing.run import (
    CASES, DEV_SEED, HERE, LOADS, ROOT, digest, physical_input, rel,
    scheduler_factory, write)

DURATION = 300


def run_one(case: str, method: str) -> str:
    import contextlib
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    output = HERE / "runs/batch" / case / f"{method}_seed{DEV_SEED}.json"
    if output.exists():
        return rel(output)
    physical, topology = physical_input(case)
    deployment = ROOT / "rcaps/v3_layouts" / topology
    base_factory = scheduler_factory(case, method)
    stats = defaultdict(lambda: {"executions": 0, "decode_executions": 0,
                                 "decode_requests": 0, "single_decode_executions": 0,
                                 "prompt_executions": 0})

    def factory(simulator):
        for node in simulator.compute_nodes.values():
            original = node.start_execution

            def start_execution(requests, _original=original, _uid=node.node_uid):
                record = stats[_uid]
                decodes = sum(r.phase == RequestPhase.Increment for r in requests)
                record["executions"] += 1
                if decodes:
                    record["decode_executions"] += 1
                    record["decode_requests"] += decodes
                    record["single_decode_executions"] += decodes == 1
                if decodes < len(requests):
                    record["prompt_executions"] += 1
                return _original(requests)

            node.start_execution = start_execution
        return base_factory(simulator)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        row = fixed_window.run(
            topology, "queue_dag", LOADS[case], DURATION, 0, DEV_SEED,
            deployment / "solution.ini", deployment / "simulator_cluster.ini",
            profile_resources=True, compact=True, physical_cluster=physical,
            machine_counts=TopologyModel(physical).machine_counts,
            scheduler_factory=factory)
    total = {k: sum(s[k] for s in stats.values()) for k in next(iter(stats.values()))}
    keep = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
            "completion_fraction", "trace_sha256", "gpu_busy_fraction")
    write(output, {"case": case, "cell": method, "seed": DEV_SEED, "duration_s": DURATION,
                   "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                   "scheduler_sha256": digest(HERE / "scheduler.py"),
                   "probe_sha256": digest(HERE / "batch_probe.py"),
                   **{k: row[k] for k in keep},
                   "mean_gpu_busy_fraction": sum(row["gpu_busy_fraction"].values()) /
                   len(row["gpu_busy_fraction"]),
                   "total": total,
                   "mean_decode_batch": total["decode_requests"] / total["decode_executions"],
                   "single_decode_share": total["single_decode_executions"] / total["decode_executions"],
                   "per_gpu": {str(uid): s for uid, s in sorted(stats.items())}})
    return rel(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--methods", nargs="+", default=["v3", "canonical", "cycle"])
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, case, method)
                   for case in CASES for method in args.methods]
        for future in as_completed(futures):
            print("done", future.result(), flush=True)


if __name__ == "__main__":
    main()

"""Slow-link-gated path admission: audit, development, formal and report.

Phases:
  audit   admitted edge sets (canonical + detours) for both C1 topologies.
  dev     seed 100, 300 s on both topologies (go/no-go per protocol_dev.json).
  formal  seeds 0/1/2, 1800 s on both topologies.
  report  paired analysis against released V3 and canonical-route windows.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from experiments.v3_cohort_routing.run import run_one
from experiments.v3_cycle_pricing.run import (
    CASES, DEV_SEED, FORMAL_SEEDS, digest, scheduler_factory, write)

HERE = Path(__file__).resolve().parent


def builder(case: str, cell: str):
    from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler
    from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
    if cell == "v3":
        return RecordedV3Scheduler
    canonical = scheduler_factory(case, "canonical").keywords["allowed_edges"]
    if cell == "canonical":
        return scheduler_factory(case, "canonical")
    if cell == "gated":
        return partial(SlowLinkGatedScheduler, allowed_edges=canonical)
    raise ValueError(cell)


def audit() -> dict:
    """Instantiate each deployment once and list the admitted edges."""
    from benchmarks.fixed_window import ModelName, load_graph_layout
    from experiments.v3_cycle_pricing.run import ROOT, physical_input
    from rcaps.v3.resource_graph import from_simulator
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.cluster_simulator import ClusterSimulator

    result = {"scheduler_sha256": digest(HERE / "scheduler.py"), "cases": {}}
    for case in CASES:
        physical, topology = physical_input(case)
        deployment = ROOT / "rcaps/v3_layouts" / topology
        sim = ClusterSimulator(model_name=ModelName.LLaMa70B,
                               machine_num_dict=TopologyModel(physical).machine_counts)
        sim.from_ini_file(config_file_name=str(deployment / "simulator_cluster.ini"))
        scheduler = builder(case, "gated")(sim)
        sim.set_scheduler(scheduler)
        sim.init_query_manager()
        sim.mark_as_ready()
        load_graph_layout(sim, deployment / "solution.ini")
        scheduler._allow_placement_edge(sim.source_node.node_uid, 0)
        dag = from_simulator(sim)
        bandwidth = {(l.node_in.node_uid, l.node_out.node_uid): l.bandwidth
                     for l in sim.links.values()}
        result["cases"][case] = {
            "full_edges": len(dag.edge_set),
            "canonical_edges": len(scheduler.canonical_edges),
            "admitted_edges": len(scheduler.allowed_edges),
            "detours": [{"edge": [a, b], "bandwidth_Bps": bandwidth[(a, b)]}
                        for a, b in sorted(scheduler.detour_edges)],
            "slow_canonical_edges": sorted(
                [a, b] for a, b in scheduler.canonical_edges
                if not isinstance(a, str) and not isinstance(b, str)
                and bandwidth[(a, b)] <= 50_000_000)}
    write(HERE / "audit.json", result)
    return result


def jobs(phase: str) -> list:
    if phase == "dev":
        return [(case, "gated", DEV_SEED, 300,
                 HERE / "runs/dev" / case / f"gated_seed{DEV_SEED}.json") for case in CASES]
    return [(case, "gated", seed, 1800, HERE / "runs/formal" / case / f"gated_seed{seed}.json")
            for case in CASES for seed in FORMAL_SEEDS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("audit", "dev", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "audit":
        print(json.dumps(audit(), indent=2))
        return
    if args.phase == "report":
        from experiments.v3_gated_pathspace.report import main as report
        report()
        return
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    if args.phase == "formal" and not (HERE / "protocol.json").exists():
        raise SystemExit("protocol.json must be committed before formal runs")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job, builder=builder, here=HERE): job
                   for job in jobs(args.phase)}
        for future in as_completed(futures):
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", futures[future][:3], repr(error), flush=True)


if __name__ == "__main__":
    main()

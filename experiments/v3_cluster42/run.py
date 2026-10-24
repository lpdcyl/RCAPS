"""Core V3 experiments on the 42-node Helix high-heterogeneity cluster.

Cells (frozen trace protocol, fixed window, no warmup, no tail drain):
  helix       Helix ILP layout (artifact) with Helix MaxFlow online scheduling
  v3          V3 layout (plan.py) with frozen V3 M3 on the full DAG
  gated       V3 layout with slow-link-gated admission (no slow link here, so
              canonical routes); experiments/v3_gated_pathspace/scheduler.py
  v3_off,     v3 / gated with the simulator's one-request decode doubling
  gated_off   switched off (experiments/v3_batch1_counterfactual)

Loads: 2150 (Helix artifact MaxFlow load) and 1450 (Helix artifact Swarm load)
offered token/s. Phases: smoke | formal | report.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from experiments.v3_cycle_pricing.run import FORMAL_SEEDS, ROOT, digest, read, rel, write

HERE = Path(__file__).resolve().parent
BASE = ROOT / "artifact_evaluation/high_heterogeneity"
PHYSICAL = BASE / "config/cluster42.ini"
PROFILE = BASE / "config/machine_profiles.ini"
HELIX = BASE / "layout_llama70b/ilp"
LAYOUT = HERE / "layout"
GATED = ROOT / "experiments/v3_gated_pathspace/scheduler.py"
LOADS = (2150.0, 1450.0)


def canonical_allowed() -> frozenset:
    from experiments.m2_multistage_candidate.placement import validate
    from experiments.v3_pathspace_ablation.run import canonical_edges
    from rcaps.v3.topology import TopologyModel

    state = read(LAYOUT / "placement.json")["state"]
    checked = validate(TopologyModel(PHYSICAL), state)
    offset = 2  # solution.ini uses compute_node_{gpu_id + 2}
    return frozenset((a if isinstance(a, str) else a + offset,
                      b if isinstance(b, str) else b + offset)
                     for a, b in canonical_edges(state, checked["dag"]))


def builder(cell: str):
    from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler
    from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
    if cell.startswith("v3"):
        return RecordedV3Scheduler
    return partial(SlowLinkGatedScheduler, allowed_edges=canonical_allowed())


def run_one(cell: str, load: float, seed: int, duration: int, output: Path) -> str:
    if output.exists():
        return rel(output)
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    if cell.endswith("_off"):
        from experiments.v3_batch1_counterfactual.run import disable_single_decode_doubling
        disable_single_decode_doubling()
    counts = TopologyModel(PHYSICAL).machine_counts
    stats = defaultdict(lambda: [0, 0, 0])
    factory = None
    if cell != "helix":
        base = builder(cell)

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
            return base(simulator)

    layout = HELIX if cell == "helix" else LAYOUT
    solution = layout / ("ilp_sol.ini" if cell == "helix" else "solution.ini")
    sim_cluster = layout / "simulator_cluster.ini"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            # Scenario "single" only names the run; every input is passed explicitly.
            row = fixed_window.run(
                "single", "helix" if cell == "helix" else "queue_dag", load, duration, 0, seed,
                solution, sim_cluster, profile_resources=True, compact=True,
                record_query_samples=True, physical_cluster=PHYSICAL, machine_profile=PROFILE,
                machine_counts=counts, scheduler_factory=factory)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"cell": cell, "load": load, "seed": seed, "error": repr(error),
                   "traceback": traceback.format_exc()})
            raise
    executions = sum(s[0] for s in stats.values())
    row.update({"case": "cluster42", "cell": cell, "load": load, "seed": seed,
                "duration_s": duration, "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                "runner_sha256": digest(HERE / "run.py"),
                "gated_scheduler_sha256": digest(GATED),
                "solution_sha256": digest(solution), "sim_cluster_sha256": digest(sim_cluster),
                "physical_sha256": digest(PHYSICAL),
                "gpu_seconds_per_output_token": sum(row["gpu_busy_fraction"].values()) /
                max(row["output_throughput_tokens_per_s"], 1e-9)})
    if executions:
        row["decode_batches"] = {
            "executions": executions,
            "mean_batch": sum(s[1] for s in stats.values()) / executions,
            "single_share": sum(s[2] for s in stats.values()) / executions}
    write(output, row)
    return rel(output)


def jobs(phase: str) -> list:
    if phase == "smoke":
        return [(cell, load, 100, 60, HERE / "runs/smoke" / f"load{load:g}" / f"{cell}.json")
                for load in LOADS for cell in ("helix", "v3", "gated")]
    plan = read(HERE / "protocol.json")["formal"]["cells"]
    return [(cell, float(load), seed, 1800,
             HERE / "runs/formal" / f"load{float(load):g}" / f"{cell}_seed{seed}.json")
            for seed in FORMAL_SEEDS for load, cells in plan.items() for cell in cells]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "report":
        from experiments.v3_cluster42.report import main as report
        report()
        return
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    if args.phase == "formal" and not (HERE / "protocol.json").exists():
        raise SystemExit("protocol.json must be committed before formal runs")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(args.phase)}
        for future in as_completed(futures):
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", futures[future][:3], repr(error), flush=True)


if __name__ == "__main__":
    main()

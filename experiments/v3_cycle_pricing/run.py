"""Run the full-cycle session pricing candidate against frozen V3.

Phases:
  dev     seed 100, 300 s: frozen V3, canonical routes and the candidate on
          both C1 topologies, with per-request hop records (mechanism check).
  formal  seeds 0/1/2, 1800 s: the candidate, plus a frozen-V3 rerun that
          must reproduce the released window and adds hop records.
  report  paired analysis against released V3 and canonical-route windows.

Frozen code, layouts and released runs are read only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = ("C1_single", "C1_multi")
LOADS = {"C1_single": 700.0, "C1_multi": 320.0}
FORMAL_SEEDS = (0, 1, 2)
DEV_SEED = 100
DEV_DURATION = 300
FORMAL_DURATION = 1800
RELEASED = {"C1_single": "benchmarks/runs/single/seed{seed}/rcaps_v3.json",
            "C1_multi": "benchmarks/runs/multi/seed{seed}/rcaps_v3.json"}
CANONICAL = "experiments/v3_pathspace_ablation/runs/formal/{case}/seed{seed}.json"
PARITY_FIELDS = ("trace_sha256", "output_throughput_tokens_per_s", "ttft_p95_s",
                 "tpot_p95_s", "completion_fraction", "backlog_at_window_end",
                 "route_counts", "query_samples")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    part.replace(path)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def physical_input(case: str) -> tuple[Path, str]:
    """Physical cluster file with its frozen hash; the planning template is
    not used here (its recorded hash is of a CRLF checkout)."""
    item = read(ROOT / "rcaps/v3/planning_inputs.json")[case]
    physical = ROOT / item["physical"]
    if digest(physical) != item["physical_sha256"]:
        raise ValueError(f"Physical resource changed for {case}")
    return physical, item["scenario"]


def scheduler_factory(case: str, method: str):
    from experiments.v3_cycle_pricing.scheduler import (
        FullCycleSessionScheduler, RecordedV3Scheduler, RouteRecorder)
    if method == "v3":
        return RecordedV3Scheduler
    if method == "cycle":
        return FullCycleSessionScheduler
    if method == "canonical":
        from experiments.m2_multistage_candidate.placement import validate
        from experiments.v3_pathspace_ablation.run import (
            CanonicalGraphDagScheduler, canonical_edges, layout)
        from rcaps.v3.topology import TopologyModel

        class RecordedCanonical(RouteRecorder, CanonicalGraphDagScheduler):
            pass

        physical, _ = physical_input(case)
        state = read(layout(case) / "placement.json")["state"]
        checked = validate(TopologyModel(physical), state)
        offset = 2  # solution.ini uses compute_node_{gpu_id + 2}
        allowed = frozenset((a if isinstance(a, str) else a + offset,
                             b if isinstance(b, str) else b + offset)
                            for a, b in canonical_edges(state, checked["dag"]))
        return partial(RecordedCanonical, allowed_edges=allowed)
    raise ValueError(method)


def run_one(case: str, method: str, seed: int, duration: int, output: Path) -> str:
    if output.exists():
        return rel(output)
    import contextlib
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel

    physical, topology = physical_input(case)
    deployment = ROOT / "rcaps/v3_layouts" / topology
    holder = {}
    base_factory = scheduler_factory(case, method)

    def factory(simulator):
        holder["scheduler"] = base_factory(simulator)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    log = output.with_suffix(".log")
    with log.open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window.run(
                topology, "queue_dag", LOADS[case], duration, 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=factory)
            records = getattr(holder["scheduler"], "route_records", {})
            route_hops = {str(uid): {"hops": hops, "partial_hops": partial_hops}
                          for uid, (hops, partial_hops) in records.items()}
            row.update({"case": case, "cell": method, "seed": seed,
                        "duration_s": duration,
                        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                        "scheduler_sha256": digest(HERE / "scheduler.py"),
                        "solution_sha256": digest(deployment / "solution.ini"),
                        "sim_cluster_sha256": digest(deployment / "simulator_cluster.ini"),
                        "physical_sha256": digest(physical),
                        "route_hops": route_hops})
            write(output, row)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"case": case, "cell": method, "seed": seed,
                   "error": repr(error), "traceback": traceback.format_exc()})
            raise
    return rel(output)


def jobs(phase: str) -> list[tuple[str, str, int, int, Path]]:
    if phase == "dev":
        return [(case, method, DEV_SEED, DEV_DURATION,
                 HERE / "runs/dev" / case / f"{method}_seed{DEV_SEED}.json")
                for case in CASES for method in ("v3", "canonical", "cycle")]
    return [(case, method, seed, FORMAL_DURATION,
             HERE / "runs/formal" / case / f"{method}_seed{seed}.json")
            for method in ("cycle", "v3") for case in CASES for seed in FORMAL_SEEDS]


def execute(phase: str, workers: int) -> None:
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    if phase == "formal" and not (HERE / "protocol.json").exists():
        raise SystemExit("protocol.json must be committed before formal runs")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(phase)}
        for future in as_completed(futures):
            case, method, seed, _, _ = futures[future]
            try:
                print("done", future.result(), flush=True)
            except Exception as error:  # failure JSON is kept beside the log
                print("failed", case, method, seed, repr(error), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("dev", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "report":
        from experiments.v3_cycle_pricing.report import main as report
        report()
    else:
        execute(args.phase, args.workers)


if __name__ == "__main__":
    main()

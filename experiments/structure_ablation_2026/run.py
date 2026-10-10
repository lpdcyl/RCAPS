"""Evaluate one 70B structure under the unchanged RCAPS online scheduler."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run
from rcaps.placement.partition import ROOT, scenario as physical_scenario
from rcaps.placement.topology import TopologyModel
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "validation_2026" / "runs70b"
LOADS = {"single": 700.0, "multi": 320.0}
ARMS = {"single": ("s1_all24", "s1_lean", "s3_prefix11", "s2_prefix12"),
        "multi": ("s1_all24", "s1_lean", "s3_prefix10", "s3_prefix11",
                  "s2_prefix12")}


def layout_for(scenario: str, arm: str) -> tuple[Path, Path, dict]:
    if arm == "s2_prefix12":
        directory = ROOT / "rcaps/layouts" / scenario
        placement = json.loads((directory / "placement.json").read_text(encoding="utf-8"))
        model = TopologyModel(physical_scenario(scenario)[0])
        spans = {int(node): interval for node, interval in placement["intervals"].items()}
        assigned = sum(end - start for start, end in spans.values())
        active_capacity = sum(model.capacity[node] for node in spans)
        capacity = {"active_gpu_count": len(spans),
                    "assigned_layer_replicas": assigned,
                    "active_capacity_utilization": assigned / active_capacity,
                    "pool_capacity_utilization": assigned / sum(model.capacity.values())}
    else:
        directory = HERE / "layouts" / scenario / arm
        metadata = json.loads((directory / "structure.json").read_text(encoding="utf-8"))
        capacity = metadata["capacity"]
    return directory / "solution.ini", directory / "simulator_cluster.ini", capacity


def evaluate(scenario: str, arm: str, seed: int, duration: int,
             offered: float | None = None) -> dict:
    offered = LOADS[scenario] if offered is None else offered
    solution, sim_cluster, capacity = layout_for(scenario, arm)
    result = run(scenario, "queue_dag", offered, duration, 0, seed,
                 solution, sim_cluster, profile_resources=True,
                 scheduler_factory=QueueAwareDagScheduler, compact=True,
                 record_query_samples=True)
    if duration == 1800 and offered == LOADS[scenario]:
        reference = json.loads((REFERENCE / scenario / f"seed{seed}" /
                                "rcaps.json").read_text(encoding="utf-8"))
        fields = ("trace_sha256", "arrivals", "duration_s", "warmup_s",
                  "offered_tokens_per_s", "evaluation_protocol")
        mismatch = [field for field in fields if result[field] != reference[field]]
        if mismatch:
            raise ValueError(f"Structure and S2 trace/window differ: {mismatch}")
    result.update({"system": arm, "structural_arm": arm,
                   "placement_structure": ("single_path" if arm.startswith("s1_")
                                           else "shared_prefix_two_suffixes"),
                   "online_scheduler": "QueueAwareDagScheduler",
                   "active_gpu_count": capacity["active_gpu_count"],
                   "assigned_layer_replicas": capacity["assigned_layer_replicas"],
                   "active_capacity_utilization": capacity["active_capacity_utilization"],
                   "pool_capacity_utilization": capacity["pool_capacity_utilization"],
                   "solution_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
                   "sim_cluster_sha256": hashlib.sha256(sim_cluster.read_bytes()).hexdigest()})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=LOADS, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--offered", type=float)
    parser.add_argument("--output-root", type=Path, default=HERE / "runs70b")
    args = parser.parse_args()
    if args.arm not in ARMS[args.scenario]:
        parser.error(f"{args.arm} is not generated for {args.scenario}")
    if args.duration <= 0:
        parser.error("duration must be positive")
    output = (args.output_root / args.scenario / f"seed{args.seed}" /
              f"{args.arm}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_suffix(".json.lock")
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        print(f"already running: {output}", flush=True)
        return
    try:
        if output.exists():
            print(f"skip {output}", flush=True)
            return
        result = evaluate(args.scenario, args.arm, args.seed, args.duration,
                          args.offered)
        partial = output.with_suffix(".json.part")
        partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        partial.replace(output)
        print(f"done {output}", flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

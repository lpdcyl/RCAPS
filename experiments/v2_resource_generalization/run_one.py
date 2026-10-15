"""Run one paired fixed-window resource-pool benchmark with input hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from benchmarks.fixed_window import run
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

from .prepare import BASE, HERE, ROOT, COUNTS


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=COUNTS)
    parser.add_argument("--method", required=True,
                        choices=("adaptive", "fixed_branches", "fixed_structure",
                                 "helix", "helix_petals"))
    parser.add_argument("--offered", type=float, required=True)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.duration <= 0 or args.offered <= 0:
        parser.error("duration and offered load must be positive")
    physical = HERE / "pools" / args.case / "physical.ini"
    layout = HERE / "layouts" / args.case / (
        "petals" if args.method == "helix_petals" else
        "helix_numeric" if args.method == "helix" else args.method)
    if args.case == "C1" and args.method == "helix":
        layout = ROOT / "artifact_evaluation/single_cluster/layout_llama70b/ilp"
    solution = layout / ({"helix": "ilp_sol.ini", "helix_petals": "petals_sol.ini"}
                         .get(args.method, "solution.ini"))
    cluster = layout / "simulator_cluster.ini"
    for path in (physical, solution, cluster):
        if not path.is_file():
            raise FileNotFoundError(path)
    identity = {"case": args.case, "method": args.method,
                "offered_tokens_per_s": args.offered, "duration_s": args.duration,
                "seed": args.seed, "warmup_s": 0,
                "physical_sha256": digest(physical),
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster)}
    output = args.output or (HERE / "runs" / args.case / f"{args.duration}s" /
                              f"load{args.offered:g}" /
                              f"seed{args.seed}" / f"{args.method}.json")
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        if all(old.get(key) == value for key, value in identity.items()):
            print(f"skip {output}")
            return
        raise ValueError(f"Existing result differs from requested inputs: {output}")
    is_helix_scheduler = args.method in ("helix", "helix_petals")
    result = run("single", "helix" if is_helix_scheduler else "queue_dag",
                 args.offered, args.duration, 0, args.seed, solution, cluster,
                 profile_resources=not is_helix_scheduler,
                 scheduler_factory=(None if is_helix_scheduler
                                    else QueueAwareDagScheduler),
                 compact=True, record_query_samples=True,
                 physical_cluster=physical,
                 machine_profile=BASE / "config/machine_profile.ini",
                 machine_counts=COUNTS[args.case])
    result.update(identity)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".json.part")
    partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    partial.replace(output)
    print(f"done {output}")


if __name__ == "__main__":
    os.environ.setdefault("MPLBACKEND", "Agg")
    main()

"""Fixed-window comparison for the queue-aware layered DAG scheduler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.critical_graph.fixed_window import run
from experiments.queue_dag.scheduler_final import QueueAwareDagScheduler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--sim-cluster", type=Path, required=True)
    parser.add_argument("--physical-cluster", type=Path)
    parser.add_argument("--offered", type=float, required=True)
    parser.add_argument("--duration", type=int, default=1980)
    parser.add_argument("--warmup", type=int, default=180)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--policy", default="final",
                        help="final (default); coalesced_corrected replays old results. "
                             "Other historical names are in experimental/policies.py")
    parser.add_argument("--checkpoint-file", type=Path)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--profile-scheduler", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.policy in ("final", "coalesced_corrected"):
        scheduler = QueueAwareDagScheduler
    else:
        # Keep old ablation commands reproducible without crowding the normal
        # entry point with every discarded candidate.
        from experiments.queue_dag.experimental.policies import POLICY_NAMES, scheduler_for

        if args.policy not in POLICY_NAMES:
            parser.error(f"Unknown policy: {args.policy}")
        scheduler = scheduler_for(args.policy, args.solution)
    result = run(args.scenario, "queue_dag", args.offered, args.duration,
                 args.warmup, args.seed, args.solution, args.sim_cluster,
                 scheduler_factory=scheduler,
                 checkpoint_file=args.checkpoint_file,
                 checkpoint_every=args.checkpoint_every, compact=args.compact,
                 physical_cluster=args.physical_cluster,
                 profile_scheduler=args.profile_scheduler)
    result["routing_policy"] = args.policy
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

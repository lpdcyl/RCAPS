"""Evaluate a frozen V2 diagnostic placement at a new offered load."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "experiments/v2_core_ablations"
LOADS = (350.0, 525.0, 700.0)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidates() -> list[str]:
    data = json.loads((SOURCE / "modeling_candidates/single.json").read_text(encoding="utf-8"))
    return data["diagnostic_ids"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, choices=candidates())
    parser.add_argument("--offered", required=True, type=float, choices=LOADS)
    parser.add_argument("--seed", type=int, default=100)
    args = parser.parse_args()
    layout = SOURCE / "layouts/diagnostic/single" / args.candidate
    solution, cluster = layout / "solution.ini", layout / "simulator_cluster.ini"
    if args.offered == 700.0 and args.seed in (100, 101):
        existing = SOURCE / "diagnostic_runs/single" / args.candidate / f"seed{args.seed}.json"
        if existing.is_file():
            print(f"reuse {existing}")
            return
    output = (HERE / "runs" / f"load{args.offered:g}" /
              args.candidate / f"seed{args.seed}.json")
    identity = {"candidate_id": args.candidate, "scenario": "single",
                "offered_tokens_per_s": args.offered, "duration_s": 600,
                "warmup_s": 0, "seed": args.seed,
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster)}
    if output.exists():
        old = json.loads(output.read_text(encoding="utf-8"))
        if all(old.get(key) == value for key, value in identity.items()):
            print(f"skip {output}")
            return
        raise ValueError(f"Existing output has different inputs: {output}")
    result = run("single", "queue_dag", args.offered, 600, 0, args.seed,
                 solution, cluster, profile_resources=True,
                 scheduler_factory=QueueAwareDagScheduler,
                 compact=True, record_query_samples=True)
    result.update(identity)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".json.part")
    partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    partial.replace(output)
    print(f"done {output}")


if __name__ == "__main__":
    main()

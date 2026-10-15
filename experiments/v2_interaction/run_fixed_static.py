"""Missing A cell: fixed V2 placement with static-cost legal DAG routing."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run
from experiments.v2_core_ablations.adapters import StaticCostDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOAD = {"single": 700.0, "multi": 320.0}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=LOAD)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--offered", type=float)
    args = parser.parse_args()
    layout = ROOT / "rcaps" / "v2_layouts" / f"{args.scenario}_fixed"
    solution = layout / "solution.ini"
    cluster = layout / "simulator_cluster.ini"
    offered = LOAD[args.scenario] if args.offered is None else args.offered
    output = (HERE / "runs" / f"{args.duration}s" / f"load{offered:g}" /
              args.scenario / f"seed{args.seed}" / "fixed_static.json")
    identity = {"scenario": args.scenario, "seed": args.seed,
                "offered_tokens_per_s": offered,
                "duration_s": args.duration, "warmup_s": 0,
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster),
                "scheduler": "StaticCostDagScheduler"}
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if all(existing.get(key) == value for key, value in identity.items()):
            print(f"skip {output}")
            return
        raise ValueError(f"Existing output has different inputs: {output}")
    result = run(args.scenario, "queue_dag", offered, args.duration,
                 0, args.seed, solution, cluster, profile_resources=True,
                 scheduler_factory=StaticCostDagScheduler, compact=True,
                 record_query_samples=True)
    result.update(identity)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".json.part")
    partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    partial.replace(output)
    print(f"done {output}")


if __name__ == "__main__":
    main()

"""Run phase-corrected layouts with the unchanged online scheduler."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOADS = {"single": 700.0, "multi": 320.0}


def execute(name: str, seed: int, *, duration: int = 1800) -> Path:
    if seed not in (0, 1, 2):
        raise ValueError("This experiment uses only seeds 0, 1, 2")
    layout = HERE / "layouts" / name
    solution = layout / "solution.ini"
    cluster = layout / "simulator_cluster.ini"
    output = HERE / "runs70b" / name / f"seed{seed}" / "rcaps_queue_phase.json"
    if output.exists():
        raise FileExistsError(output)
    result = run(name, "queue_dag", LOADS[name], duration, 0, seed,
                 solution, cluster, scheduler_factory=QueueAwareDagScheduler,
                 profile_resources=True, compact=True, record_query_samples=True)
    result.update({"system": "rcaps_queue_phase",
                   "solution_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
                   "sim_cluster_sha256": hashlib.sha256(cluster.read_bytes()).hexdigest()})
    if duration == 1800:
        baseline = json.loads((ROOT / "experiments/validation_2026/runs70b" /
                               name / f"seed{seed}" / "rcaps.json").read_text(encoding="utf-8"))
        for field in ("trace_sha256", "duration_s", "offered_tokens_per_s",
                      "warmup_s", "arrivals", "evaluation_protocol"):
            if result[field] != baseline[field]:
                raise AssertionError(f"Protocol mismatch: {name} seed{seed} {field}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.part")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, choices=LOADS)
    parser.add_argument("--seed", required=True, type=int, choices=(0, 1, 2))
    parser.add_argument("--duration", default=1800, type=int)
    args = parser.parse_args()
    print(execute(args.scenario, args.seed, duration=args.duration))

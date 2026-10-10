"""Run the queue-predicted placement with the unchanged RCAPS scheduler."""

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


def execute(name: str, seed: int, duration: int, output: Path) -> Path:
    if seed not in (0, 1, 2):
        raise ValueError("This experiment is limited to seeds 0, 1, and 2")
    layout = HERE / "layouts" / name
    solution = layout / "solution.ini"
    cluster = layout / "simulator_cluster.ini"
    result = run(name, "queue_dag", LOADS[name], duration, 0, seed,
                 solution, cluster, scheduler_factory=QueueAwareDagScheduler,
                 profile_resources=True, compact=True, record_query_samples=True)
    result.update({"system": "rcaps_queue_predictor",
                   "solution_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
                   "sim_cluster_sha256": hashlib.sha256(cluster.read_bytes()).hexdigest()})
    if duration == 1800:
        baseline = json.loads((ROOT / "experiments/validation_2026/runs70b" /
                               name / f"seed{seed}" / "rcaps.json").read_text(
                                   encoding="utf-8"))
        for field in ("trace_sha256", "duration_s", "offered_tokens_per_s",
                      "warmup_s", "arrivals"):
            if result[field] != baseline[field]:
                raise AssertionError(f"Protocol mismatch: {name} seed{seed} {field}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=LOADS, required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--output-root", type=Path, default=HERE / "runs70b")
    args = parser.parse_args()
    target = args.output_root / args.scenario / f"seed{args.seed}" / "rcaps_queue_predictor.json"
    if target.exists():
        raise FileExistsError(target)
    print(execute(args.scenario, args.seed, args.duration, target))


if __name__ == "__main__":
    main()

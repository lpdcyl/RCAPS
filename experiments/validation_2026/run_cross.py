"""Run the two off-diagonal placement-by-scheduler combinations on 70B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from baselines.helix import layout as helix_layout
from benchmarks.fixed_window import run
from rcaps.method import layout as rcaps_layout
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOADS = {"single": 700.0, "multi": 320.0}
ARMS = ("helix_layout_rcaps_scheduler", "rcaps_layout_helix_scheduler")


def check_reference(result: dict, scenario: str, seed: int) -> None:
    for path in (ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / "helix.json",
                 HERE / "runs70b" / scenario / f"seed{seed}" / "rcaps.json"):
        reference = json.loads(path.read_text(encoding="utf-8"))
        fields = ("trace_sha256", "arrivals", "duration_s", "warmup_s",
                  "offered_tokens_per_s", "evaluation_protocol")
        mismatch = [field for field in fields if result[field] != reference[field]]
        if mismatch:
            raise ValueError(f"Request/window mismatch against {path}: {mismatch}")


def evaluate(scenario: str, seed: int, arm: str) -> dict:
    if arm == "helix_layout_rcaps_scheduler":
        solution, sim_cluster = helix_layout(scenario, ROOT)
        result = run(scenario, "queue_dag", LOADS[scenario], 1800, 0, seed,
                     solution, sim_cluster,
                     scheduler_factory=QueueAwareDagScheduler,
                     compact=True, record_query_samples=True)
        placement, scheduler = "helix", "rcaps"
    elif arm == "rcaps_layout_helix_scheduler":
        solution, sim_cluster = rcaps_layout(scenario, ROOT)
        result = run(scenario, "helix", LOADS[scenario], 1800, 0, seed,
                     solution, sim_cluster,
                     compact=True, record_query_samples=True)
        placement, scheduler = "rcaps", "helix"
    else:
        raise ValueError(arm)
    check_reference(result, scenario, seed)
    result.update({
        "system": arm,
        "placement": placement,
        "online_scheduler": scheduler,
        "solution_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
        "sim_cluster_sha256": hashlib.sha256(sim_cluster.read_bytes()).hexdigest(),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=LOADS, required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=HERE / "cross_runs70b")
    args = parser.parse_args()
    output = (args.output_root / args.scenario / f"seed{args.seed}" /
              f"{args.arm}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_suffix(".json.lock")
    try:
        with lock.open("x", encoding="utf-8") as stream:
            stream.write("running\n")
    except FileExistsError:
        print(f"already running: {output}", flush=True)
        return
    try:
        if output.exists():
            print(f"skip {output}", flush=True)
            return
        result = evaluate(args.scenario, args.seed, args.arm)
        partial = output.with_suffix(".json.part")
        partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        partial.replace(output)
        print(f"done {output}", flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

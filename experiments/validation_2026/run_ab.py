"""Three-seed search ablation and passive bottleneck profile on LLaMA-2 70B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run
from experiments.validation_2026.equivalence import static_single_equals_coarse
from rcaps.ablations import variant_layout
from rcaps.method import layout as final_layout
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


ROOT = Path(__file__).resolve().parents[2]
LOADS = {"single": 700.0, "multi": 320.0}
METHODS = ("rcaps_coarse", "rcaps_full_search", "rcaps",
           "rcaps_static_no_graph")


def paths(method: str, scenario: str) -> tuple[Path, Path]:
    return (final_layout(scenario, ROOT) if method == "rcaps" else
            variant_layout(method, scenario, ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", nargs="+", choices=LOADS,
                        default=list(LOADS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--methods", nargs="+", choices=METHODS,
                        default=list(METHODS))
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "experiments/validation_2026/runs70b")
    args = parser.parse_args()
    for scenario in args.scenarios:
        for seed in args.seeds:
            for method in args.methods:
                if scenario == "single" and method == "rcaps_static_no_graph":
                    if not static_single_equals_coarse():
                        raise AssertionError("Static single layout differs from topology-only")
                    if seed in (1, 2):
                        print(f"equivalent: single seed{seed} static = coarse", flush=True)
                        continue
                solution, cluster = paths(method, scenario)
                output = args.output_dir / scenario / f"seed{seed}" / f"{method}.json"
                if output.exists():
                    print(f"skip {output}", flush=True)
                    continue
                result = run(scenario, "queue_dag", LOADS[scenario],
                             args.duration, 0, seed, solution, cluster,
                             scheduler_factory=QueueAwareDagScheduler,
                             profile_resources=True, compact=True,
                             record_query_samples=True)
                result.update({
                    "system": method,
                    "solution_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
                    "sim_cluster_sha256": hashlib.sha256(cluster.read_bytes()).hexdigest(),
                })
                output.parent.mkdir(parents=True, exist_ok=True)
                partial = output.with_suffix(".json.part")
                partial.write_text(json.dumps(result, indent=2) + "\n",
                                   encoding="utf-8")
                partial.replace(output)
                print(f"done {output}", flush=True)


if __name__ == "__main__":
    main()

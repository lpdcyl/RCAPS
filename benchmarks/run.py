"""Run RCAPS and registered baselines with one trace and metric protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from .registry import MAIN_METHOD, METHODS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "benchmarks" / "runs"
PAPER_LOAD = {"single": 700.0, "multi": 320.0}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_file(results_dir: Path, scenario: str, seed: int,
                method: str) -> Path:
    return results_dir / scenario / f"seed{seed}" / f"{method}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--methods", nargs="+", choices=sorted(METHODS),
                        default=list(METHODS))
    parser.add_argument("--scenarios", nargs="+", choices=PAPER_LOAD,
                        default=list(PAPER_LOAD))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--offered-single", type=float, default=PAPER_LOAD["single"])
    parser.add_argument("--offered-multi", type=float, default=PAPER_LOAD["multi"])
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--warmup", type=int, default=0)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Replace results from an earlier protocol or layout")
    args = parser.parse_args()
    if args.duration <= args.warmup or args.warmup < 0:
        parser.error("duration must exceed a nonnegative warmup")

    loads = {"single": args.offered_single, "multi": args.offered_multi}
    for scenario in args.scenarios:
        for seed in args.seeds:
            for name in args.methods:
                spec = METHODS[name]
                solution, cluster = spec.layout(scenario, ROOT)
                if not solution.is_file() or not cluster.is_file():
                    raise FileNotFoundError(f"Missing {name} layout: {solution}, {cluster}")
                output = output_file(args.results_dir, scenario, seed, name)
                identity = {
                    "system": name, "scenario": scenario, "seed": seed,
                    "offered_tokens_per_s": loads[scenario],
                    "duration_s": args.duration, "warmup_s": args.warmup,
                    "solution_sha256": digest(solution),
                    "sim_cluster_sha256": digest(cluster),
                }
                if args.dry_run:
                    print(f"{spec.role:8} {scenario:6} seed={seed} {name:8} -> {output}")
                    continue
                if output.exists() and not args.force:
                    previous = json.loads(output.read_text(encoding="utf-8"))
                    if all(previous.get(key) == value for key, value in identity.items()):
                        print(f"skip {output}")
                        continue
                    raise ValueError(f"Existing result has different inputs: {output}; use --force")
                os.environ.setdefault("MPLBACKEND", "Agg")
                result = spec.evaluate(scenario, loads[scenario], args.duration,
                                       args.warmup, seed, solution, cluster)
                result.update(identity)
                result["role"] = spec.role
                result["main_method"] = MAIN_METHOD
                output.parent.mkdir(parents=True, exist_ok=True)
                partial = output.with_suffix(".json.part")
                partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                partial.replace(output)
                print(f"done {output}")


if __name__ == "__main__":
    main()

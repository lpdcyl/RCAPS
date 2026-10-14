"""Run only missing formal incremental-ablation windows, preserving old logs."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from benchmarks.registry import METHODS
from benchmarks.run import ROOT, digest, output_file, run_child
from experiments.v2_method_ablation.report import RUNS, SCENARIOS, SEEDS
from experiments.v2_method_ablation.adapters import NAME_A, NAME_AB, NAME_BASE


FORMAL_METHODS = (NAME_BASE, NAME_A, NAME_AB)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("workers must be between 1 and 4")
    args.offered_single = 700.0
    args.offered_multi = 320.0
    args.duration = 1800
    args.warmup = 0
    args.force = False
    jobs = []
    skipped = 0
    for scenario in SCENARIOS:
        for seed in SEEDS:
            for method in FORMAL_METHODS:
                solution, sim_cluster = METHODS[method].layout(scenario, ROOT)
                expected = {
                    "system": method, "scenario": scenario, "seed": seed,
                    "offered_tokens_per_s": (args.offered_single if scenario == "single"
                                             else args.offered_multi),
                    "duration_s": args.duration, "warmup_s": args.warmup,
                    "query_samples_schema": 1,
                    "solution_sha256": digest(solution),
                    "sim_cluster_sha256": digest(sim_cluster),
                }
                output = output_file(RUNS, scenario, seed, method)
                if output.exists():
                    previous = json.loads(output.read_text(encoding="utf-8"))
                    if any(previous.get(key) != value for key, value in expected.items()):
                        raise ValueError(f"Existing record differs from formal inputs: {output}")
                    skipped += 1
                else:
                    jobs.append((scenario, seed, method))
    print(f"audited existing: {skipped}; missing formal windows: {len(jobs)}", flush=True)
    if args.dry_run:
        for scenario, seed, method in jobs:
            print(f"{scenario} seed={seed} {method}")
        return
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_child, RUNS.resolve(), scenario, seed, method, args):
                   (scenario, seed, method) for scenario, seed, method in jobs}
        for future in as_completed(futures):
            scenario, seed, method = futures[future]
            _, code, log = future.result()
            print(f"{scenario} seed={seed} {method}: "
                  f"{'done' if code == 0 else f'failed ({code})'}; {log}", flush=True)
            if code:
                failures.append(str(log))
    if failures:
        raise SystemExit(f"{len(failures)} formal runs failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()

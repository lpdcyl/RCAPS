"""Parallelize independent fixed-window simulator processes without shared state."""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def run_job(name: str, argv: list[str]) -> tuple[str, int]:
    log = HERE / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(argv) + "\n\n")
        stream.flush()
        done = subprocess.run(argv, cwd=ROOT, stdout=stream,
                              stderr=subprocess.STDOUT, check=False)
    return name, done.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--scenarios", nargs="+", choices=("single", "multi"),
                        default=["single", "multi"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    args = parser.parse_args()
    jobs = []
    for scenario in args.scenarios:
        for seed in args.seeds:
            for method in ("rcaps_coarse", "rcaps_full_search", "rcaps",
                           "rcaps_static_no_graph"):
                name = f"ab_{scenario}_seed{seed}_{method}"
                cmd = [sys.executable, "-u", "-m",
                       "experiments.validation_2026.run_ab", "--scenarios", scenario,
                       "--seeds", str(seed), "--methods", method]
                jobs.append((name, cmd))
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, name, command): name
                   for name, command in jobs}
        for future in as_completed(futures):
            name, code = future.result()
            print(f"{name}: {'done' if code == 0 else f'FAILED {code}'}", flush=True)
            if code:
                failures.append(name)
    if failures:
        raise SystemExit(f"Failed jobs: {', '.join(failures)}")


if __name__ == "__main__":
    main()

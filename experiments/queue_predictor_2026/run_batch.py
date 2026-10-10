"""Bounded local process batch for the three-seed queue-predictor evaluation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def job(scenario: str, seed: int) -> tuple[str, int]:
    name = f"queue_{scenario}_seed{seed}"
    log = HERE / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, "-u", "-m", "experiments.queue_predictor_2026.run",
            "--scenario", scenario, "--seed", str(seed)]
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(argv) + "\n\n")
        stream.flush()
        completed = subprocess.run(argv, cwd=ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    return name, completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--scenarios", nargs="+", choices=("single", "multi"),
                        default=["single", "multi"])
    parser.add_argument("--seeds", nargs="+", type=int, choices=(0, 1, 2),
                        default=[0, 1, 2])
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(job, scenario, seed)
                   for scenario in args.scenarios for seed in args.seeds]
        failures = []
        for future in as_completed(futures):
            name, status = future.result()
            print(f"{name}: {'done' if status == 0 else f'FAILED {status}'}",
                  flush=True)
            if status:
                failures.append(name)
    if failures:
        raise SystemExit("Failed jobs: " + ", ".join(failures))


if __name__ == "__main__":
    main()

"""Run the 12 independent 2x2 crossover simulations with bounded workers."""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from experiments.validation_2026.run_cross import ARMS, HERE, LOADS


ROOT = Path(__file__).resolve().parents[2]


def launch(scenario: str, seed: int, arm: str) -> tuple[str, int]:
    name = f"cross_{scenario}_seed{seed}_{arm}"
    log = HERE / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "-m",
               "experiments.validation_2026.run_cross",
               "--scenario", scenario, "--seed", str(seed), "--arm", arm]
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    return name, completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--scenarios", nargs="+", choices=LOADS,
                        default=list(LOADS))
    parser.add_argument("--seeds", nargs="+", type=int, choices=(0, 1, 2),
                        default=[0, 1, 2])
    parser.add_argument("--arms", nargs="+", choices=ARMS,
                        default=list(ARMS))
    args = parser.parse_args()
    jobs = [(scenario, seed, arm) for scenario in args.scenarios
            for seed in args.seeds for arm in args.arms]
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(launch, *job): job for job in jobs}
        for future in as_completed(futures):
            name, code = future.result()
            print(f"{name}: {'done' if code == 0 else f'FAILED {code}'}", flush=True)
            if code:
                failed.append(name)
    if failed:
        raise SystemExit("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()

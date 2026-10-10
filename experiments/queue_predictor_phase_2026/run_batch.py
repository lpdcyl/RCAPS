"""Run exactly two topologies times seeds 0, 1, 2 with bounded workers."""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def job(name: str, seed: int) -> tuple[str, int]:
    label = f"phase_{name}_seed{seed}"
    log = HERE / "logs" / f"{label}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-u", "-m", "experiments.queue_predictor_phase_2026.run",
            "--scenario", name, "--seed", str(seed)]
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(args) + "\n\n")
        stream.flush()
        completed = subprocess.run(args, cwd=ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    return label, completed.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(job, name, seed)
                   for name in ("single", "multi") for seed in (0, 1, 2)]
        for future in as_completed(futures):
            label, status = future.result()
            print(f"{label}: {'done' if status == 0 else f'FAILED {status}'}", flush=True)
            if status:
                failures.append(label)
    if failures:
        raise SystemExit("Failed jobs: " + ", ".join(failures))

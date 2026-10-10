"""Run three-seed official-load offline comparisons with KV-guided admission."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import gurobipy


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs_dynamic"
VERSION = ".".join(map(str, gurobipy.gurobi.version()))


def valid(path: Path, scenario: str, method: str, seed: int) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data["scenario"] == scenario and data["method"] == method and
                data["seed"] == seed and data["workload"] == "offline_kv_guided" and
                data["warmup_s"] == 60 and data["measurement_s"] == 600 and
                data["gurobi_version"] == VERSION)
    except (ValueError, OSError, KeyError):
        return False


def run(job: tuple[str, str, int], python: Path) -> tuple[str, float]:
    scenario, method, seed = job
    target = RUNS / f"seed{seed}" / f"{scenario}_{method}.json"
    if valid(target, scenario, method, seed):
        return "skipped", 0.0
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".json.part")
    command = [str(python), "-u", "-m", "experiments.baseline_audit.offline_compare",
               "--scenario", scenario, "--method", method, "--seed", str(seed),
               "--output", str(partial)]
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"
    environment["MPLBACKEND"] = "Agg"
    started = time.monotonic()
    with target.with_suffix(".log").open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, env=environment,
                                stdout=stream, stderr=subprocess.STDOUT,
                                check=False)
    elapsed = time.monotonic() - started
    if result.returncode != 0 or not partial.is_file():
        return f"failed (exit {result.returncode})", elapsed
    data = json.loads(partial.read_text(encoding="utf-8"))
    if (data["scenario"], data["method"], data["seed"], data["workload"]) != (
            scenario, method, seed, "offline_kv_guided"):
        return "failed (identity mismatch)", elapsed
    os.replace(partial, target)
    return "done", elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    if gurobipy.gurobi.version()[0] != 13:
        parser.error("Gurobi 13 is required")
    jobs = [(scenario, method, seed) for seed in args.seeds
            for scenario in ("single", "multi")
            for method in ("helix", "integrated")]
    print(f"Running {len(jobs)} offline comparisons, Gurobi={VERSION}",
          flush=True)
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, job, args.python): job for job in jobs}
        for index, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            try:
                status, elapsed = future.result()
            except Exception as error:
                status, elapsed = f"failed ({type(error).__name__}: {error})", 0.0
            print(f"[{index}/{len(jobs)}] {job}: {status}; {elapsed:.1f}s", flush=True)
            if status.startswith("failed"):
                failed.append(job)
    if failed:
        raise SystemExit(f"Failed jobs: {failed}")


if __name__ == "__main__":
    main()

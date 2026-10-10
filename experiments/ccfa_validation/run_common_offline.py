"""Repeat offline throughput with one shared KV-admission rule."""

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
RUNS = Path(__file__).resolve().parent / "runs" / "offline_common"
VERSION = ".".join(map(str, gurobipy.gurobi.version()))


def valid(path: Path, scenario: str, method: str, seed: int) -> bool:
    if not path.is_file():
        return False
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return (result["scenario"] == scenario and result["method"] == method and
                result["seed"] == seed and result["admission_rule"] == "common" and
                result["warmup_s"] == 60 and result["measurement_s"] == 600 and
                result["gurobi_version"] == VERSION)
    except (OSError, ValueError, KeyError):
        return False


def execute(scenario: str, method: str, seed: int, python: Path) -> tuple[str, float]:
    target = RUNS / f"seed{seed}" / f"{scenario}_{method}.json"
    if valid(target, scenario, method, seed):
        return "skipped", 0.0
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".json.part")
    command = [str(python), "-u", "-m", "experiments.baseline_audit.offline_compare",
               "--scenario", scenario, "--method", method, "--seed", str(seed),
               "--warmup", "60", "--measurement", "600", "--admission", "common",
               "--output", str(partial)]
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"
    environment["MPLBACKEND"] = "Agg"
    started = time.monotonic()
    with target.with_suffix(".log").open("w", encoding="utf-8") as log:
        log.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        log.flush()
        process = subprocess.run(command, cwd=ROOT, env=environment,
                                 stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    if process.returncode != 0 or not partial.is_file():
        return f"failed (exit {process.returncode})", elapsed
    data = json.loads(partial.read_text(encoding="utf-8"))
    if not valid(partial, scenario, method, seed):
        return "failed (identity mismatch)", elapsed
    data["wall_time_s"] = elapsed
    partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, target)
    return "done", elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if gurobipy.gurobi.version()[0] != 13:
        parser.error(f"Gurobi 13 required; found {VERSION}")
    python = args.python.resolve()
    child = subprocess.check_output([str(python), "-c",
        "import gurobipy; print('.'.join(map(str, gurobipy.gurobi.version())))"],
        cwd=ROOT, text=True).strip()
    if child != VERSION:
        parser.error(f"Child Gurobi {child} differs from runner {VERSION}")
    selected = [(scenario, method, seed)
                for seed in args.seeds
                for scenario in ("single", "multi")
                for method in ("helix", "integrated")]
    pending = [(scenario, method, seed) for scenario, method, seed in selected
               if not valid(RUNS / f"seed{seed}" / f"{scenario}_{method}.json",
                            scenario, method, seed)]
    print(f"Selected {len(selected)}, complete {len(selected)-len(pending)}, pending {len(pending)}", flush=True)
    if args.dry_run:
        for job in pending:
            print(job)
        return
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute, *job, python): job for job in pending}
        for index, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            try:
                status, elapsed = future.result()
            except Exception as error:
                status, elapsed = f"failed ({type(error).__name__}: {error})", 0.0
            print(f"[{index}/{len(pending)}] {job}: {status}; {elapsed:.1f}s", flush=True)
            if status.startswith("failed"):
                failed.append(job)
    if failed:
        raise SystemExit(f"Failed jobs: {failed}")


if __name__ == "__main__":
    main()

"""Repeat fresh-process V3 and original Helix ILP planning on one host."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .worker import ROOT, sha256, write_json


HERE = Path(__file__).resolve().parent
CASES = ("C1_single", "C1_multi")


def environment() -> dict:
    import gurobipy as gp
    import psutil

    return {"utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(), "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "physical_cpus": psutil.cpu_count(logical=False),
            "ram_gib": round(psutil.virtual_memory().total / 2**30, 2),
            "python": sys.version,
            "gurobi_version": gp.gurobi.version(),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True,
                                       check=True).stdout.strip(),
            "v3_release_manifest_sha256": sha256(
                ROOT / "experiments/v3_release/manifest.json"),
            "runner_sha256": sha256(HERE / "run.py"),
            "worker_sha256": sha256(HERE / "worker.py")}


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def one(case: str, method: str, repetition: int, timeout_s: int,
        solver_budget_s: int | None = None,
        *, force: bool = False) -> dict:
    output = HERE / "runs" / case / method / f"rep{repetition}"
    result_file = output / "result.json"
    if result_file.exists() and not force:
        result = json.loads(result_file.read_text(encoding="utf-8"))
        if not method.startswith("helix_ilp_budget") or result.get("solver_budget_s") == solver_budget_s:
            result["repetition"] = repetition
            result["method"] = method
            for stream in ("stdout", "stderr"):
                stream_file = output / f"{stream}.txt"
                if stream_file.exists():
                    result[f"{stream}_sha256"] = sha256(stream_file)
            write_json(result_file, result)
            print(f"Reuse {case}/{method}/rep{repetition}", flush=True)
            return result
    output.mkdir(parents=True, exist_ok=True)
    worker_method = "helix_ilp_budgeted" if method.startswith(
        "helix_ilp_budget") else method
    command = [sys.executable, "-m", "experiments.v3_search_efficiency.worker",
               "--case", case, "--method", worker_method, "--output", str(output)]
    if method.startswith("helix_ilp_budget"):
        command.extend(["--solver-budget-s", str(solver_budget_s)])
    started = time.perf_counter()
    try:
        process = subprocess.run(command, cwd=ROOT, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace",
                                 timeout=timeout_s)
        stdout, stderr = process.stdout, process.stderr
        code = process.returncode
        status = "passed" if code == 0 else "failed"
    except subprocess.TimeoutExpired as error:
        stdout, stderr = _text(error.stdout), _text(error.stderr)
        code, status = None, "timeout"
    process_wall = time.perf_counter() - started
    (output / "stdout.txt").write_text(stdout, encoding="utf-8")
    (output / "stderr.txt").write_text(stderr, encoding="utf-8")
    if status == "passed" and result_file.exists():
        result = json.loads(result_file.read_text(encoding="utf-8"))
    else:
        result = {"status": status, "case": case, "method": method,
                  "solver_budget_s": solver_budget_s if method.startswith("helix_ilp_budget")
                  else None,
                  "return_code": code, "process_wall_s": process_wall,
                  "external_timeout_s": timeout_s,
                  "stdout_sha256": sha256(output / "stdout.txt"),
                  "stderr_sha256": sha256(output / "stderr.txt")}
        write_json(result_file, result)
    result["repetition"] = repetition
    result["method"] = method
    result["process_wall_s"] = process_wall
    result["external_timeout_s"] = timeout_s
    result["stdout_sha256"] = sha256(output / "stdout.txt")
    result["stderr_sha256"] = sha256(output / "stderr.txt")
    write_json(result_file, result)
    print(case, method, repetition, result["status"],
          round(result.get("total_wall_s", process_wall), 3), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-s", type=int, default=900,
                        help="External guard only; Helix's original solver policy remains unchanged")
    parser.add_argument("--helix-mode", choices=("original", "budgeted"),
                        default="budgeted")
    parser.add_argument("--solver-budget-s", type=int, default=120)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout_s < 1 or args.solver_budget_s < 1:
        parser.error("repeats, timeout and solver budget must be positive")
    manifest = environment()
    write_json(HERE / "environment.json", manifest)
    current = HERE / "index.json"
    rows = [row for row in json.loads(current.read_text(encoding="utf-8"))["trials"]
            if "repetition" in row] if current.exists() else []
    budget_label = ("helix_ilp_budgeted" if args.solver_budget_s == 120 else
                    f"helix_ilp_budget{args.solver_budget_s}")
    pair = ("v3", "helix_ilp" if args.helix_mode == "original" else budget_label)
    for case in args.cases:
        for repetition in range(args.repeats):
            # Interleave methods, while never running timed trials concurrently.
            for method in pair if repetition % 2 == 0 else pair[::-1]:
                result = one(case, method, repetition, args.timeout_s,
                             args.solver_budget_s, force=args.force)
                rows = [row for row in rows if not (
                    row["case"] == case and row["method"] == method and
                    row.get("repetition") == repetition)]
                rows.append(result)
                write_json(HERE / "index.json", {"environment": manifest,
                                                  "trials": rows})


if __name__ == "__main__":
    main()

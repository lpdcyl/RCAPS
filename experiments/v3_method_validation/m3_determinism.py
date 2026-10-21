"""Run one isolated T3 window twice to audit deterministic behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_release.verify import digest
from rcaps.v3_method import layout as v3_layout

from .crossover import ROOT, _physical
from .m3_state import VARIANTS


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs" / "m3_determinism"


def _write(path: Path, value: dict):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def run_attempt(attempt: int):
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise ValueError("T3 deterministic diagnosis requires PYTHONHASHSEED=0")
    if os.environ.get("MPLBACKEND") != "Agg":
        raise ValueError("T3 deterministic diagnosis requires MPLBACKEND=Agg")
    out = RUNS / f"attempt{attempt}"
    out.mkdir(parents=True, exist_ok=True)
    solution, cluster = v3_layout("single", ROOT)
    physical = _physical("single")
    adapter = HERE / "m3_state.py"
    expected = {
        "scenario": "single", "seed": 2, "offered_tokens_per_s": 700.0,
        "duration_s": 1800, "warmup_s": 0,
        "solution_sha256": digest(solution),
        "sim_cluster_sha256": digest(cluster),
        "physical_cluster_sha256": digest(physical),
        "evaluation_protocol": "fixed_window_no_tail_drain",
        "m3_state_variant": "observed_eft",
    }
    _write(out / "environment.json", {
        "PYTHONHASHSEED": os.environ["PYTHONHASHSEED"],
        "MPLBACKEND": os.environ["MPLBACKEND"],
        "python_version": sys.version.split()[0],
        "adapter_sha256_raw": digest(adapter),
        "adapter_sha256_lf": hashlib.sha256(
            adapter.read_bytes().replace(bytes([13, 10]), bytes([10]))).hexdigest(),
        "fixed_window_sha256": digest(ROOT / "benchmarks/fixed_window.py"),
        "expected": expected,
    })
    result_path = out / "observed_eft.json"
    failure_path = out / "observed_eft.failure.json"
    log_path = out / "observed_eft.log"
    if result_path.exists() or failure_path.exists() or log_path.exists():
        raise FileExistsError(f"Diagnostic attempt already exists: {out}")
    try:
        with log_path.open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            row = fixed_window_run(
                "single", "queue_dag", 700.0, 1800, 0, 2,
                solution, cluster, physical_cluster=physical,
                scheduler_factory=VARIANTS["observed_eft"], compact=True,
                record_query_samples=True)
            row.update(expected)
            row["adapter_sha256"] = digest(adapter)
            _write(result_path, row)
        print(f"attempt{attempt}: passed sha256={digest(result_path)}")
    except Exception as error:
        stack = traceback.format_exc()
        with log_path.open("a", encoding="utf-8") as log:
            log.write(stack)
        progress = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("progress:")]
        _write(failure_path, {"status": "failed", "error_type": type(error).__name__,
                              "error": str(error), "traceback": stack,
                              "last_progress": progress[-1] if progress else None,
                              "expected": expected})
        print(f"attempt{attempt}: failed {type(error).__name__}: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, choices=(1, 2), required=True)
    run_attempt(parser.parse_args().attempt)


if __name__ == "__main__":
    main()

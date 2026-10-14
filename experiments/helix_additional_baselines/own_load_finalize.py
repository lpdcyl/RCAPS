"""Wait for both development selections, then run formal windows and audit report.

This script is intentionally resumable. It never changes a selected load or fills
missing metrics. Search processes are launched separately with own_load_search.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from .own_load_search import GRIDS


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCENARIOS = ("single", "multi")
METHODS = {"helix", "swarm", "separate", "rcaps_v2"}
STATUS = HERE / "own_load_pipeline_status.json"
LOG = HERE / "own_load_pipeline.log"


def write_status(stage: str, **details: object) -> None:
    STATUS.write_text(json.dumps({"stage": stage, "details": details,
                                  "updated_utc_epoch_s": time.time()},
                                 indent=2) + "\n", encoding="utf-8")


def selections_ready() -> bool:
    for scenario in SCENARIOS:
        path = HERE / "own_load_development" / scenario / "selection.json"
        if not path.is_file():
            return False
        selection = json.loads(path.read_text(encoding="utf-8"))
        if set(selection["methods"]) != METHODS:
            return False
        if tuple(selection["grid"]) != GRIDS[scenario]:
            return False
        statuses = {method: choice["status"]
                    for method, choice in selection["methods"].items()}
        if not all(status in ("selected", "grid_ceiling", "no_grid_load_passed")
                   for status in statuses.values()):
            return False
    return True


def resume_extended_grids() -> None:
    """Resume only once the old-grid search has finished all methods."""
    terminal = {"selected", "grid_ceiling", "no_grid_load_passed"}
    for scenario in SCENARIOS:
        path = HERE / "own_load_development" / scenario / "selection.json"
        if not path.is_file():
            continue
        selection = json.loads(path.read_text(encoding="utf-8"))
        if tuple(selection["grid"]) == GRIDS[scenario]:
            continue
        methods = selection["methods"]
        if set(methods) != METHODS or not all(
                choice["status"] in terminal for choice in methods.values()):
            continue
        result = subprocess.run(
            [sys.executable, "-u", "-m",
             "experiments.helix_additional_baselines.own_load_search",
             "--scenario", scenario], cwd=ROOT, capture_output=True,
            text=True, check=False)
        with LOG.open("a", encoding="utf-8") as stream:
            stream.write(result.stdout + result.stderr)
        if result.returncode != 0:
            write_status("failed", reason=f"Extended search failed: {scenario}",
                         log=str(LOG))
            raise RuntimeError(f"Extended search failed: {scenario}")


def main() -> None:
    started = time.monotonic()
    write_status("waiting_for_development_selections")
    while not selections_ready():
        resume_extended_grids()
        if time.monotonic() - started > 8 * 3600:
            write_status("failed", reason="Development selection timeout")
            raise TimeoutError("Development selection timeout")
        time.sleep(30)
    write_status("formal_running")
    with LOG.open("a", encoding="utf-8") as stream:
        processes = {scenario: subprocess.Popen(
            [sys.executable, "-u", "-m",
             "experiments.helix_additional_baselines.own_load_formal",
             "--scenario", scenario],
            cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            for scenario in SCENARIOS}
        codes = {scenario: process.wait() for scenario, process in processes.items()}
        stream.write(f"Formal runner exit codes: {codes}\n")
    if any(code != 0 for code in codes.values()):
        write_status("failed", formal_exit_codes=codes, log=str(LOG))
        raise RuntimeError(f"Formal runner failed: {codes}")
    write_status("auditing")
    result = subprocess.run(
        [sys.executable, "-m",
         "experiments.helix_additional_baselines.summarize_own_load"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(result.stdout + result.stderr)
    if result.returncode != 0:
        write_status("failed", audit_exit_code=result.returncode, log=str(LOG))
        raise RuntimeError("Own-load audit failed; see pipeline log")
    write_status("complete", report=str(HERE / "OWN_LOAD_RESULTS_CN.md"))


if __name__ == "__main__":
    main()

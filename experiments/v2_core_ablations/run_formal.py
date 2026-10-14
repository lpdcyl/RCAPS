"""Run only the unreused V2 core-ablation formal windows."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from .report import HERE, ROOT, SEEDS, OFFERED, layout, record, same_trace
from .audit_layouts import audit as audit_layout


NEW = {
    "single": ("rcaps_v2_model_compute", "rcaps_v2_fixed_branches",
               "rcaps_v2_static_dag", "rcaps_v2_queue_dag"),
    "multi": ("rcaps_v2_model_compute", "rcaps_v2_model_static",
              "rcaps_v2_fixed_branches", "rcaps_v2_static_dag",
              "rcaps_v2_queue_dag"),
}


def audit_reuse(scenario: str) -> None:
    for method in (*NEW[scenario], "rcaps_v2", "rcaps_v2_fixed_structure",
                   "rcaps_v2_model_event", "rcaps_v2_model_static"):
        audit_layout(*layout(method, scenario), scenario)
    for seed in SEEDS:
        full, _ = record("rcaps_v2", scenario, seed)
        fixed, _ = record("rcaps_v2_fixed_structure", scenario, seed)
        same_trace(full, fixed)
    for method in ("rcaps_v2_model_event",):
        if layout(method, scenario) != layout("rcaps_v2", scenario):
            # Paths differ, but report.record checks the byte hashes.
            for seed in SEEDS:
                record(method, scenario, seed)
    if scenario == "single":
        # Static communication and compute-only select the same bytes here.
        from .report import digest
        left = layout("rcaps_v2_model_compute", scenario)
        right = layout("rcaps_v2_model_static", scenario)
        if tuple(map(digest, left)) != tuple(map(digest, right)):
            raise ValueError("Single-cluster modeling reuse is not byte identical")


def main(scenario: str) -> None:
    audit_reuse(scenario)
    output = HERE / "runs"
    log = HERE / f"formal_{scenario}.log"
    methods = NEW[scenario]
    command = [sys.executable, "-u", "-m", "benchmarks.run",
               "--methods", *methods, "--scenarios", scenario,
               "--seeds", *(str(seed) for seed in SEEDS),
               "--offered-single", str(OFFERED[scenario]),
               "--offered-multi", str(OFFERED[scenario]),
               "--duration", "1800", "--warmup", "0", "--workers", "2",
               "--results-dir", str(output)]
    started = time.perf_counter()
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    status = {"scenario": scenario, "methods": methods, "seeds": SEEDS,
              "offered_tokens_per_s": OFFERED[scenario], "duration_s": 1800,
              "warmup_s": 0, "command": command, "exit_code": result.returncode,
              "wall_s": time.perf_counter() - started,
              "log": str(log.relative_to(ROOT))}
    (HERE / f"formal_{scenario}_status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"{scenario} formal exit={result.returncode} wall={status['wall_s']:.1f}s",
          flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=NEW, required=True)
    main(parser.parse_args().scenario)

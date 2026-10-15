"""Development load sweep around each pool's 1800-second primary load."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .prepare import HERE, ROOT


JOBS = {
    "C1": ((350.0, 525.0, 700.0),
           ("adaptive", "fixed_branches", "fixed_structure", "helix")),
    "C2": ((80.0, 120.0, 160.0), ("adaptive", "helix")),
    "C3": ((250.0, 400.0, 550.0),
           ("adaptive", "fixed_branches", "fixed_structure", "helix_petals")),
    "C4": ((70.0, 120.0, 170.0), ("adaptive", "helix_petals")),
    "C5": ((300.0, 500.0, 700.0),
           ("adaptive", "fixed_branches", "fixed_structure", "helix_petals")),
}


def one(case: str, offered: float, method: str) -> tuple[str, float, str, int]:
    log = HERE / "sensitivity_logs" / case / f"load{offered:g}" / f"{method}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "-m",
               "experiments.v2_resource_generalization.run_one",
               "--case", case, "--method", method, "--offered", str(offered),
               "--duration", "600", "--seed", "100"]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["MPLBACKEND"] = "Agg"
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    return case, offered, method, result.returncode


if __name__ == "__main__":
    jobs = [(case, offered, method)
            for case, (loads, methods) in JOBS.items()
            for offered in loads for method in methods]
    failures = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, *job) for job in jobs]):
            case, offered, method, code = future.result()
            print(f"{case} load={offered:g} {method} exit={code}", flush=True)
            if code:
                failures.append((case, offered, method))
    if failures:
        print(f"Incomplete development windows: {failures}", flush=True)

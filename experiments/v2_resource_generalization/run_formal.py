"""Run the remaining paired 1800-second resource-pool windows."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .prepare import HERE, ROOT


JOBS = {
    "C3": (400.0, ("adaptive", "fixed_branches", "fixed_structure", "helix_petals")),
    "C4": (120.0, ("adaptive", "helix_petals")),
    "C5": (500.0, ("adaptive", "fixed_branches", "fixed_structure", "helix_petals")),
}


def one(case: str, offered: float, method: str, seed: int) -> tuple[str, str, int, int]:
    log = HERE / "logs" / case / f"seed{seed}" / f"{method}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "-m",
               "experiments.v2_resource_generalization.run_one",
               "--case", case, "--method", method, "--offered", str(offered),
               "--duration", "1800", "--seed", str(seed)]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["MPLBACKEND"] = "Agg"
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    return case, method, seed, result.returncode


if __name__ == "__main__":
    jobs = [(case, offered, method, seed)
            for case, (offered, methods) in JOBS.items()
            for seed in (0, 1, 2) for method in methods]
    failed = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, *job) for job in jobs]):
            case, method, seed, code = future.result()
            print(f"{case} seed={seed} {method} exit={code}", flush=True)
            if code:
                failed.append((case, method, seed))
    if failed:
        raise SystemExit(f"Failed windows: {failed}")

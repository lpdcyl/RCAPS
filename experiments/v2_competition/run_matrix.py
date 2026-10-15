"""Run the two missing loads for six frozen diagnostic layouts."""

from __future__ import annotations

import os
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from .run_one import HERE, ROOT, candidates


def one(candidate: str, offered: float, seed: int) -> tuple[str, float, int]:
    log = HERE / "logs" / f"load{offered:g}" / f"{candidate}_seed{seed}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "-m", "experiments.v2_competition.run_one",
               "--candidate", candidate, "--offered", str(offered), "--seed", str(seed)]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["MPLBACKEND"] = "Agg"
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    return candidate, offered, result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=100)
    seed = parser.parse_args().seed
    jobs = [(candidate, offered, seed) for offered in (350.0, 525.0)
            for candidate in candidates()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, *job) for job in jobs]
        for future in as_completed(futures):
            candidate, offered, code = future.result()
            print(f"{candidate} load={offered:g} exit={code}", flush=True)
            if code:
                raise RuntimeError("A diagnostic run failed; inspect logs")

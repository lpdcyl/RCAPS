"""Run independent structure-ablation cells with bounded concurrency."""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from experiments.structure_ablation_2026.run import ARMS, HERE, LOADS


ROOT = HERE.parents[1]


def launch(scenario: str, seed: int, arm: str, offered: float,
           output_root: str) -> tuple[str, int]:
    name = f"{scenario}_seed{seed}_{arm}"
    if offered != LOADS[scenario]:
        name += f"_load{offered:g}"
    log = HERE / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", "-m",
               "experiments.structure_ablation_2026.run",
               "--scenario", scenario, "--seed", str(seed), "--arm", arm,
               "--offered", str(offered), "--output-root", output_root]
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    return name, completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--scenarios", nargs="+", choices=LOADS,
                        default=list(LOADS))
    parser.add_argument("--seeds", nargs="+", type=int, choices=(0, 1, 2),
                        default=[0, 1, 2])
    parser.add_argument("--arms", nargs="+",
                        choices=sorted(set().union(*map(set, ARMS.values()))),
                        default=None)
    parser.add_argument("--single-load", type=float, default=LOADS["single"])
    parser.add_argument("--multi-load", type=float, default=LOADS["multi"])
    parser.add_argument("--output-root", default=str(HERE / "runs70b"))
    args = parser.parse_args()
    selected = {scenario: tuple(arm for arm in ARMS[scenario]
                                if arm in (args.arms or [item for item in ARMS[scenario]
                                                      if item != "s2_prefix12"]))
                for scenario in args.scenarios}
    jobs = [(scenario, seed, arm,
             args.single_load if scenario == "single" else args.multi_load,
             args.output_root)
            for scenario in args.scenarios for seed in args.seeds
            for arm in selected[scenario]]
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(launch, *job) for job in jobs]
        for future in as_completed(futures):
            name, code = future.result()
            print(f"{name}: {'done' if code == 0 else f'FAILED {code}'}", flush=True)
            if code:
                failed.append(name)
    if failed:
        raise SystemExit("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()

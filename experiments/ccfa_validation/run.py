"""Run the targeted load, WAN-RTT, and scheduler-overhead experiments."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import gurobipy

from .prepare_network import OUT as NETWORK_LAYOUTS, prepare


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
VERSION = ".".join(map(str, gurobipy.gurobi.version()))
PAPER_LOAD = {"single": 700, "multi": 320}
HELIX = {
    "single": ROOT / "artifact_evaluation/single_cluster/layout_llama70b/ilp",
    "multi": ROOT / "artifact_evaluation/distributed_clusters/layout_llama70b/ilp",
}
GREEN = {
    "single": ROOT / "experiments/critical_graph/runs/single_final",
    "multi": ROOT / "experiments/critical_graph/runs/multi_final",
}


@dataclass(frozen=True)
class Job:
    group: str
    setting: str
    scenario: str
    method: str
    seed: int
    offered: int

    @property
    def output(self) -> Path:
        return RUNS / self.group / self.setting / f"seed{self.seed}" / f"{self.scenario}_{self.method}.json"

    @property
    def layout(self) -> Path:
        if self.group == "network":
            return NETWORK_LAYOUTS / self.setting / self.method
        return HELIX[self.scenario] if self.method == "helix" else GREEN[self.scenario]


def jobs(groups: list[str], seeds: list[int]) -> list[Job]:
    result = []
    for group in groups:
        if group == "load":
            settings = (("low", 0.7),)
            scenarios = ("single", "multi")
        elif group == "load_upper":
            settings = (("high", 1.1),)
            scenarios = ("single", "multi")
        elif group == "network":
            settings = (("rtt_0p5x", 1.0), ("rtt_2x", 1.0))
            scenarios = ("multi",)
        else:
            settings = (("official", 1.0),)
            scenarios = ("single", "multi")
        for setting, multiplier in settings:
            for scenario in scenarios:
                for method in ("helix", "green"):
                    for seed in seeds if group != "overhead" else seeds[:1]:
                        result.append(Job(group, setting, scenario, method, seed,
                                          round(PAPER_LOAD[scenario] * multiplier)))
    return result


def complete(job: Job) -> bool:
    if not job.output.is_file():
        return False
    try:
        record = json.loads(job.output.read_text(encoding="utf-8"))
        return (record["scenario"] == job.scenario and record["seed"] == job.seed and
                record["method"] == ("helix" if job.method == "helix" else "queue_dag") and
                record["offered_tokens_per_s"] == job.offered and
                record["duration_s"] == 1800 and record["warmup_s"] == 0 and
                record["gurobi_version"] == VERSION and
                ("scheduler_call_profile" in record) == (job.group == "overhead") and
                ("physical_cluster_sha256" in record) == (job.group == "network"))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def execute(job: Job, python: Path) -> tuple[str, float]:
    if complete(job):
        return "skipped", 0.0
    layout = job.layout
    solution = layout / ("ilp_sol.ini" if job.method == "helix" else "solution.ini")
    cluster = layout / "simulator_cluster.ini"
    if not solution.is_file() or not cluster.is_file():
        raise FileNotFoundError(layout)
    target = job.output
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".json.part")
    module = ("experiments.critical_graph.fixed_window" if job.method == "helix"
              else "experiments.queue_dag.evaluate")
    command = [str(python), "-u", "-m", module,
               "--scenario", job.scenario, "--solution", str(solution),
               "--sim-cluster", str(cluster), "--offered", str(job.offered),
               "--duration", "1800", "--warmup", "0", "--seed", str(job.seed),
               "--compact", "--output", str(partial)]
    if job.method == "helix":
        command += ["--method", "helix"]
    else:
        command += ["--policy", "final"]
    if job.group == "network":
        command += ["--physical-cluster",
                    str(NETWORK_LAYOUTS / job.setting / "physical_cluster.ini")]
    if job.group == "overhead":
        command += ["--profile-scheduler"]
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"
    environment["MPLBACKEND"] = "Agg"
    started = time.monotonic()
    with target.with_suffix(".log").open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, env=environment,
                                stdout=stream, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    if result.returncode != 0 or not partial.is_file():
        return f"failed (exit {result.returncode})", elapsed
    record = json.loads(partial.read_text(encoding="utf-8"))
    if record["seed"] != job.seed or record["scenario"] != job.scenario:
        return "failed (identity mismatch)", elapsed
    record["gurobi_version"] = VERSION
    record["validation_group"] = job.group
    record["validation_setting"] = job.setting
    record["wall_time_s"] = elapsed
    partial.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, target)
    return "done", elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", nargs="+",
                        choices=("load", "load_upper", "network", "overhead"),
                        default=["load", "load_upper", "network", "overhead"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if gurobipy.gurobi.version()[0] != 13:
        parser.error(f"Gurobi 13 required, found {VERSION}")
    python = args.python.resolve()
    child_version = subprocess.check_output([str(python), "-c",
        "import gurobipy; print('.'.join(map(str, gurobipy.gurobi.version())))"],
        cwd=ROOT, text=True).strip()
    if child_version != VERSION:
        parser.error(f"Child Gurobi {child_version} differs from runner {VERSION}")
    if "network" in args.groups and not args.dry_run:
        for factor in (0.5, 2.0):
            prepare(factor)
    selected = jobs(args.groups, args.seeds)
    pending = [job for job in selected if not complete(job)]
    print(f"Selected {len(selected)}, complete {len(selected)-len(pending)}, pending {len(pending)}", flush=True)
    if args.dry_run:
        for job in pending:
            print(job.output.relative_to(HERE))
        return
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute, job, python): job for job in pending}
        for index, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            try:
                status, elapsed = future.result()
            except Exception as error:
                status, elapsed = f"failed ({type(error).__name__}: {error})", 0.0
            print(f"[{index}/{len(pending)}] {job.group}/{job.setting} "
                  f"{job.scenario}/{job.method}/seed{job.seed}: {status}; {elapsed:.1f}s",
                  flush=True)
            if status.startswith("failed"):
                failures.append(str(job.output))
    if failures:
        raise SystemExit(f"Failed runs: {failures}")


if __name__ == "__main__":
    main()

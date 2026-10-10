"""Run the current paper experiments with independently labeled seeds.

Each simulation is a separate process. Successful results are written atomically,
so an interrupted batch can be resumed without replacing completed runs.
"""

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


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
GUROBI_VERSION = ".".join(map(str, gurobipy.gurobi.version()))
PAPER_LOAD = {"single": 700, "multi": 320}
DEV_LOAD = {"single": 400, "multi": 160}

LAYOUTS = {
    "single": {
        "paper_helix": "artifact_evaluation/single_cluster/layout_llama70b/ilp",
        "dev_helix": "examples/simulation/layouts/ilp",
        "final": "experiments/critical_graph/runs/single_final",
        "before": "experiments/critical_graph/runs/single",
        "model_after": "experiments/critical_graph/runs/single_sharedpush",
    },
    "multi": {
        "paper_helix": "artifact_evaluation/distributed_clusters/layout_llama70b/ilp",
        "dev_helix": "artifact_evaluation/distributed_clusters/layout_llama70b/ilp",
        "final": "experiments/critical_graph/runs/multi_final",
        "before": "experiments/critical_graph/runs/multi_coarse",
        "model_after": "experiments/critical_graph/runs/multi",
    },
}


@dataclass(frozen=True)
class Job:
    seed: int
    scenario: str
    name: str
    method: str
    layout: str
    offered: int
    duration: int
    warmup: int
    profile: bool = False
    policy: str = "final"

    @property
    def output(self) -> Path:
        return RUNS / f"seed{self.seed}" / self.scenario / f"{self.name}.json"


def jobs(seeds: list[int], scenarios: list[str], groups: list[str]) -> list[Job]:
    result = []
    for seed in seeds:
        for scenario in scenarios:
            paper = PAPER_LOAD[scenario]
            dev = DEV_LOAD[scenario]
            if "paper" in groups:
                result += [
                    Job(seed, scenario, "paper_helix", "helix", "paper_helix", paper, 1800, 0),
                    Job(seed, scenario, "paper_integrated", "queue_dag", "final", paper, 1800, 0),
                ]
            if "paper_placement" in groups:
                result.append(Job(seed, scenario, "paper_scheduler_helix", "helix",
                                  "final", paper, 1800, 0))
            if "dev" in groups:
                result += [
                    Job(seed, scenario, "dev_helix", "helix", "dev_helix", dev, 1980, 180),
                    Job(seed, scenario, "dev_integrated", "queue_dag", "final", dev, 1980, 180),
                    Job(seed, scenario, "dev_scheduler_helix", "helix", "final", dev, 1980, 180),
                    Job(seed, scenario, "dev_placement_helix_layout", "graph", "dev_helix", dev, 1980, 180),
                    Job(seed, scenario, "dev_placement_final_layout", "graph", "final", dev, 1980, 180),
                    Job(seed, scenario, "dev_ablation_before", "graph", "before", dev, 1980, 180),
                ]
            if "model" in groups:
                result += [
                    Job(seed, scenario, "model_profile", "graph", "before", dev, 300, 60, True),
                    Job(seed, scenario, "model_before", "graph", "before", dev, 600, 180),
                    Job(seed, scenario, "model_after", "graph", "model_after", dev, 600, 180),
                ]
            if "model_refined" in groups and scenario == "multi":
                result.append(Job(seed, scenario, "model_profile_refined", "graph",
                                  "model_after", dev, 300, 60, True))
            if "scheduler_ablation" in groups:
                result.append(Job(seed, scenario, "dev_scheduler_serial", "queue_dag",
                                  "final", dev, 1980, 180, policy="workload_serial"))
                if scenario == "multi":
                    result.append(Job(seed, scenario, "dev_scheduler_coalesced", "queue_dag",
                                      "final", dev, 1980, 180, policy="coalesced"))
    return result


def layout_files(job: Job) -> tuple[Path, Path]:
    base = ROOT / LAYOUTS[job.scenario][job.layout]
    solution = base / ("ilp_sol.ini" if job.layout in ("paper_helix", "dev_helix") else "solution.ini")
    cluster = base / "simulator_cluster.ini"
    if not solution.is_file() or not cluster.is_file():
        raise FileNotFoundError(f"Missing layout for {job}: {solution}, {cluster}")
    return solution, cluster


def valid_existing(job: Job) -> bool:
    if not job.output.is_file():
        return False
    try:
        data = json.loads(job.output.read_text(encoding="utf-8"))
        return all((
            data["seed"] == job.seed,
            data["scenario"] == job.scenario,
            data["method"] == job.method,
            data["offered_tokens_per_s"] == job.offered,
            data["duration_s"] == job.duration,
            data["warmup_s"] == job.warmup,
            bool("gpu_busy_fraction" in data) == job.profile,
            (data.get("routing_policy") == job.policy if job.method == "queue_dag" else True),
            data.get("gurobi_version") == GUROBI_VERSION,
            "trace_sha256" in data,
        ))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def execute(job: Job, python: Path) -> tuple[Job, str, float]:
    if valid_existing(job):
        return job, "skipped", 0.0
    solution, cluster = layout_files(job)
    output = job.output
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".json.part")
    log = output.with_suffix(".log")
    module = ("experiments.queue_dag.evaluate" if job.method == "queue_dag"
              else "experiments.critical_graph.fixed_window")
    command = [str(python), "-u", "-m", module,
               "--scenario", job.scenario, "--solution", str(solution),
               "--sim-cluster", str(cluster), "--offered", str(job.offered),
               "--duration", str(job.duration), "--warmup", str(job.warmup),
               "--seed", str(job.seed), "--output", str(partial), "--compact"]
    if job.method == "queue_dag":
        command += ["--policy", job.policy]
    else:
        command += ["--method", job.method]
    if job.profile:
        command += ["--profile-resources"]
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"
    environment["MPLBACKEND"] = "Agg"
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
        stream.flush()
        finished = subprocess.run(command, cwd=ROOT, env=environment,
                                  stdout=stream, stderr=subprocess.STDOUT,
                                  check=False)
    elapsed = time.monotonic() - started
    if finished.returncode != 0:
        return job, f"failed (exit {finished.returncode})", elapsed
    if not partial.is_file():
        return job, "failed (no JSON output)", elapsed
    # Validate before committing, using the same protocol check as resumption.
    data = json.loads(partial.read_text(encoding="utf-8"))
    if data["seed"] != job.seed or data["scenario"] != job.scenario:
        return job, "failed (output identity mismatch)", elapsed
    data["gurobi_version"] = GUROBI_VERSION
    partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, output)
    return job, "done", elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--scenarios", nargs="+", choices=("single", "multi"),
                        default=["single", "multi"])
    parser.add_argument("--groups", nargs="+",
                        choices=("paper", "paper_placement", "dev", "model", "model_refined",
                                 "scheduler_ablation"),
                        default=["paper", "dev", "model", "model_refined",
                                 "scheduler_ablation"])
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if gurobipy.gurobi.version()[0] != 13:
        parser.error(f"This three-seed batch requires Gurobi 13; found {GUROBI_VERSION}")
    child_version = subprocess.check_output(
        [str(args.python), "-c",
         "import gurobipy; print('.'.join(map(str, gurobipy.gurobi.version())))"],
        cwd=ROOT, text=True).strip()
    if child_version != GUROBI_VERSION:
        parser.error(f"Runner uses Gurobi {GUROBI_VERSION}, child uses {child_version}")
    selected = jobs(args.seeds, args.scenarios, args.groups)
    pending = [job for job in selected if not valid_existing(job)]
    print(f"Selected {len(selected)} runs; completed {len(selected) - len(pending)}; pending {len(pending)}.", flush=True)
    for job in selected:
        layout_files(job)
    if args.dry_run:
        for job in pending:
            print(job.output.relative_to(HERE), flush=True)
        return
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute, job, args.python): job for job in pending}
        for index, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            try:
                _, status, elapsed = future.result()
            except Exception as error:
                status, elapsed = f"failed ({type(error).__name__}: {error})", 0.0
            print(f"[{index}/{len(pending)}] seed={job.seed} {job.scenario} "
                  f"{job.name}: {status}; {elapsed:.1f}s", flush=True)
            if status.startswith("failed"):
                failures.append(str(job.output))
    if failures:
        raise SystemExit(f"{len(failures)} run(s) failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()

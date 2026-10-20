"""Run pre-registered dynamic-bottleneck counterfactuals for V3.

Usage:
  python -m experiments.v3_dynamic_bottleneck_counterfactuals.run --phase prepare
  python -m experiments.v3_dynamic_bottleneck_counterfactuals.run --phase smoke
  python -m experiments.v3_dynamic_bottleneck_counterfactuals.run --phase formal --workers 2
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import traceback
from configparser import ConfigParser
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.prepare import files
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from .scheduler import LengthOracleGraphDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SEEDS = (1, 2, 3)
RUNTIME = (
    "benchmarks/fixed_window.py",
    "benchmarks/resource_profile.py",
    "rcaps/v3/scheduler.py",
    "rcaps/v3/routing.py",
    "rcaps/v3/queue_cost.py",
    "rcaps/v3/online_scheduler.py",
    "experiments/v3_dynamic_bottleneck_counterfactuals/scheduler.py",
    "experiments/v3_dynamic_bottleneck_counterfactuals/run.py",
)
FORMAL_DURATION_S = 600


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def branch_layout(case: str, variant: str) -> tuple[Path, Path, Path, str]:
    physical, _, scenario = files(case)
    root = ROOT / "experiments/v3_m2_branch_parallelism/layouts" / case / variant
    return physical, root / "solution.ini", root / "simulator_cluster.ini", scenario


def v3_layout(topology: str) -> tuple[Path, Path, Path, str]:
    case = "C1_multi" if topology == "multi" else "C1_single"
    physical, _, scenario = files(case)
    root = ROOT / "rcaps/v3_layouts" / topology
    return physical, root / "solution.ini", root / "simulator_cluster.ini", scenario


def layout_for(group: str, treatment: str) -> tuple[Path, Path, Path, str]:
    if group == "kv":
        return branch_layout("C1_single", "k1")
    if group == "network":
        return branch_layout("C1_multi", treatment.split("_")[0])
    if group == "oracle":
        return v3_layout("multi")
    raise ValueError(f"Unknown group: {group}")


def mutate_config(source: Path, destination: Path, *, kv_multiplier: int = 1,
                  bandwidth_multiplier: int = 1) -> None:
    config = ConfigParser(interpolation=None)
    if not config.read(source):
        raise FileNotFoundError(source)
    if kv_multiplier != 1:
        for section in ast.literal_eval(config["ComputeNodes"]["names"]):
            capacity = int(config[section]["kv_cache_capacity"])
            config[section]["kv_cache_capacity"] = str(capacity * kv_multiplier)
    if bandwidth_multiplier != 1:
        for section in ast.literal_eval(config["Links"]["names"]):
            text = config[section]["bandwidth"]
            value, unit = text.split(" * ", maxsplit=1)
            config[section]["bandwidth"] = f"{float(value) * bandwidth_multiplier:g} * {unit}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        config.write(handle)


def derived_config(group: str, treatment: str, source: Path) -> Path:
    if treatment in {"base", "k1_base", "k3_base", "fixed", "length_oracle"}:
        return source
    destination = HERE / "derived_configs" / group / f"{treatment}.ini"
    if treatment == "kv2":
        mutate_config(source, destination, kv_multiplier=2)
    elif treatment.endswith("bw2"):
        mutate_config(source, destination, bandwidth_multiplier=2)
    elif treatment in {"k1_flat", "flat"}:
        # The trace, rather than the resource configuration, is changed.
        mutate_config(source, destination)
    else:
        raise ValueError(f"Unknown treatment: {treatment}")
    return destination


def raw_trace(load: float, duration: int, seed: int) -> list[tuple[float, int, int]]:
    feeder = OnlineRequestFeeder(cluster_token_throughput=load, start_time=0,
                                 duration=duration, seed=seed)
    return [(arrival, inputs, outputs) for arrival, inputs, outputs in feeder.trace]


def flat_trace(trace: list[tuple[float, int, int]], duration: int) -> list[tuple[float, int, int]]:
    if not trace:
        return []
    spacing = duration / len(trace)
    return [((index + 0.5) * spacing, inputs, outputs)
            for index, (_, inputs, outputs) in enumerate(trace)]


def jobs(phase: str) -> list[dict]:
    if phase == "smoke":
        return [
            {"group": "kv", "treatment": "base", "load": 700., "seed": 1,
             "trace_mode": "arrival_trace"},
            {"group": "kv", "treatment": "kv2", "load": 700., "seed": 1,
             "trace_mode": "arrival_trace"},
            {"group": "network", "treatment": "k1_base", "load": 320., "seed": 1,
             "trace_mode": "arrival_trace"},
            {"group": "network", "treatment": "k1_bw2", "load": 320., "seed": 1,
             "trace_mode": "arrival_trace"},
            {"group": "network", "treatment": "k1_flat", "load": 320., "seed": 1,
             "trace_mode": "flat_uniform"},
            {"group": "oracle", "treatment": "fixed", "load": 320., "seed": 1,
             "trace_mode": "arrival_trace"},
            {"group": "oracle", "treatment": "length_oracle", "load": 320., "seed": 1,
             "trace_mode": "arrival_trace"},
        ]
    result = []
    for load, seed_values in ((600., (4, 5, 6)), (1100., SEEDS)):
        for treatment in ("base", "kv2"):
            result.extend({"group": "kv", "treatment": treatment, "load": load,
                           "seed": seed, "trace_mode": "arrival_trace"}
                          for seed in seed_values)
    for treatment in ("k1_base", "k1_bw2", "k1_flat", "k3_base", "k3_bw2"):
        mode = "flat_uniform" if treatment.endswith("flat") else "arrival_trace"
        result.extend({"group": "network", "treatment": treatment, "load": 320.,
                       "seed": seed, "trace_mode": mode} for seed in SEEDS)
    for treatment in ("fixed", "length_oracle"):
        result.extend({"group": "oracle", "treatment": treatment, "load": 320.,
                       "seed": seed, "trace_mode": "arrival_trace"} for seed in SEEDS)
    return result


def scheduler_for(group: str, treatment: str):
    return LengthOracleGraphDagScheduler if group == "oracle" and treatment == "length_oracle" \
        else GraphModeledQueueAwareDagScheduler


def prepare() -> dict:
    plan = {
        "protocol": "fixed_window_no_tail_drain",
        "formal_duration_s": FORMAL_DURATION_S,
        "seeds": list(SEEDS),
        "runtime_sha256": {item: digest(ROOT / item) for item in RUNTIME},
        "design": {
            "kv": "C1_single/k1; multiply every deployed node KV capacity by 2; GPU, links, layout, and trace fixed.",
            "network": "C1_multi k1/k3; multiply every deployed link bandwidth by 2, or replace the same seed's arrival times with uniform spacing while retaining request sizes and order.",
            "oracle": "Frozen V3 multi layout; Decode remains on the prompt path. The oracle observes true remaining output lengths of currently live sessions, but no future arrivals.",
        },
        "layouts": {},
    }
    for group, treatment in (("kv", "base"), ("network", "k1_base"),
                             ("network", "k3_base"), ("oracle", "fixed"),
                             ("oracle", "length_oracle")):
        physical, solution, source, scenario = layout_for(group, treatment)
        if not solution.exists() or not source.exists():
            raise FileNotFoundError(f"Missing prepared layout: {solution.parent}")
        destination = derived_config(group, treatment, source)
        plan["layouts"][f"{group}/{treatment}"] = {
            "scenario": scenario, "physical": rel(physical),
            "physical_sha256": digest(physical), "solution": rel(solution),
            "solution_sha256": digest(solution), "source_sim_cluster": rel(source),
            "source_sim_cluster_sha256": digest(source),
            "sim_cluster": rel(destination), "sim_cluster_sha256": digest(destination),
        }
    for group, treatment, source_treatment in (("kv", "kv2", "base"),
                                                 ("network", "k1_bw2", "k1_base"),
                                                 ("network", "k1_flat", "k1_base"),
                                                 ("network", "k3_bw2", "k3_base")):
        _, _, source, _ = layout_for(group, source_treatment)
        destination = derived_config(group, treatment, source)
        plan["layouts"][f"{group}/{treatment}"] = {
            "sim_cluster": rel(destination), "sim_cluster_sha256": digest(destination),
            "resource_change": ("kv_capacity_x2" if treatment == "kv2" else
                                "all_deployed_link_bandwidth_x2" if treatment.endswith("bw2") else
                                "none_trace_only"),
        }
    write(HERE / "plan.json", plan)
    return plan


def run_one(job: dict, phase: str) -> str:
    plan = read(HERE / "plan.json")
    if plan["runtime_sha256"] != {item: digest(ROOT / item) for item in RUNTIME}:
        raise ValueError("Runtime changed after plan freeze; rerun --phase prepare")
    group, treatment = job["group"], job["treatment"]
    physical, solution, source, scenario = layout_for(group, treatment)
    sim_cluster = derived_config(group, treatment, source)
    expected = plan["layouts"].get(f"{group}/{treatment}", {})
    if expected.get("sim_cluster_sha256") != digest(sim_cluster):
        raise ValueError("Derived simulator resource file drifted")
    duration = 60 if phase == "smoke" else FORMAL_DURATION_S
    trace = raw_trace(job["load"], duration, job["seed"])
    if job["trace_mode"] == "flat_uniform":
        trace = flat_trace(trace, duration)
    output = HERE / "runs" / phase / group / treatment / (
        f"load{job['load']:g}_seed{job['seed']}.json")
    identity = {
        **job, "phase": phase, "duration_s": duration,
        "solution_sha256": digest(solution), "sim_cluster_sha256": digest(sim_cluster),
        "physical_sha256": digest(physical),
        "scheduler": scheduler_for(group, treatment).__name__,
        "runtime_sha256": plan["runtime_sha256"],
    }
    if output.exists():
        row = read(output)
        if all(row.get(key) == value for key, value in identity.items()):
            return rel(output)
        raise ValueError(f"Existing result identity changed: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", job["load"], duration, 0, job["seed"],
                solution, sim_cluster, profile_resources=False, compact=True,
                record_query_samples=True, physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=scheduler_for(group, treatment), trace_override=trace)
            row.update(identity)
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Incomplete request-level samples")
            write(output, row)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return rel(output)


def run_phase(phase: str, workers: int, groups: tuple[str, ...] = ()) -> dict:
    if phase == "formal600":
        smoke = read(HERE / "smoke_index.json")
        if smoke["failures"]:
            raise ValueError("Smoke gate failed")
    scheduled = jobs(phase)
    if groups:
        scheduled = [job for job in scheduled if job["group"] in groups]
    index = {"phase": phase, "jobs": {}, "failures": {}}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, job, phase): job for job in scheduled}
        for future in as_completed(futures):
            job = futures[future]
            key = f"{job['group']}/{job['treatment']}/load{job['load']:g}/seed{job['seed']}"
            try:
                path = ROOT / future.result()
                row = read(path)
                index["jobs"][key] = {"status": "passed", "source": rel(path),
                                      "sha256": digest(path), "trace_sha256": row["trace_sha256"]}
                print("PASS", key, flush=True)
            except Exception as exc:
                index["jobs"][key] = {"status": "failed", "error": repr(exc)}
                index["failures"][key] = repr(exc)
                print("FAIL", key, repr(exc), flush=True)
            write(HERE / f"{phase}_index.json", index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "smoke", "formal600"), required=True)
    parser.add_argument("--group", choices=("kv", "network", "oracle"), action="append")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.phase == "prepare":
        print(json.dumps(prepare(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run_phase(args.phase, args.workers, tuple(args.group or ()))["failures"], indent=2))


if __name__ == "__main__":
    main()

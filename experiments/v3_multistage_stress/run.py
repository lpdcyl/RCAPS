"""Run paired synthetic layer-hotspot windows without changing frozen V3."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from benchmarks import fixed_window
from benchmarks.compare import MATCH_FIELDS, common_cohort
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from rcaps.v3.placement import digest, validate
from rcaps.v3.resource_graph import from_simulator
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from .plan import SCENES, write_json
from .pool import HERE, PHYSICAL, ROOT, prepare


MAIN_LOADS = (150, 300, 450)
SEEDS = (0, 1, 2)
VARIANTS = ("uniform_single", "uniform_multi", "aware_single", "aware_multi",
            "witness")


def matrix() -> list[tuple[str, int, bool, int, str]]:
    jobs = []
    for scene in SCENES:
        loads = MAIN_LOADS if scene == "mid_x4" else (300,)
        for offered in loads:
            for seed in SEEDS:
                for variant in VARIANTS:
                    if variant == "witness" and offered != 300:
                        continue
                    jobs.append((scene, offered, False, seed, variant))
    for seed in SEEDS:
        for variant in VARIANTS:
            jobs.append(("mid_x4", 300, True, seed, variant))
    return jobs


def placement_path(scene: str, variant: str) -> Path:
    if variant == "witness":
        return HERE / "layouts/witness_1_4_1"
    information, mode = variant.split("_", 1)
    if information == "aware":
        information = "layer_aware"
    if information == "uniform":
        scene = "mid_x1"
    return HERE / "layouts" / information / scene / mode


def trace(offered: int, seed: int, burst: bool) -> list[tuple[float, int, int]]:
    base = OnlineRequestFeeder(cluster_token_throughput=offered,
                               start_time=0, duration=1800, seed=seed).trace
    def warp(t: float) -> float:
        if t < 480:
            return t / .8
        if t < 1080:
            return 600 + (t - 480) / 2
        return 900 + (t - 1080) / .8
    values = [(warp(t) if burst else t, i, o) for t, i, o in base]
    if any(not 0 <= t < 1800 for t, _, _ in values):
        raise ValueError("Arrival outside formal window")
    return values


def trace_digest(values: list[tuple[float, int, int]]) -> str:
    payload = [(round(t, 9), i, o) for t, i, o in values]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def identity(scene: str, load: int, burst: bool, seed: int, variant: str,
             duration: int) -> dict:
    folder = placement_path(scene, variant)
    return {"scene": scene, "variant": variant, "seed": seed,
            "offered_tokens_per_s": float(load), "duration_s": duration,
            "warmup_s": 0, "burst": burst,
            "physical_sha256": digest(PHYSICAL),
            "solution_sha256": digest(folder / "solution.ini"),
            "sim_cluster_sha256": digest(folder / "simulator_cluster.ini"),
            "fixed_window_sha256": digest(ROOT / "benchmarks/fixed_window.py"),
            "cost_adapter_sha256": digest(HERE / "cost.py"),
            "execution_sha256": hashlib.sha256("".join(digest(ROOT / p) for p in (
                "rcaps/v3/resource_graph.py", "rcaps/v3/online_scheduler.py",
                "rcaps/v3/scheduler.py")).encode()).hexdigest(),
            "evaluation_protocol": "fixed_window_no_tail_drain",
            "query_samples_schema": 1}


def key(job: tuple[str, int, bool, int, str]) -> str:
    scene, load, burst, seed, variant = job
    return f"{scene}/{'burst' if burst else 'uniform'}/{load}/seed{seed}/{variant}"


def path_for(job: tuple[str, int, bool, int, str], duration: int) -> Path:
    scene, load, burst, seed, variant = job
    phase = "smoke" if duration == 60 else "formal"
    return (HERE / "runs" / phase / scene / ("burst" if burst else "uniform") /
            f"load{load}" / f"seed{seed}" / f"{variant}.json")


def _apply_layer_cost(simulator, solution: Path, interval: tuple[int, int],
                      multiplier: float) -> float:
    start = ORIGINAL_LAYOUT(simulator, solution)
    state = json.loads((solution.parent / "placement.json").read_text(
        encoding="utf-8"))["state"]
    expected_dag = validate(TopologyModel(PHYSICAL), state)["dag"]
    runtime_dag = from_simulator(simulator)
    runtime_edges = {((left - 2) if isinstance(left, int) else left,
                      (right - 2) if isinstance(right, int) else right)
                     for left, right in runtime_dag.edges}
    if runtime_edges != expected_dag.edge_set or \
            runtime_dag.path_count() != expected_dag.path_count():
        raise ValueError("M1 deployment and M3 runtime DAG differ")
    changed = 0
    seen = set()
    for node in simulator.name_2_compute_node.values():
        for layer in node.in_vram_model_layers.values():
            if not interval[0] <= layer.layer_id < interval[1]:
                continue
            if id(layer) in seen:
                continue
            seen.add(id(layer))
            layer.prompt_bs2time = {k: v * multiplier
                                    for k, v in layer.prompt_bs2time.items()}
            layer.decode_bs2time = {k: v * multiplier
                                    for k, v in layer.decode_bs2time.items()}
            changed += 1
    if changed == 0:
        raise ValueError("Synthetic hotspot reached no loaded layers")
    return start


ORIGINAL_LAYOUT = fixed_window.load_graph_layout


def execute(job: tuple[str, int, bool, int, str], duration: int) -> dict:
    scene, load, burst, seed, variant = job
    output = path_for(job, duration)
    expected = identity(scene, load, burst, seed, variant, duration)
    trace_values = trace(load, seed, burst) if duration == 1800 else None
    if output.is_file():
        row = json.loads(output.read_text(encoding="utf-8"))
        if any(row.get(field) != value for field, value in expected.items()):
            raise ValueError(f"Existing window differs: {output}")
        return {"status": "passed", "source": output.relative_to(ROOT).as_posix(),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "existing": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    log_file = output.with_suffix(".log")
    failure_file = output.with_suffix(".failure.json")
    interval, multiplier = SCENES[scene]
    folder = placement_path(scene, variant)
    model = TopologyModel(PHYSICAL)
    try:
        with log_file.open("w", encoding="utf-8") as log, \
                redirect_stdout(log), redirect_stderr(log), patch.object(
                    fixed_window, "load_graph_layout", lambda sim, sol: _apply_layer_cost(
                        sim, sol, interval, multiplier)):
            row = fixed_window.run(
                "single", "queue_dag", float(load), duration, 0, seed,
                folder / "solution.ini", folder / "simulator_cluster.ini",
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                compact=True, record_query_samples=True,
                physical_cluster=PHYSICAL, machine_counts=model.machine_counts,
                trace_override=trace_values, profile_resources=duration == 1800)
            row.update(expected)
            if trace_values is not None and row["trace_sha256"] != trace_digest(trace_values):
                raise ValueError("Stress trace digest differs from requested trace")
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Missing request-level samples")
            row["path_use"] = path_use(row, folder / "placement.json", model)
            write_json(output, row)
        failure_file.unlink(missing_ok=True)
        return {"status": "passed", "source": output.relative_to(ROOT).as_posix(),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"]}
    except Exception as error:
        with log_file.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        write_json(failure_file, {"error": repr(error), "identity": expected,
                                  "log": log_file.relative_to(ROOT).as_posix()})
        return {"status": "failed", "error": repr(error),
                "source": failure_file.relative_to(ROOT).as_posix(),
                "sha256": digest(failure_file)}


def path_use(row: dict, placement_file: Path, model: TopologyModel) -> dict:
    state = json.loads(placement_file.read_text(encoding="utf-8"))["state"]
    checked = validate(model, state)
    dag = checked["dag"]
    memberships = {}
    for level, segment in enumerate(state["segments"]):
        for branch, replica in enumerate(segment["replicas"]):
            for node in replica:
                memberships[node] = (level, branch)
    distinct = set()
    total = crossed = 0
    for encoded, count in row["route_counts"].items():
        nodes = tuple(int(token) - 2 for token in encoded.split("-"))
        edges = list(zip(("source", *nodes), (*nodes, "sink")))
        if any(edge not in dag.edge_set for edge in edges):
            raise ValueError(f"Executed path absent from deployment DAG: {encoded}")
        distinct.add(nodes)
        total += count
        seen = {}
        for node in nodes:
            level, branch = memberships[node]
            seen.setdefault(level, set()).add(branch)
        if any(len(branches) > 1 for branches in seen.values()):
            crossed += count
    return {"compatible_paths": dag.path_count(), "compatible_edges": len(dag.edges),
            "actual_paths": len(distinct), "routed_requests": total,
            "cross_replica_requests": crossed,
            "cross_replica_fraction": crossed / total if total else None}


def launch(phase: str, workers: int) -> None:
    prepare()
    manifest = json.loads((HERE / "plan_index.json").read_text(encoding="utf-8"))
    if manifest["physical_sha256"] != digest(PHYSICAL):
        raise ValueError("Stress physical pool changed after planning")
    duration = 60 if phase == "smoke" else 1800
    if phase == "formal":
        smoke = json.loads((HERE / "smoke_index.json").read_text(encoding="utf-8"))
        if any(item["status"] != "passed" for item in smoke["jobs"].values()):
            raise ValueError("Smoke gate has failures")
    jobs = matrix()
    if phase == "smoke":
        jobs = [(scene, 300, False, 100, variant) for scene in SCENES
                for variant in VARIANTS]
    index_file = HERE / f"{phase}_index.json"
    index = {"physical_sha256": digest(PHYSICAL), "duration_s": duration,
             "jobs": {}}
    # Deployment identity and trace define an identical execution; aliases reuse it.
    unique, aliases = {}, {}
    for job in jobs:
        scene, load, burst, seed, variant = job
        if not placement_path(scene, variant).joinpath("solution.ini").exists():
            raise FileNotFoundError(f"Missing placement for {key(job)}")
        match = (scene, load, burst, seed, duration,
                 digest(placement_path(scene, variant) / "solution.ini"),
                 digest(placement_path(scene, variant) / "simulator_cluster.ini"))
        if match in unique:
            aliases.setdefault(key(unique[match]), []).append(key(job))
        else:
            unique[match] = job
    write_json(index_file, index)
    print(f"{phase}: requested={len(jobs)}, distinct={len(unique)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(execute, job, duration): job for job in unique.values()}
        for future in as_completed(futures):
            job = futures[future]
            item = future.result()
            index["jobs"][key(job)] = item
            for alias in aliases.get(key(job), []):
                index["jobs"][alias] = {**item, "reused_from": key(job)}
            write_json(index_file, index)
            print(key(job), item["status"], flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    launch(args.phase, args.workers)


if __name__ == "__main__":
    main()

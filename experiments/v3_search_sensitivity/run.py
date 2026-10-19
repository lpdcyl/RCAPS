"""Audited online windows for distinct layouts from the V3 M2 sensitivity scan."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_release.verify import digest, snapshot
from rcaps.v3.placement import validate
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel

from .plan import CASES, HERE, ROOT, SETTINGS, files, label, write_json


LOADS = {"C1_single": (350, 700), "C1_multi": (160, 320)}
SEEDS = (0, 1, 2)
RELEASE = ROOT / "experiments/v3_release/manifest.json"
BENCHMARK = ROOT / "benchmarks/fixed_window.py"
HISTORY = ROOT / "experiments/v3_load_boundary"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def audit() -> dict:
    saved = read_json(RELEASE)
    if snapshot() != saved:
        raise ValueError("Frozen V3 release manifest changed")
    planning = read_json(HERE / "planning_index.json")
    if planning["release_manifest_sha256"] != digest(RELEASE) or \
            planning["search_sha256"] != digest(ROOT / "rcaps/v3/search.py") or \
            planning["placement_sha256"] != digest(ROOT / "rcaps/v3/placement.py"):
        raise ValueError("Planning inputs changed after search")
    groups = {}
    for case in CASES:
        physical, _, scenario = files(case)
        model = TopologyModel(physical)
        by_layout = {}
        for beam, budget in SETTINGS:
            name = label(beam, budget)
            item = planning["cases"][case][name]
            folder = HERE / "layouts" / case / name
            record = read_json(folder / "placement.json")
            if digest(folder / "placement.json") != item["placement_sha256"]:
                raise ValueError(f"Placement metadata changed: {case}/{name}")
            if digest(folder / "solution.ini") != item["solution_sha256"] or \
                    digest(folder / "simulator_cluster.ini") != item["sim_cluster_sha256"]:
                raise ValueError(f"Deployment changed: {case}/{name}")
            checked = validate(model, record["state"])
            if checked["dag"].path_count() != item["compatible_paths"] or \
                    len(checked["dag"].edges) != item["compatibility_edges"]:
                raise ValueError(f"DAG changed: {case}/{name}")
            pair = (item["solution_sha256"], item["sim_cluster_sha256"])
            by_layout.setdefault(pair, []).append(name)
        groups[case] = [
            {"canonical": names[0], "aliases": names,
             "solution_sha256": pair[0], "sim_cluster_sha256": pair[1]}
            for pair, names in by_layout.items()]
        released = saved["layouts"][scenario]
        baseline = planning["cases"][case][label(64, 500)]
        if baseline["solution_sha256"] != released["solution_sha256"] or \
                baseline["sim_cluster_sha256"] != released["sim_cluster_sha256"]:
            raise ValueError(f"Baseline differs from released V3: {case}")
    return {"release_manifest_sha256": digest(RELEASE),
            "benchmark_sha256": digest(BENCHMARK),
            "planning_index_sha256": digest(HERE / "planning_index.json"),
            "loads": LOADS, "seeds": SEEDS, "duration_s": 1800,
            "warmup_s": 0, "tail_drain": False, "groups": groups}


def identity(case: str, canonical: str, load: int, seed: int, duration: int) -> dict:
    physical, _, scenario = files(case)
    folder = HERE / "layouts" / case / canonical
    return {"scenario": scenario, "case": case, "layout": canonical,
            "seed": seed, "offered_tokens_per_s": float(load),
            "duration_s": duration, "warmup_s": 0,
            "evaluation_protocol": "fixed_window_no_tail_drain",
            "query_samples_schema": 1,
            "solution_sha256": digest(folder / "solution.ini"),
            "sim_cluster_sha256": digest(folder / "simulator_cluster.ini"),
            "physical_sha256": digest(physical),
            "benchmark_sha256": digest(BENCHMARK),
            "release_manifest_sha256": digest(RELEASE)}


def historical(case: str, load: int, seed: int, canonical: str) -> dict | None:
    if canonical != label(64, 500):
        return None
    scenario = "single" if case == "C1_single" else "multi"
    index = read_json(HISTORY / "index.json")
    history_audit = HISTORY / "audit.json"
    if index["audit_sha256"] != digest(history_audit):
        raise ValueError("Historical load-boundary audit changed")
    item = index["jobs"].get(f"{scenario}/{load}/seed{seed}/rcaps_v3")
    if not item or item["status"] not in ("passed", "reused"):
        return None
    source = ROOT / item["source"]
    if not source.is_file() or digest(source) != item["sha256"]:
        return None
    row = read_json(source)
    expected = identity(case, canonical, load, seed, 1800)
    for field in ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                  "warmup_s", "evaluation_protocol", "query_samples_schema",
                  "solution_sha256", "sim_cluster_sha256", "physical_sha256",
                  "benchmark_sha256"):
        if row.get(field) != expected[field]:
            return None
    if len(row.get("query_samples", {})) != row.get("arrivals") or \
            row.get("trace_sha256") != item["trace_sha256"]:
        return None
    if item["status"] == "reused" and row.get("release_manifest_sha256") != digest(RELEASE):
        return None
    return {"status": "reused", "source": relative(source),
            "sha256": digest(source), "trace_sha256": row["trace_sha256"],
            "identity": expected, "provenance": "v3_load_boundary"}


def route_audit(case: str, canonical: str, row: dict) -> dict:
    physical, _, _ = files(case)
    model = TopologyModel(physical)
    state = read_json(HERE / "layouts" / case / canonical / "placement.json")["state"]
    dag = validate(model, state)["dag"]
    used = 0
    for encoded, count in row.get("route_counts", {}).items():
        nodes = [int(part) - 2 for part in encoded.split("-")]
        edges = list(zip(("source", *nodes), (*nodes, "sink")))
        if any(edge not in dag.edge_set for edge in edges):
            raise ValueError(f"Runtime route not in M1 DAG: {encoded}")
        used += count
    if used == 0:
        raise ValueError("No requests were routed")
    return {"routed_requests": used, "actual_paths": len(row["route_counts"]),
            "compatible_paths": dag.path_count(), "compatible_edges": len(dag.edges)}


def result_path(case: str, canonical: str, load: int, seed: int,
                duration: int) -> Path:
    phase = "smoke" if duration == 60 else "formal"
    return HERE / "runs" / phase / case / canonical / f"load{load}" / f"seed{seed}.json"


def execute(case: str, canonical: str, load: int, seed: int,
            duration: int) -> dict:
    output = result_path(case, canonical, load, seed, duration)
    expected = identity(case, canonical, load, seed, duration)
    if output.is_file():
        row = read_json(output)
        if any(row.get(key) != value for key, value in expected.items()) or \
                len(row.get("query_samples", {})) != row.get("arrivals"):
            raise ValueError(f"Existing window has a different identity: {output}")
        route_audit(case, canonical, row)
        return {"status": "passed", "source": relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "identity": expected, "existing": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    log_file = output.with_suffix(".log")
    failure_file = output.with_suffix(".failure.json")
    physical, _, scenario = files(case)
    folder = HERE / "layouts" / case / canonical
    try:
        with log_file.open("w", encoding="utf-8") as log, \
                redirect_stdout(log), redirect_stderr(log):
            row = fixed_window_run(
                scenario, "queue_dag", float(load), duration, 0, seed,
                folder / "solution.ini", folder / "simulator_cluster.ini",
                physical_cluster=physical,
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                compact=True, record_query_samples=True,
                profile_resources=duration == 1800)
            row.update(expected)
            if len(row.get("query_samples", {})) != row.get("arrivals"):
                raise ValueError("Request samples incomplete")
            row["route_audit"] = route_audit(case, canonical, row)
            write_json(output, row)
        failure_file.unlink(missing_ok=True)
        return {"status": "passed", "source": relative(output),
                "sha256": digest(output), "trace_sha256": row["trace_sha256"],
                "identity": expected, "log": relative(log_file)}
    except Exception as error:
        with log_file.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        failure = {"status": "failed", "identity": expected,
                   "error": repr(error), "log": relative(log_file)}
        write_json(failure_file, failure)
        return {**failure, "source": relative(failure_file),
                "sha256": digest(failure_file)}


def run(phase: str, workers: int) -> None:
    protocol = audit()
    write_json(HERE / "audit.json", protocol)
    duration = 60 if phase == "smoke" else 1800
    if phase == "formal":
        smoke_index = read_json(HERE / "smoke_index.json")
        if smoke_index["audit_sha256"] != digest(HERE / "audit.json") or \
                any(item["status"] not in ("passed", "reused")
                    for item in smoke_index["jobs"].values()):
            raise ValueError("Smoke gate is incomplete or its audit changed")
    jobs = []
    index = {"audit_sha256": digest(HERE / "audit.json"), "jobs": {}}
    for case in CASES:
        groups = protocol["groups"][case]
        for group in groups:
            canonical = group["canonical"]
            loads = (LOADS[case][0],) if phase == "smoke" else LOADS[case]
            seeds = (100,) if phase == "smoke" else SEEDS
            for load in loads:
                for seed in seeds:
                    key = f"{case}/{canonical}/{load}/seed{seed}"
                    reused = (historical(case, load, seed, canonical)
                              if phase == "formal" else None)
                    if reused is not None:
                        index["jobs"][key] = reused
                    else:
                        jobs.append((case, canonical, load, seed, duration))
    write_json(HERE / f"{phase}_index.json", index)
    print(f"{phase}: reused={len(index['jobs'])}, new={len(jobs)}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(execute, *job): job for job in jobs}
        for future in as_completed(futures):
            case, canonical, load, seed, _ = futures[future]
            key = f"{case}/{canonical}/{load}/seed{seed}"
            try:
                index["jobs"][key] = future.result()
            except Exception as error:
                index["jobs"][key] = {"status": "runner_failed", "error": repr(error)}
            write_json(HERE / f"{phase}_index.json", index)
            print(key, index["jobs"][key]["status"], flush=True)
    # All methods in a pool/load/seed must receive an identical arrival trace.
    if phase == "formal":
        for case in CASES:
            for load in LOADS[case]:
                for seed in SEEDS:
                    traces = {entry["trace_sha256"] for key, entry in index["jobs"].items()
                              if key.startswith(f"{case}/") and key.endswith(f"/{load}/seed{seed}")
                              and entry["status"] in ("passed", "reused")}
                    if len(traces) > 1:
                        raise ValueError(f"Trace mismatch: {case}/{load}/seed{seed}")
    print(HERE / f"{phase}_index.json", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("audit", "smoke", "formal"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "audit":
        write_json(HERE / "audit.json", audit())
        print(HERE / "audit.json")
    else:
        run(args.phase, args.workers)


if __name__ == "__main__":
    main()

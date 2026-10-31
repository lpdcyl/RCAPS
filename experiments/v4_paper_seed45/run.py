"""Complete five-seed V4 paper controls by adding preregistered seeds 3 and 4."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
INDEX = HERE / "index.json"
OLD_CSV = ROOT / "experiments/v4_paper/individual.csv"
OLD_SEEDS = (0, 1, 2)
NEW_SEEDS = (3, 4)
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "gpu_seconds_per_output_token", "completion_fraction")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment():
    packages = ("numpy", "scipy", "networkx", "matplotlib")
    return dict(python=platform.python_version(), executable=sys.executable,
                packages={name: importlib.metadata.version(name) for name in packages},
                platform=platform.platform(),
                env={name: os.environ.get(name) for name in
                     ("PYTHONHASHSEED", "MPLBACKEND", "PYTHONIOENCODING", "OMP_NUM_THREADS",
                      "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")})


def jobs():
    out = []
    for scenario, load in (("single", 700), ("multi", 320)):
        for cell in ("static", "single_boundary"):
            for seed in NEW_SEEDS:
                out.append(dict(group="components", scenario=scenario, load=load,
                                cell=cell, seed=seed, duration_s=1800, warmup_s=0,
                                key=f"components/{scenario}/{load}/{cell}/seed{seed}"))
    for cell in ("chunk1", "chunk2", "chunk8", "all4"):
        for seed in NEW_SEEDS:
            out.append(dict(group="mechanism", scenario="multi", load=320,
                            cell=cell, seed=seed, duration_s=1800, warmup_s=0,
                            key=f"mechanism/multi/320/{cell}/seed{seed}"))
    for ms in (1, 10):
        for seed in NEW_SEEDS:
            out.append(dict(group="boundary_cost", experiment="boundary_cost",
                            scenario="multi", load=320, cell=f"hold_{ms}ms", seed=seed,
                            boundary_cost_s=ms / 1000, arrival_horizon_s=1800,
                            duration_s=5400, warmup_s=0,
                            key=f"boundary_cost/multi/320/hold_{ms}ms/seed{seed}"))
    for scenario, load in (("C2", 160), ("C3", 400)):
        for cell in ("v3", "v4"):
            for seed in NEW_SEEDS:
                out.append(dict(group="pools", scenario=scenario, load=load,
                                cell=cell, seed=seed, duration_s=1800, warmup_s=0,
                                key=f"pools/{scenario}/{load}/{cell}/seed{seed}"))
    assert len(out) == 28
    return out


def old_rows():
    rows = {}
    with OLD_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[(row["scenario"], int(row["load"]), row["cell"], int(row["seed"]))] = row
    return rows


def source_paths():
    paths = [ROOT / name for name in (
        "benchmarks/fixed_window.py", "benchmarks/accumulator.py", "benchmarks/resource_profile.py",
        "simulator/event_simulator/cluster_simulator.py", "simulator/event_simulator/compute_node.py",
        "simulator/event_simulator/kv_cache.py", "simulator/event_simulator/model.py",
        "simulator/event_simulator/request.py", "simulator/trace_generator/simulator_query_feeder.py",
        "rcaps/v3/topology.py", "rcaps/v3_method.py", "rcaps/v4_method.py",
        "rcaps/v4/admission.py", "rcaps/v4/chunking.py", "rcaps/v4/probe.py",
        "experiments/v4_formal/run.py", "experiments/v4_validation/diagnostics.py",
        "experiments/v4_core_validation/core.py", "experiments/v4_paper_seed45/run.py",
        "rcaps/v3/planning_inputs.json", "experiments/v4_paper/individual.csv",
        "experiments/v4_formal/manifest.json", "experiments/v4_recovery/manifest.json",
        "experiments/v4_recovery2/manifest.json", "experiments/v4_core_validation/manifest.json",
    )]
    for case in ("C1_single", "C1_multi"):
        paths.extend(ROOT / "experiments/m2_multistage_candidate/layouts" / case / "single_any" / name
                     for name in ("placement.json", "solution.ini", "simulator_cluster.ini"))
    for case in ("single", "multi", "C2", "C3"):
        paths.extend(ROOT / "rcaps/v3_layouts" / case / name
                     for name in ("placement.json", "solution.ini", "simulator_cluster.ini"))
    planning = read(ROOT / "rcaps/v3/planning_inputs.json")
    paths.extend(ROOT / planning[case]["physical"]
                 for case in ("C1_single", "C1_multi", "C2", "C3"))
    return sorted(set(paths))


def register():
    if MANIFEST.exists():
        manifest = read(MANIFEST)
        check_manifest(manifest)
        return manifest
    old = old_rows()
    base_refs = []
    for job in jobs():
        if job["group"] == "boundary_cost":
            # The old 1 ms/10 ms rows are in v4_core_validation, keyed by scenario/cell/seed.
            for seed in OLD_SEEDS:
                path = ROOT / f"experiments/v4_core_validation/execution/runs/boundary_cost/multi/load320/{job['cell']}/seed{seed}/result.json"
                assert path.exists(), path
                base_refs.append(dict(group="boundary_cost", scenario="multi", load=320,
                                      cell=job["cell"], seed=seed, path=path.relative_to(ROOT).as_posix(),
                                      sha256=sha(path)))
        else:
            scenario = job["scenario"]
            for seed in OLD_SEEDS:
                source_row = old.get((scenario, job["load"], job["cell"], seed))
                assert source_row and source_row["source"], (scenario, job["load"], job["cell"], seed)
                path = ROOT / source_row["source"]
                assert path.exists(), path
                base_refs.append(dict(group=job["group"], scenario=scenario, load=job["load"],
                                      cell=job["cell"], seed=seed, path=source_row["source"], sha256=sha(path)))
    sources = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths()}
    for item in base_refs:
        sources[item["path"]] = item["sha256"]
    manifest = dict(registered_at=stamp(), campaign="V4 evidence completion seeds 3 and 4",
                    jobs=jobs(), base_seed_references=base_refs, sources_sha256=sources,
                    environment=environment(),
                    protocol=dict(seeds=[3, 4], reused_seeds=[0, 1, 2], window_s=1800,
                                  boundary_cost_observation_s=5400, boundary_cost_arrival_horizon_s=1800,
                                  warmup_s=0, drain_tail=False, concurrency=2,
                                  failure_policy="Preserve each failure; continue independent jobs; never overwrite prior attempts"),
                    claim="The 28 additions complete the existing three-seed groups to five; they are not held-out seeds.")
    write(MANIFEST, manifest)
    return manifest


def check_manifest(manifest=None):
    manifest = manifest or read(MANIFEST)
    for path, expected in manifest["sources_sha256"].items():
        actual = sha(ROOT / path)
        if actual != expected:
            raise RuntimeError(f"Frozen input changed: {path}")
    assert environment() == manifest["environment"]
    return manifest


def evaluate(job):
    if job["group"] == "boundary_cost":
        from experiments.v4_core_validation.core import evaluate as evaluate_core
        row = evaluate_core(job, duration=job["duration_s"], arrival_horizon=job["arrival_horizon_s"])
    else:
        from experiments.v4_formal.run import inputs
        from rcaps.v3.topology import TopologyModel
        from rcaps.v4_method import evaluate_variant
        physical, deployment = inputs(dict(scenario=job["scenario"], load=job["load"], cell=job["cell"]))
        cell = job["cell"]
        admission = "full" if cell == "v3" else "canonical" if cell == "canonical4" else "sparse"
        chunk = {"static": 4_194_304, "single_boundary": 4_194_304,
                 "chunk1": 1_048_576, "chunk2": 2_097_152,
                 "chunk8": 8_388_608, "all4": 4_194_304,
                 "v3": 0, "v4": 4_194_304}[cell]
        scenario = job["scenario"] if job["scenario"] in {"single", "multi"} else "single"
        row = evaluate_variant(scenario, job["load"], job["duration_s"], job["warmup_s"], job["seed"],
                               deployment / "solution.ini", deployment / "simulator_cluster.ini",
                               admission=admission, chunk_bytes=chunk,
                               scope="all" if cell == "all4" else "slow",
                               routing_state="static" if cell == "static" else "live",
                               physical_cluster=physical, machine_counts=TopologyModel(physical).machine_counts)
    row.update(status="completed", job=job, manifest_sha256=sha(MANIFEST),
               finished_at=stamp(), environment=environment())
    if "gpu_seconds_per_output_token" not in row and row.get("output_throughput_tokens_per_s"):
        row["gpu_seconds_per_output_token"] = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
    return row


def worker(key):
    manifest = check_manifest()
    job = next(row for row in manifest["jobs"] if row["key"] == key)
    folder = HERE / "runs" / key
    result_path, failure_path = folder / "result.json", folder / "failure.json"
    if result_path.exists() or failure_path.exists():
        raise RuntimeError(f"Attempt already exists: {key}")
    start = time.perf_counter()
    try:
        row = evaluate(job)
        row.update(elapsed_wall_s=time.perf_counter() - start)
        check_manifest()
        write(result_path, row)
        print("WORKER_COMPLETE", key, flush=True)
    except BaseException as error:
        write(failure_path, dict(status="failed", job=job, error=repr(error),
              traceback=traceback.format_exc(), manifest_sha256=sha(MANIFEST),
              elapsed_wall_s=time.perf_counter() - start, finished_at=stamp()))
        raise


def queue():
    manifest = check_manifest()
    if INDEX.exists():
        index = read(INDEX)
        assert index["manifest_sha256"] == sha(MANIFEST)
        assert index["status"] == "running"
    else:
        index = dict(status="running", started_at=stamp(), manifest_sha256=sha(MANIFEST),
                     jobs={job["key"]: dict(status="pending") for job in manifest["jobs"]})
    active = {}
    write(INDEX, index)
    pending = [job for job in manifest["jobs"] if index["jobs"][job["key"]]["status"] == "pending"]
    while pending or active:
        while pending and len(active) < manifest["protocol"]["concurrency"]:
            job = pending.pop(0)
            key = job["key"]
            folder = HERE / "runs" / key
            folder.mkdir(parents=True, exist_ok=True)
            log_path = folder / "worker.log"
            if log_path.exists():
                archived = folder / f"worker.interrupted.{stamp().replace(':', '-')}.log"
                log_path.rename(archived)
            log = log_path.open("x", encoding="utf-8")
            cmd = [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", key]
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy())
            active[key] = (proc, log, job)
            index["jobs"][key] = dict(status="running", pid=proc.pid, started_at=stamp())
            write(INDEX, index)
            print("START", key, proc.pid, flush=True)
        for key, (proc, log, job) in list(active.items()):
            code = proc.poll()
            if code is None:
                continue
            log.close()
            del active[key]
            folder = HERE / "runs" / key
            result, failure = folder / "result.json", folder / "failure.json"
            if code == 0 and result.exists():
                artifact, status = result, "completed"
            elif failure.exists():
                artifact, status = failure, "failed"
            else:
                artifact, status = failure, "failed"
                write(failure, dict(status="failed", classification="native_process_exit",
                      job=job, exit_code=code, error="Worker exited without a result or Python exception artifact",
                      finished_at=stamp()))
            entry = index["jobs"][key]
            entry.update(status=status, exit_code=code, source=artifact.relative_to(ROOT).as_posix(),
                          artifact_sha256=sha(artifact), finished_at=stamp())
            write(INDEX, index)
            print("END", key, status, code, flush=True)
        if active:
            time.sleep(2)
    index.update(status="terminal", finished_at=stamp())
    write(INDEX, index)
    report()


def report():
    manifest = check_manifest()
    index = read(INDEX)
    assert index["status"] == "terminal"
    old = old_rows()
    entries = []
    for job in manifest["jobs"]:
        key, entry = job["key"], index["jobs"][job["key"]]
        path = ROOT / entry["source"]
        assert sha(path) == entry["artifact_sha256"]
        artifact = read(path)
        seed = job["seed"]
        if entry["status"] == "completed":
            row = artifact
        else:
            row = artifact
        entries.append(dict(job=job, status=entry["status"], artifact=artifact,
                            source=entry["source"], sha256=entry["artifact_sha256"]))
    grouped = defaultdict(list)
    individual = []
    refs = {(x["group"], x["scenario"], x["load"], x["cell"], x["seed"]): x
            for x in manifest["base_seed_references"]}
    for item in manifest["jobs"]:
        ident = (item["group"], item["scenario"], item["load"], item["cell"])
        for seed in OLD_SEEDS:
            ref = refs[(*ident, seed)]
            base = read(ROOT / ref["path"])
            grouped[ident].append((seed, "completed", base, ref["path"], ref["sha256"]))
        entry = index["jobs"][item["key"]]
        artifact = read(ROOT / entry["source"])
        grouped[ident].append((item["seed"], entry["status"], artifact, entry["source"], entry["artifact_sha256"]))
    lines = ["# V4 第 7 节五种子补齐结果", "",
             "复用既有种子 0–2，新增窗口为 seed3、seed4；这五个都是已观察种子，不是留出集。",
             "正式窗口 1800 s、零预热、不排空；边界开销实验使用 1800 s 到达期与 5400 s 观察期。",
             "失败不填零；完整五种子组才汇总均值和样本标准差。", "",
             "| 类别/配置 | 成功 | P95 TPOT s | P95 TTFT s | 输出 token/s | 完成率 | GPU s/token |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for ident, rows in grouped.items():
        good = [row for row in rows if row[1] == "completed"]
        complete = len(good) == 5 and {r[0] for r in good} == {0, 1, 2, 3, 4}
        if complete:
            values = []
            for metric in METRICS:
                xs = [float(r[2][metric]) for r in good]
                values.append(f"{mean(xs):.4f} ± {stdev(xs):.4f}")
        else:
            values = ["不汇总"] * len(METRICS)
        label = "/".join(str(x) for x in ident)
        lines.append(f"| {label} | {len(good)}/5 | " + " | ".join(values) + " |")
        for seed, status, row, source, digest in rows:
            individual.append(dict(group=ident[0], scenario=ident[1], load=ident[2], cell=ident[3],
                                   seed=seed, status=status,
                                   **{metric: row.get(metric) if status == "completed" else None for metric in METRICS},
                                   source=source, sha256=digest,
                                   error=row.get("error") if status == "failed" else None))
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=("group", "scenario", "load", "cell", "seed", "status",
                          *METRICS, "source", "sha256", "error"))
        writer.writeheader()
        writer.writerows(individual)
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, new_windows=len(entries),
          counts=dict(Counter(item["status"] for item in entries)),
          manifest_sha256=sha(MANIFEST), index_sha256=sha(INDEX),
          individual_sha256=sha(HERE / "individual.csv"), results_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.register:
        print("REGISTERED", len(register()["jobs"]))
    elif args.worker:
        worker(args.worker)
    elif args.queue:
        queue()
    elif args.report:
        report()
    elif args.status:
        index = read(INDEX)
        print(json.dumps(dict(status=index["status"], counts=Counter(x["status"] for x in index["jobs"].values())),
                         ensure_ascii=False))
    else:
        parser.error("choose --register, --queue, --worker, --report, or --status")


if __name__ == "__main__":
    main()

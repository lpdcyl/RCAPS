"""Frozen cumulative mechanism experiment on the existing RCAPS simulator."""
import argparse
import csv
import importlib.metadata
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write

HERE = Path(__file__).resolve().parent
CONDITIONS = (("single", 350), ("single", 700), ("multi", 160), ("multi", 320))
STAGES = {
    "R2": {"admission": "full", "routing_state": "no_session", "chunk_bytes": 0},
    "S3": {"admission": "sparse", "routing_state": "no_session", "chunk_bytes": 0},
    "Q4": {"admission": "sparse", "routing_state": "live", "chunk_bytes": 0},
}
OLD = {"H0": "HHplus", "P1": "RHplus", "T5": "V4"}


def activated():
    prefix = Path(os.environ.get("CONDA_PREFIX", "")).resolve()
    if os.environ.get("CONDA_DEFAULT_ENV") != "gllm" or prefix.name.lower() != "gllm" or Path(sys.executable).resolve().parent != prefix:
        raise RuntimeError("Activate conda gllm before E6")
    return {"conda_prefix": str(prefix), "python": sys.executable,
            "path_head": os.environ.get("PATH", "").split(os.pathsep)[:7],
            "packages": {n: importlib.metadata.version(n) for n in ("numpy", "scipy", "networkx", "gurobipy")}}


def old_sources():
    core = ROOT / "experiments/v5_core_supplement"
    manifest_path = core / "formal/manifest.json"
    index_path = core / "formal/index.json"
    manifest, index = read(manifest_path), read(index_path)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Prior core campaign is not frozen and terminal")
    rows = {}
    with (core / "individual.csv").open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["cell"] not in OLD.values():
                continue
            key = f"{row['scenario']}/load{row['load']}/{row['cell']}/seed{row['seed']}"
            state = index["jobs"][key]
            path = ROOT / row["source"]
            if state["status"] not in ("completed", "reused") or sha(path) != state["artifact_sha256"]:
                raise RuntimeError("Old source state or SHA mismatch: " + key)
            rows[key] = {"source": row["source"], "sha256": sha(path),
                         "trace_sha256": row["trace_sha256"],
                         "solution_sha256": row["solution_sha256"],
                         "sim_cluster_sha256": row["sim_cluster_sha256"]}
    if len(rows) != 60:
        raise RuntimeError(f"Expected 60 old reference rows, got {len(rows)}")
    return rows, {"manifest_sha256": sha(manifest_path), "index_sha256": sha(index_path),
                  "individual_sha256": sha(core / "individual.csv")}


def sources():
    files = [Path(__file__), HERE / "PLAN_CN.md",
             ROOT / "experiments/v5_core_supplement/adapters.py",
             ROOT / "experiments/v5_core_supplement/run.py",
             ROOT / "experiments/v5_core_supplement/individual.csv"]
    for directory in ("simulator", "rcaps", "benchmarks", "baselines"):
        files += [p for p in (ROOT / directory).rglob("*")
                  if p.is_file() and p.suffix in (".py", ".csv", ".pkl")
                  and "__pycache__" not in p.parts]
    from experiments.v5_core_supplement.run import paths
    from benchmarks.layout import scenario as physical
    for scenario, _ in CONDITIONS:
        solution, cluster, physical_path = paths(scenario, "RR")
        files += [solution, cluster, physical_path, solution.parent / "placement.json", physical(scenario)[1]]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))}


def register(phase):
    if phase not in ("smoke", "formal"):
        raise ValueError(phase)
    directory = HERE / phase
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        check(read(manifest_path), manifest_path)
        return read(manifest_path)
    if phase == "formal":
        smoke = read(HERE / "smoke/index.json")
        if smoke["status"] != "terminal" or any(s["status"] != "completed" for s in smoke["jobs"].values()):
            raise RuntimeError("Smoke is incomplete or failed")
    activated()
    old, registry = old_sources()
    cases = (("single", 700), ("multi", 320)) if phase == "smoke" else CONDITIONS
    seeds = (100,) if phase == "smoke" else tuple(range(5))
    jobs = [{"key": f"{scenario}/load{load}/{stage}/seed{seed}",
             "scenario": scenario, "load": load, "stage": stage,
             "seed": seed, "duration_s": 60 if phase == "smoke" else 1800}
            for scenario, load in cases for seed in seeds for stage in STAGES]
    manifest = {"registered_at": now(), "phase": phase, "jobs": jobs,
        "source_sha256": sources(), "old_rows": old, "old_registry": registry,
        "environment": activated(), "stages": STAGES, "old_stages": OLD,
        "warmup_s": 0, "drain_tail": False, "max_workers": 1,
        "failure_policy": "one attempt per key, immutable original/replay records; no imputation"}
    write(manifest_path, manifest)
    return manifest


def check(manifest, path):
    activated()
    if manifest["environment"]["conda_prefix"] != activated()["conda_prefix"]:
        raise RuntimeError("Conda prefix changed")
    for name, digest in manifest["source_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen source changed: " + name)
    core = ROOT / "experiments/v5_core_supplement"
    registry = manifest["old_registry"]
    for name, actual in (("manifest_sha256", core / "formal/manifest.json"),
                         ("index_sha256", core / "formal/index.json"),
                         ("individual_sha256", core / "individual.csv")):
        if sha(actual) != registry[name]:
            raise RuntimeError("Old reference registry changed: " + name)
    for row in manifest["old_rows"].values():
        if sha(ROOT / row["source"]) != row["sha256"]:
            raise RuntimeError("Old result changed: " + row["source"])


def worker(phase, key):
    path = HERE / phase / "manifest.json"
    manifest = read(path)
    job = next(j for j in manifest["jobs"] if j["key"] == key)
    folder = HERE / phase / "runs" / key
    started = time.perf_counter()
    try:
        check(manifest, path)
        from benchmarks.layout import scenario as physical
        from experiments.v5_core_supplement.run import paths
        from rcaps.v4_method import evaluate_variant
        scenario = job["scenario"]
        solution, cluster, _ = paths(scenario, "RR")
        config = manifest["stages"][job["stage"]]
        row = evaluate_variant(scenario, job["load"], job["duration_s"], 0, job["seed"],
            solution, cluster, physical_cluster=physical(scenario)[0],
            admission=config["admission"], chunk_bytes=config["chunk_bytes"],
            routing_state=config["routing_state"], mechanism=True)
        if len(row["query_samples"]) != row["arrivals"] or not row["output_throughput_tokens_per_s"]:
            raise RuntimeError("Missing request samples or zero output")
        row.update(status="completed", job=job, solution_sha256=sha(solution),
            sim_cluster_sha256=sha(cluster), physical_cluster_sha256=sha(physical(scenario)[0]),
            gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"],
            manifest_sha256=sha(path), finished_at=now(), elapsed_wall_s=time.perf_counter()-started)
        if phase == "formal":
            reference = f"{scenario}/load{job['load']}/V4/seed{job['seed']}"
            expected = manifest["old_rows"][reference]
            if (row["trace_sha256"] != expected["trace_sha256"] or
                    row["solution_sha256"] != expected["solution_sha256"] or
                    row["sim_cluster_sha256"] != expected["sim_cluster_sha256"]):
                raise RuntimeError("Track or deployment differs from reused V4: " + key)
        check(manifest, path)
        write(folder / "result.json", row)
    except BaseException as error:
        write(folder / "failure.json", {"status": "failed", "job": job,
            "error": repr(error), "traceback": traceback.format_exc(),
            "manifest_sha256": sha(path), "finished_at": now(),
            "elapsed_wall_s": time.perf_counter()-started})
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase):
    manifest = register(phase)
    directory = HERE / phase
    index_path = directory / "index.json"
    if index_path.exists():
        raise RuntimeError("Index exists; inspect before recovery")
    index = {"status": "running", "controller_pid": os.getpid(),
             "manifest_sha256": sha(directory / "manifest.json"), "started_at": now(),
             "jobs": {j["key"]: {"status": "pending"} for j in manifest["jobs"]}}
    write(index_path, index)
    for job in manifest["jobs"]:
        check(manifest, directory / "manifest.json")
        key = job["key"]
        folder = directory / "runs" / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "worker.log").open("x", encoding="utf-8") as stream:
            proc = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.E6_cumulative.run", "--phase", phase, "--worker", key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=stream, stderr=subprocess.STDOUT)
            index["jobs"][key] = {"status": "running", "pid": proc.pid, "started_at": now()}
            write(index_path, index)
            try:
                code = proc.wait(timeout=7200)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        result = folder / "result.json"
        failure = folder / "failure.json"
        artifact = result if code == 0 and result.exists() else failure
        if not artifact.exists():
            write(artifact, {"status": "failed", "job": job,
                             "classification": "native_or_abnormal_exit", "exit_code": code,
                             "finished_at": now()})
        index["jobs"][key].update(status="completed" if artifact == result else "failed",
            exit_code=code, source=artifact.relative_to(ROOT).as_posix(),
            artifact_sha256=sha(artifact), finished_at=now())
        write(index_path, index)
        print(key, index["jobs"][key]["status"], flush=True)
    index.update(status="terminal", finished_at=now(),
                 summary=dict(Counter(s["status"] for s in index["jobs"].values())))
    write(index_path, index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"), required=True)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.phase, args.worker)
    elif args.register:
        register(args.phase)
    else:
        queue(args.phase)

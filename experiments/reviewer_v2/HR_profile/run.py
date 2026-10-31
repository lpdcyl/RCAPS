"""Independent, frozen HR passive-resource supplement for E3a."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ENV = dict(PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg",
           OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
CONDITIONS = (("single", 700), ("multi", 320))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def rel(path):
    return Path(path).relative_to(ROOT).as_posix()

def now():
    return datetime.now(timezone.utc).isoformat()

def sources():
    from experiments.v5_core_supplement.run import paths
    from benchmarks.layout import scenario as physical
    files = [Path(__file__), HERE / "PLAN_CN.md", ROOT / "experiments/v5_core_supplement/run.py",
             ROOT / "experiments/v5_core_supplement/adapters.py",
             ROOT / "experiments/v3_method_validation/crossover.py"]
    for directory in ("simulator", "rcaps", "benchmarks", "baselines"):
        files += [p for p in (ROOT / directory).rglob("*") if p.is_file()
                  and p.suffix in (".py", ".csv", ".pkl") and "__pycache__" not in p.parts]
    for scenario, _ in CONDITIONS:
        files += list(paths(scenario, "HR"))
        files.append(physical(scenario)[1])
    core = ROOT / "experiments/v5_core_supplement/individual.csv"
    files.append(core)
    with core.open(newline="", encoding="utf-8-sig") as stream:
        files += [ROOT / r["source"] for r in csv.DictReader(stream)
                  if r["cell"] == "HR" and (r["scenario"], int(r["load"])) in CONDITIONS]
    return {rel(p): sha(p) for p in sorted(set(files))}

def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen input changed: " + name)

def register(phase):
    dest = HERE / phase
    dest.mkdir(exist_ok=True)
    path = dest / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    if phase == "formal":
        smoke = read(HERE / "smoke/index.json")
        if smoke["status"] != "terminal" or any(j["status"] != "completed" for j in smoke["jobs"].values()):
            raise RuntimeError("Smoke did not pass")
    seeds = [100] if phase == "smoke" else list(range(5))
    jobs = [dict(key=f"{scenario}/load{load}/seed{seed}", scenario=scenario,
                 load=load, seed=seed, duration_s=60 if phase == "smoke" else 1800)
            for scenario, load in CONDITIONS for seed in seeds]
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs, max_workers=2,
        warmup_s=0, drain_tail=False, failure_policy="one attempt, failures retained, no imputation",
        environment=dict(executable=sys.executable, python=sys.version, env=ENV,
            packages={p: importlib.metadata.version(p) for p in ("numpy", "scipy", "networkx", "gurobipy")}),
        sources_sha256=sources())
    write(path, manifest)
    return manifest

def worker(phase, key):
    manifest_path = HERE / phase / "manifest.json"
    manifest = read(manifest_path)
    job = next(j for j in manifest["jobs"] if j["key"] == key)
    dest = HERE / phase / "runs" / key
    start = time.perf_counter()
    try:
        check(manifest)
        from experiments.v5_core_supplement.run import evaluate
        row = evaluate(job["scenario"], job["load"], job["seed"], "HR", job["duration_s"], dest / "kv.csv.gz")
        check(manifest)
        if row["output_throughput_tokens_per_s"] <= 0 or len(row["query_samples"]) != row["arrivals"]:
            raise RuntimeError("Invalid throughput or sample count")
        row.update(status="completed", job=job, environment=manifest["environment"],
                   manifest_sha256=sha(manifest_path), kv_series_sha256=sha(dest / "kv.csv.gz"),
                   elapsed_wall_s=time.perf_counter() - start, finished_at=now())
        write(dest / "result.json", row)
    except BaseException as error:
        write(dest / "failure.json", dict(status="failed", job=job, error=repr(error),
            traceback=traceback.format_exc(), manifest_sha256=sha(manifest_path),
            elapsed_wall_s=time.perf_counter() - start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)

def queue(phase):
    manifest = register(phase)
    dest = HERE / phase
    index_path = dest / "index.json"
    if index_path.exists():
        raise RuntimeError("Index exists; inspect before recovery")
    index = dict(status="running", controller_pid=os.getpid(), started_at=now(),
        manifest_sha256=sha(dest / "manifest.json"),
        jobs={j["key"]: dict(status="pending") for j in manifest["jobs"]})
    write(index_path, index)
    pending = list(manifest["jobs"])
    active = []
    environment = dict(os.environ, **ENV)
    while pending or active:
        while pending and len(active) < manifest["max_workers"]:
            check(manifest)
            job = pending.pop(0)
            run_dir = dest / "runs" / job["key"]
            run_dir.mkdir(parents=True, exist_ok=False)
            log = (run_dir / "worker.log").open("x", encoding="utf-8")
            command = [sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.HR_profile.run", "--phase", phase, "--worker", job["key"]]
            proc = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log)
            active.append((proc, job, log, time.monotonic()))
            index["jobs"][job["key"]] = dict(status="running", pid=proc.pid, started_at=now())
            write(index_path, index)
        for item in list(active):
            proc, job, log, start = item
            code = proc.poll()
            timed_out = code is None and time.monotonic() - start > 7200
            if timed_out:
                proc.kill()
                code = proc.wait()
            if code is None:
                continue
            log.close()
            active.remove(item)
            run_dir = dest / "runs" / job["key"]
            passed = code == 0 and (run_dir / "result.json").exists()
            output = run_dir / ("result.json" if passed else "failure.json")
            if not output.exists():
                write(output, dict(status="failed", job=job, exit_code=code,
                                   classification="timeout" if timed_out else "native_or_abnormal_exit", finished_at=now()))
            index["jobs"][job["key"]].update(status="completed" if passed else "failed", exit_code=code,
                source=rel(output), artifact_sha256=sha(output), finished_at=now())
            write(index_path, index)
        if active:
            time.sleep(2)
    check(manifest)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if not args.phase:
        parser.error("--phase required")
    if args.worker:
        worker(args.phase, args.worker)
    elif args.register:
        register(args.phase)
    else:
        queue(args.phase)

if __name__ == "__main__":
    main()

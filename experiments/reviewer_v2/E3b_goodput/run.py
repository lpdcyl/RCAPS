"""Frozen 200-window warmup-and-drain SLO goodput campaign."""
from __future__ import annotations

import argparse
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

from .evaluate import METHODS, evaluate
from .probe import SLO

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ENV = dict(PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg",
           OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
LOADS = {"single": (350, 500, 700, 900), "multi": (160, 240, 320, 400)}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def sources():
    from experiments.v5_core_supplement.run import paths
    from experiments.reviewer_v2.E2a_helix_tuning.run import sources as core_sources
    base = dict(core_sources())
    files = [Path(__file__), HERE / "PLAN_CN.md", HERE / "evaluate.py",
             HERE / "probe.py", HERE / "smoke.py", HERE / "SMOKE_AUDIT.json",
             ROOT / "experiments/v5_core_supplement/drain.py",
             ROOT / "experiments/v6_completion/session_cost.py",
             ROOT / "experiments/reviewer_v2/E2a_helix_tuning/FINAL_AUDIT.json",
             ROOT / "experiments/reviewer_v2/E2a_helix_tuning/selection.json",
             ROOT / "experiments/reviewer_v2/E2a_helix_tuning/single_correction/selection.json"]
    for case in LOADS:
        for cell in ("HH", "V4"):
            solution, cluster, physical = paths(case, cell)
            files.extend((solution, cluster, physical))
            if cell == "V4":
                files.append(solution.parent / "placement.json")
    base.update({rel(path): sha(path) for path in sorted(set(files))})
    return base


def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen E3b input changed: " + name)


def register():
    dest = HERE / "formal"
    dest.mkdir(exist_ok=True)
    target = dest / "manifest.json"
    if target.exists():
        manifest = read(target)
        check(manifest)
        return manifest
    smoke = read(HERE / "SMOKE_AUDIT.json")
    if not smoke["passed"] or len(smoke["rows"]) != 10:
        raise RuntimeError("E3b ten-window smoke incomplete")
    e2a = read(ROOT / "experiments/reviewer_v2/E2a_helix_tuning/FINAL_AUDIT.json")
    if not e2a["passed"] or e2a["complete_five_seed_groups"] != 4:
        raise RuntimeError("E2a held-out audit incomplete")
    jobs = [dict(key=f"{case}/{load}/{method}/seed{seed}", scenario=case,
                 load=load, method=method, seed=seed)
            for case, loads in LOADS.items() for load in loads
            for method in METHODS for seed in range(5)]
    if len(jobs) != 200:
        raise RuntimeError("Wrong E3b job count")
    manifest = dict(registered_at=now(), protocol="warmup300_measure1800_drain_cap3600",
        warmup_s=300, measurement_s=1800, tail_cap_s=3600, jobs=jobs, loads=LOADS,
        methods=METHODS, seeds=list(range(5)), slo=SLO, max_workers=6,
        timeout_wall_s=10800,
        gpu_busy_scope="All deployed GPU execution from measurement start through actual drain stop, including competing warmup traffic",
        failure_policy="One original attempt per key; preserve failure.json; independent replay only",
        environment=dict(executable=sys.executable, python=sys.version, env=ENV,
            packages={p: importlib.metadata.version(p)
                      for p in ("numpy", "scipy", "networkx", "gurobipy")}),
        sources_sha256=sources())
    write(target, manifest)
    return manifest


def worker(key):
    manifest_path = HERE / "formal/manifest.json"
    manifest = read(manifest_path)
    job = next(job for job in manifest["jobs"] if job["key"] == key)
    dest = HERE / "formal/runs" / key
    start = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job["scenario"], job["load"], job["method"], job["seed"])
        check(manifest)
        good = row["goodput"]
        if (good["measurement_arrivals"] != row["drain"]["arrivals"] or
                good["completed_by_tail"] + good["right_censored"] != good["measurement_arrivals"]):
            raise RuntimeError("Goodput population mismatch")
        row.update(status="completed", job=job, manifest_sha256=sha(manifest_path),
                   environment=manifest["environment"], elapsed_wall_s=time.perf_counter()-start,
                   finished_at=now())
        write(dest / "result.json", row)
    except BaseException as error:
        write(dest / "failure.json", dict(status="failed", job=job, error=repr(error),
            traceback=traceback.format_exc(), manifest_sha256=sha(manifest_path),
            elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    dest = HERE / "formal"
    index_path = dest / "index.json"
    if index_path.exists():
        raise RuntimeError("E3b index already exists; inspect before recovery")
    index = dict(status="running", controller_pid=os.getpid(), started_at=now(),
        manifest_sha256=sha(dest / "manifest.json"),
        jobs={job["key"]: dict(status="pending") for job in manifest["jobs"]})
    write(index_path, index)
    pending, active = list(manifest["jobs"]), []
    environment = dict(os.environ, **ENV)
    while pending or active:
        while pending and len(active) < manifest["max_workers"]:
            check(manifest)
            job = pending.pop(0)
            folder = dest / "runs" / job["key"]
            folder.mkdir(parents=True, exist_ok=False)
            log = (folder / "worker.log").open("x", encoding="utf-8")
            cmd = [sys.executable, "-u", "-X", "faulthandler", "-m",
                   "experiments.reviewer_v2.E3b_goodput.run", "--worker", job["key"]]
            process = subprocess.Popen(cmd, cwd=ROOT, env=environment, stdout=log, stderr=log)
            active.append((process, job, log, time.monotonic()))
            index["jobs"][job["key"]] = dict(status="running", pid=process.pid, started_at=now())
            write(index_path, index)
            print("START", job["key"], flush=True)
        for item in list(active):
            process, job, log, begin = item
            code = process.poll()
            timed_out = code is None and time.monotonic() - begin > manifest["timeout_wall_s"]
            if timed_out:
                process.kill()
                code = process.wait()
            if code is None:
                continue
            log.close()
            active.remove(item)
            folder = dest / "runs" / job["key"]
            passed = code == 0 and (folder / "result.json").exists()
            artifact = folder / ("result.json" if passed else "failure.json")
            if not artifact.exists():
                write(artifact, dict(status="failed", job=job, exit_code=code,
                    classification="timeout" if timed_out else "native_or_abnormal_exit",
                    finished_at=now()))
            index["jobs"][job["key"]].update(status="completed" if passed else "failed",
                exit_code=code, source=rel(artifact), artifact_sha256=sha(artifact),
                finished_at=now())
            write(index_path, index)
            print("END", job["key"], code, flush=True)
        if active:
            time.sleep(2)
    check(manifest)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.register:
        register()
    else:
        queue()

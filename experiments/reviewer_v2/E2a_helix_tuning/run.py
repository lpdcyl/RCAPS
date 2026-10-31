"""Immutable E2a tuning campaign; evaluation seeds register after selection."""
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

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ENV = dict(PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg",
           OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
LOADS = (("single", 350), ("single", 700), ("multi", 160), ("multi", 320))


def now():
    return datetime.now(timezone.utc).isoformat()


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


def candidates():
    rows = [dict(priority=p, batch=b, hwm=0.9, ratio=0.6)
            for p, b in ((False, False), (False, True), (True, False), (True, True))]
    rows += [dict(priority=True, batch=True, hwm=h, ratio=r)
             for h in (0.8, 0.9, 0.95) for r in (0.4, 0.6, 0.8)
             if (h, r) != (0.9, 0.6)]
    assert len(rows) == 12
    return rows


def label(params):
    return f"p{int(params['priority'])}b{int(params['batch'])}_h{params['hwm']}_r{params['ratio']}"


def sources():
    from benchmarks.layout import scenario
    files = [Path(__file__), HERE / "PLAN_CN.md", HERE / "adapters.py", HERE / "smoke.py",
             HERE / "SMOKE_AUDIT.json", ROOT / "experiments/v5_core_supplement/adapters.py",
             ROOT / "experiments/v5_core_supplement/individual.csv"]
    for folder in ("simulator", "rcaps", "benchmarks"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                     and p.suffix in (".py", ".csv", ".pkl") and "__pycache__" not in p.parts)
    for case, _ in LOADS:
        files.extend(scenario(case))
    return {rel(p): sha(p) for p in sorted(set(files))}


def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen E2a input changed: " + name)
    if manifest["phase"] == "evaluation":
        if sha(HERE / "selection.json") != manifest["selection_sha256"]:
            raise RuntimeError("Frozen E2a selection changed")


def register(phase):
    dest = HERE / phase
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    if not read(HERE / "SMOKE_AUDIT.json")["passed"]:
        raise RuntimeError("E2a smoke audit has not passed")
    if phase == "tuning":
        jobs = [dict(scenario=case, load=load, seed=seed, params=params,
                     key=f"{case}/{load}/{label(params)}/seed{seed}")
                for case, load in LOADS for params in candidates() for seed in (5, 6)]
    elif phase == "evaluation":
        if read(HERE / "tuning/index.json")["status"] != "terminal":
            raise RuntimeError("Tuning not terminal")
        choice = read(HERE / "selection.json")
        jobs = [dict(scenario=case, load=load, seed=seed,
                     params=choice[f"{case}/{load}"]["params"],
                     key=f"{case}/{load}/tuned/seed{seed}")
                for case, load in LOADS for seed in range(5)]
    else:
        raise ValueError(phase)
    manifest = dict(phase=phase, registered_at=now(), duration_s=1800, warmup_s=0,
                    drain_tail=False, max_workers=2, timeout_wall_s=7200,
                    jobs=jobs, conditions=LOADS,
                    tuning_seed_rule="Only seeds 5,6 choose parameters; seeds 0..4 evaluation only",
                    failure_policy="One attempt per key; preserve failure.json; independent replay only",
                    environment=dict(executable=sys.executable, python=sys.version,
                        env=ENV, packages={p: importlib.metadata.version(p)
                        for p in ("numpy", "scipy", "networkx", "gurobipy")}),
                    sources_sha256=sources())
    if phase == "evaluation":
        manifest["selection_sha256"] = sha(HERE / "selection.json")
    write(path, manifest)
    return manifest


def worker(phase, key):
    manifest_path = HERE / phase / "manifest.json"
    manifest = read(manifest_path)
    job = next(job for job in manifest["jobs"] if job["key"] == key)
    dest = HERE / phase / "runs" / key
    started = time.perf_counter()
    try:
        check(manifest)
        from benchmarks.fixed_window import run
        from benchmarks.layout import scenario
        from experiments.v5_core_supplement.adapters import SetupProbe
        from experiments.reviewer_v2.E2a_helix_tuning.adapters import factory
        case, load, seed, params = (job[x] for x in ("scenario", "load", "seed", "params"))
        physical, profile, solution, cluster = scenario(case)
        row = run(case, "queue_dag", load, 1800, 0, seed, solution, cluster,
                  physical_cluster=physical,
                  scheduler_factory=factory(params["priority"], params["batch"],
                                            params["hwm"], params["ratio"]),
                  compact=True, record_query_samples=True, profile_resources=True,
                  phase_link_probe=SetupProbe())
        check(manifest)
        if len(row["query_samples"]) != row["arrivals"]:
            raise RuntimeError("Missing query samples")
        throughput = row["output_throughput_tokens_per_s"]
        if throughput <= 0:
            raise RuntimeError("Zero measured throughput")
        row.update(status="completed", job=job, cell="Helix-tuned-candidate",
                   solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) / throughput,
                   manifest_sha256=sha(manifest_path), environment=manifest["environment"],
                   elapsed_wall_s=time.perf_counter() - started, finished_at=now())
        write(dest / "result.json", row)
    except BaseException as error:
        write(dest / "failure.json", dict(status="failed", job=job, error=repr(error),
            traceback=traceback.format_exc(), manifest_sha256=sha(manifest_path),
            elapsed_wall_s=time.perf_counter() - started, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase):
    manifest = register(phase)
    dest = HERE / phase
    index_path = dest / "index.json"
    if index_path.exists():
        raise RuntimeError("E2a index exists; inspect controller before recovery")
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
            command = [sys.executable, "-u", "-X", "faulthandler", "-m",
                       "experiments.reviewer_v2.E2a_helix_tuning.run", "--phase", phase,
                       "--worker", job["key"]]
            proc = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log)
            active.append((proc, job, log, time.monotonic()))
            index["jobs"][job["key"]] = dict(status="running", pid=proc.pid, started_at=now())
            write(index_path, index)
            print("START", job["key"], flush=True)
        for item in list(active):
            proc, job, log, begin = item
            code = proc.poll()
            timed_out = code is None and time.monotonic() - begin > manifest["timeout_wall_s"]
            if timed_out:
                proc.kill()
                code = proc.wait()
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
            index["jobs"][job["key"]].update(
                status="completed" if passed else "failed", exit_code=code,
                source=rel(artifact), artifact_sha256=sha(artifact), finished_at=now())
            write(index_path, index)
            print("END", job["key"], code, flush=True)
        if active:
            time.sleep(2)
    check(manifest)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("tuning", "evaluation"), required=True)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.phase, args.worker)
    elif args.register:
        register(args.phase)
    else:
        queue(args.phase)

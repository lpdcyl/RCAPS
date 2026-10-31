"""Independent E2a single-cluster campaign on the historical Helix deployment."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.reviewer_v2.E2a_helix_tuning import run as core

ROOT = core.ROOT
HERE = Path(__file__).resolve().parent


def paths():
    from baselines.helix import layout
    from benchmarks.layout import scenario
    physical = scenario("single")[0]
    solution, cluster = layout("single", ROOT)
    return physical, solution, cluster


def inputs():
    items = dict(core.sources())
    for path in (Path(__file__), HERE / "PLAN_CN.md", HERE / "smoke.py",
                 HERE / "SMOKE_AUDIT.json", *paths()):
        items[core.rel(path)] = core.sha(path)
    return items


def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if core.sha(ROOT / name) != digest:
            raise RuntimeError("Frozen E2a single correction input changed: " + name)
    if manifest["phase"] == "evaluation":
        if core.sha(HERE / "selection.json") != manifest["selection_sha256"]:
            raise RuntimeError("Frozen corrected selection changed")


def register(phase):
    dest = HERE / phase
    dest.mkdir(exist_ok=True)
    path = dest / "manifest.json"
    if path.exists():
        manifest = core.read(path)
        check(manifest)
        return manifest
    smoke = core.read(HERE / "SMOKE_AUDIT.json")
    if not smoke["passed"]:
        raise RuntimeError("Corrected official-layout smoke has not passed")
    if phase == "tuning":
        jobs = [dict(scenario="single", load=load, seed=seed, params=params,
                     key=f"single/{load}/{core.label(params)}/seed{seed}")
                for load in (350, 700) for params in core.candidates() for seed in (5, 6)]
    elif phase == "evaluation":
        if core.read(HERE / "tuning/index.json")["status"] != "terminal":
            raise RuntimeError("Corrected tuning is not terminal")
        choice = core.read(HERE / "selection.json")
        jobs = [dict(scenario="single", load=load, seed=seed,
                     params=choice[f"single/{load}"]["params"],
                     key=f"single/{load}/tuned/seed{seed}")
                for load in (350, 700) for seed in range(5)]
    else:
        raise ValueError(phase)
    manifest = dict(phase=phase, registered_at=core.now(), jobs=jobs,
                    duration_s=1800, warmup_s=0, drain_tail=False,
                    max_workers=2, timeout_wall_s=7200,
                    original_wrong_layout_manifest_sha256=core.sha(
                        core.HERE / "tuning/manifest.json"),
                    correction_reason="single layout hash differed from historical Helix baseline",
                    failure_policy="One original attempt per key; preserve failures and replay separately",
                    environment=dict(executable=sys.executable, python=sys.version, env=core.ENV),
                    sources_sha256=inputs())
    if phase == "evaluation":
        manifest["selection_sha256"] = core.sha(HERE / "selection.json")
    core.write(path, manifest)
    return manifest


def worker(phase, key):
    manifest_path = HERE / phase / "manifest.json"
    manifest = core.read(manifest_path)
    job = next(job for job in manifest["jobs"] if job["key"] == key)
    dest = HERE / phase / "runs" / key
    started = time.perf_counter()
    try:
        check(manifest)
        from benchmarks.fixed_window import run
        from experiments.v5_core_supplement.adapters import SetupProbe
        from experiments.reviewer_v2.E2a_helix_tuning.adapters import factory
        physical, solution, cluster = paths()
        params = job["params"]
        row = run("single", "queue_dag", job["load"], 1800, 0, job["seed"],
                  solution, cluster, physical_cluster=physical,
                  scheduler_factory=factory(params["priority"], params["batch"],
                                            params["hwm"], params["ratio"]),
                  compact=True, record_query_samples=True, profile_resources=True,
                  phase_link_probe=SetupProbe())
        check(manifest)
        if len(row["query_samples"]) != row["arrivals"]:
            raise RuntimeError("Missing query samples")
        throughput = row["output_throughput_tokens_per_s"]
        if throughput <= 0:
            raise RuntimeError("Zero measured output")
        row.update(status="completed", job=job, cell="Helix-tuned-candidate",
                   solution_sha256=core.sha(solution), sim_cluster_sha256=core.sha(cluster),
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) / throughput,
                   manifest_sha256=core.sha(manifest_path), environment=manifest["environment"],
                   elapsed_wall_s=time.perf_counter() - started, finished_at=core.now())
        core.write(dest / "result.json", row)
    except BaseException as error:
        core.write(dest / "failure.json", dict(status="failed", job=job,
            error=repr(error), traceback=traceback.format_exc(),
            manifest_sha256=core.sha(manifest_path),
            elapsed_wall_s=time.perf_counter() - started, finished_at=core.now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase):
    manifest = register(phase)
    dest = HERE / phase
    index_path = dest / "index.json"
    if index_path.exists():
        raise RuntimeError("Corrected E2a index already exists")
    index = dict(status="running", controller_pid=os.getpid(), started_at=core.now(),
                 manifest_sha256=core.sha(dest / "manifest.json"),
                 jobs={job["key"]: dict(status="pending") for job in manifest["jobs"]})
    core.write(index_path, index)
    pending, active = list(manifest["jobs"]), []
    environment = dict(os.environ, **core.ENV)
    while pending or active:
        while pending and len(active) < manifest["max_workers"]:
            check(manifest)
            job = pending.pop(0)
            folder = dest / "runs" / job["key"]
            folder.mkdir(parents=True, exist_ok=False)
            log = (folder / "worker.log").open("x", encoding="utf-8")
            command = [sys.executable, "-u", "-X", "faulthandler", "-m",
                       "experiments.reviewer_v2.E2a_helix_tuning.single_correction.run",
                       "--phase", phase, "--worker", job["key"]]
            proc = subprocess.Popen(command, cwd=ROOT, env=environment,
                                    stdout=log, stderr=log)
            active.append((proc, job, log, time.monotonic()))
            index["jobs"][job["key"]] = dict(status="running", pid=proc.pid,
                                            started_at=core.now())
            core.write(index_path, index)
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
                core.write(artifact, dict(status="failed", job=job, exit_code=code,
                    classification="timeout" if timed_out else "native_or_abnormal_exit",
                    finished_at=core.now()))
            index["jobs"][job["key"]].update(
                status="completed" if passed else "failed", exit_code=code,
                source=core.rel(artifact), artifact_sha256=core.sha(artifact),
                finished_at=core.now())
            core.write(index_path, index)
            print("END", job["key"], code, flush=True)
        if active:
            time.sleep(2)
    check(manifest)
    index.update(status="terminal", finished_at=core.now())
    core.write(index_path, index)


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

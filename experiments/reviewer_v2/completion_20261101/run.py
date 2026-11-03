"""Run independent completion campaigns without changing frozen experiments."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write

HERE = Path(__file__).resolve().parent
E5A = ROOT / "experiments/reviewer_v2/E5_scale_kv"
E6 = ROOT / "experiments/reviewer_v2/E6_cumulative"
MILP = ROOT / "experiments/reviewer_v2/E2a_helix_tuning/milp_budget"
CASES = (("single", 350), ("single", 700), ("multi", 160), ("multi", 320))
CAMPAIGNS = ("e5a", "e6", "milp")


def activated():
    prefix = Path(os.environ.get("CONDA_PREFIX", "")).resolve()
    if (os.environ.get("CONDA_DEFAULT_ENV") != "gllm"
            or prefix.name.lower() != "gllm"
            or Path(sys.executable).resolve().parent != prefix):
        raise RuntimeError("Activate conda gllm before running this batch")
    return {"conda_prefix": str(prefix), "python": sys.executable}


def source_paths(campaign):
    items = [HERE / "PLAN_CN.md", Path(__file__)]
    if campaign == "e5a":
        items += [E5A / "run.py", E5A / "formal/manifest.json",
                  E5A / "E5a_FINAL_AUDIT.json"]
    elif campaign == "e6":
        items += [E6 / "run.py", E6 / "formal/manifest.json",
                  E6 / "FINAL_AUDIT.json"]
    else:
        from baselines.helix import layout

        items += [MILP / "FINAL_AUDIT.json",
                  MILP / "retry_workspace/formal/manifest.json",
                  MILP / "retry_workspace/formal/index.json",
                  ROOT / "benchmarks/fixed_window.py",
                  ROOT / "benchmarks/layout.py",
                  ROOT / "baselines/helix.py"]
        for directory in ("simulator", "rcaps", "benchmarks", "baselines"):
            items += [p for p in (ROOT / directory).rglob("*")
                      if p.is_file() and p.suffix in (".py", ".csv", ".pkl")
                      and "__pycache__" not in p.parts]
        for case in ("single", "multi"):
            items += [*layout(case, ROOT), physical_path(case)]
            base = "single_cluster" if case == "single" else "distributed_clusters"
            items += [ROOT / "artifact_evaluation" / base / "config/machine_profiles.ini"]
        for case, budget in (("single", 120), ("single", 480), ("multi", 480)):
            base = MILP / "retry_workspace/formal/runs" / f"C1_{case}" / str(budget)
            items += [base / "result.json", base / "layout/ilp_sol.ini",
                      base / "layout/simulator_cluster.ini"]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in items}


def check(campaign, manifest):
    if activated()["conda_prefix"] != manifest["environment"]["conda_prefix"]:
        raise RuntimeError("Conda environment changed")
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen source changed: " + name)
    if campaign == "e5a":
        from experiments.reviewer_v2.E5_scale_kv.run import check as old_check

        old = E5A / "formal/manifest.json"
        old_check(read(old))
    elif campaign == "e6":
        from experiments.reviewer_v2.E6_cumulative.run import check as old_check

        old = E6 / "formal/manifest.json"
        old_check(read(old), old)
    else:
        if not read(MILP / "FINAL_AUDIT.json")["passed"]:
            raise RuntimeError("MILP offline audit has not passed")


def jobs(campaign, phase):
    if campaign == "e5a":
        frozen = read(E5A / "formal/manifest.json")["jobs"]
        if phase == "smoke":
            return [dict(job, seed=100, duration_s=60,
                         key=f"E5a/load1450/{job['method']}/seed100")
                    for job in frozen if job["load"] == 1450 and job["seed"] == 0]
        return frozen
    if campaign == "e6":
        frozen = read(E6 / "formal/manifest.json")["jobs"]
        if phase == "smoke":
            return [dict(job, seed=100, duration_s=60,
                         key=f"{job['scenario']}/load{job['load']}/{job['stage']}/seed100")
                    for job in frozen if job["seed"] == 0
                    and (job["scenario"], job["load"]) in (("single", 700), ("multi", 320))]
        return frozen
    layouts = {"single": ("official", "120", "480"),
               "multi": ("official", "480")}
    selected = [(case, load, layout) for case, load in CASES
                for layout in layouts[case]]
    if phase == "smoke":
        selected = [(case, load, layout) for case, load, layout in selected
                    if load == (700 if case == "single" else 320)]
        seeds = (100,)
    else:
        seeds = range(5)
    return [dict(key=f"{case}/load{load}/{layout}/seed{seed}",
                 scenario=case, load=load, layout=layout, seed=seed,
                 duration_s=60 if phase == "smoke" else 1800)
            for case, load, layout in selected for seed in seeds]


def folder(campaign, phase):
    return HERE / campaign / phase


def register(campaign, phase):
    target = folder(campaign, phase) / "manifest.json"
    if target.exists():
        manifest = read(target)
        check(campaign, manifest)
        return manifest
    if phase == "formal" and campaign == "milp":
        smoke_dir = folder(campaign, "smoke")
        smoke = read(smoke_dir / "index.json")
        if (smoke["status"] != "terminal"
                or smoke["manifest_sha256"] != sha(smoke_dir / "manifest.json")
                or any(state["status"] != "completed" for state in smoke["jobs"].values())):
            raise RuntimeError("MILP online smoke has not passed 5/5")
    manifest = {"campaign": campaign, "phase": phase,
                "registered_at": now(), "jobs": jobs(campaign, phase),
                "environment": activated(), "sources_sha256": source_paths(campaign),
                "max_workers": 1, "timeout_wall_s": 7200,
                "failure_policy": "one attempt per key; old formal and replay remain read-only"}
    check(campaign, manifest)
    write(target, manifest)
    return manifest


def milp_paths(job):
    from baselines.helix import layout

    case = job["scenario"]
    physical = physical_path(case)
    base = "single_cluster" if case == "single" else "distributed_clusters"
    profile = ROOT / "artifact_evaluation" / base / "config/machine_profiles.ini"
    if job["layout"] == "official":
        solution, cluster = layout(case, ROOT)
    else:
        base = MILP / "retry_workspace/formal/runs" / f"C1_{case}" / job["layout"]
        offline = read(base / "result.json")
        if offline["status"] != "passed" or not offline["deployment"]["valid"]:
            raise RuntimeError("MILP layout is not validated")
        solution, cluster = base / "layout/ilp_sol.ini", base / "layout/simulator_cluster.ini"
        if (sha(solution) != offline["deployment"]["solution_sha256"]
                or sha(cluster) != offline["deployment"]["sim_cluster_sha256"]):
            raise RuntimeError("MILP layout differs from offline audit")
    return physical, profile, solution, cluster


def physical_path(case):
    base = "single_cluster" if case == "single" else "distributed_clusters"
    name = "cluster24.ini" if case == "single" else "3cluster24.ini"
    return ROOT / "artifact_evaluation" / base / "config" / name


def evaluate(campaign, job):
    if campaign == "e5a":
        from experiments.reviewer_v2.E5_scale_kv.run import evaluate as old_evaluate

        return old_evaluate(job)
    if campaign == "e6":
        from benchmarks.layout import scenario as physical
        from experiments.v5_core_supplement.run import paths
        from rcaps.v4_method import evaluate_variant

        scenario = job["scenario"]
        solution, cluster, _ = paths(scenario, "RR")
        stage = read(E6 / "formal/manifest.json")["stages"][job["stage"]]
        row = evaluate_variant(scenario, job["load"], job["duration_s"], 0,
                               job["seed"], solution, cluster,
                               physical_cluster=physical(scenario)[0],
                               admission=stage["admission"],
                               chunk_bytes=stage["chunk_bytes"],
                               routing_state=stage["routing_state"], mechanism=True)
        row.update(solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
                   physical_cluster_sha256=sha(physical(scenario)[0]))
        return row
    from benchmarks.fixed_window import run

    physical, profile, solution, cluster = milp_paths(job)
    row = run(job["scenario"], "helix", job["load"], job["duration_s"], 0,
              job["seed"], solution, cluster, physical_cluster=physical,
              machine_profile=profile, compact=True, record_query_samples=True,
              profile_resources=True)
    row.update(solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
               physical_cluster_sha256=sha(physical), machine_profile_sha256=sha(profile))
    return row


def worker(campaign, phase, key):
    base = folder(campaign, phase)
    manifest_path = base / "manifest.json"
    manifest = read(manifest_path)
    job = next(job for job in manifest["jobs"] if job["key"] == key)
    target = base / "runs" / key
    started = time.perf_counter()
    try:
        check(campaign, manifest)
        row = evaluate(campaign, job)
        check(campaign, manifest)
        if len(row["query_samples"]) != row["arrivals"]:
            raise RuntimeError("Query sample population mismatch")
        if row["output_throughput_tokens_per_s"] <= 0:
            raise RuntimeError("Zero output throughput")
        row.update(status="completed", job=job, campaign=campaign,
                   manifest_sha256=sha(manifest_path),
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values())
                   / row["output_throughput_tokens_per_s"],
                   elapsed_wall_s=time.perf_counter() - started, finished_at=now())
        write(target / "result.json", row)
    except BaseException as error:
        write(target / "failure.json", {"status": "failed", "job": job,
              "error": repr(error), "traceback": traceback.format_exc(),
              "elapsed_wall_s": time.perf_counter() - started, "finished_at": now()})
        traceback.print_exc()
        raise SystemExit(1)


def run_queue(campaign, phase, resume):
    manifest = register(campaign, phase)
    base = folder(campaign, phase)
    index_path = base / "index.json"
    if index_path.exists() and not resume:
        raise RuntimeError("Index already exists; use --resume after checking the controller")
    if index_path.exists():
        index = read(index_path)
        if index["status"] == "terminal":
            return
        if index["manifest_sha256"] != sha(base / "manifest.json"):
            raise RuntimeError("Manifest changed")
        for key, state in index["jobs"].items():
            if state["status"] != "running":
                continue
            if state.get("pid") and subprocess.run(
                    ["tasklist", "/FI", f"PID eq {state['pid']}"],
                    capture_output=True, text=True).stdout.find(str(state["pid"])) >= 0:
                raise RuntimeError("Worker still running: " + key)
            target = base / "runs" / key
            artifact = next((p for p in (target / "result.json", target / "failure.json")
                             if p.exists()), None)
            if artifact is None:
                artifact = target / "failure.json"
                write(artifact, {"status": "failed", "key": key,
                      "classification": "controller_interrupted", "finished_at": now()})
            state.update(status="completed" if artifact.name == "result.json" else "failed",
                         source=artifact.relative_to(ROOT).as_posix(),
                         artifact_sha256=sha(artifact), finished_at=now())
        write(index_path, index)
    else:
        index = {"status": "running", "controller_pid": os.getpid(),
                 "manifest_sha256": sha(base / "manifest.json"), "started_at": now(),
                 "jobs": {job["key"]: {"status": "pending"} for job in manifest["jobs"]}}
        write(index_path, index)
    for job in manifest["jobs"]:
        key = job["key"]
        if index["jobs"][key]["status"] != "pending":
            continue
        check(campaign, manifest)
        target = base / "runs" / key
        target.mkdir(parents=True, exist_ok=False)
        with (target / "worker.log").open("x", encoding="utf-8") as log:
            proc = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.completion_20261101.run", campaign, phase,
                "--worker", key], cwd=ROOT, env=dict(os.environ, **ENV),
                stdout=log, stderr=subprocess.STDOUT)
            index["jobs"][key] = {"status": "running", "pid": proc.pid,
                                   "started_at": now()}
            write(index_path, index)
            try:
                code = proc.wait(timeout=manifest["timeout_wall_s"])
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        result, failure = target / "result.json", target / "failure.json"
        artifact = result if code == 0 and result.exists() else failure
        if not artifact.exists():
            write(artifact, {"status": "failed", "job": job,
                  "classification": "native_or_abnormal_exit", "exit_code": code,
                  "finished_at": now()})
        index["jobs"][key].update(
            status="completed" if artifact == result else "failed", exit_code=code,
            source=artifact.relative_to(ROOT).as_posix(), artifact_sha256=sha(artifact),
            finished_at=now())
        write(index_path, index)
        print(campaign, phase, key, index["jobs"][key]["status"], flush=True)
    check(campaign, manifest)
    index.update(status="terminal", finished_at=now(),
                 summary=dict(Counter(s["status"] for s in index["jobs"].values())))
    write(index_path, index)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", choices=CAMPAIGNS)
    parser.add_argument("phase", choices=("smoke", "formal"))
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args.campaign, args.phase, args.worker)
    elif args.register:
        register(args.campaign, args.phase)
    else:
        run_queue(args.campaign, args.phase, args.resume)


if __name__ == "__main__":
    main()

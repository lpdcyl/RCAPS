"""Independently replay each failed MILP-online formal window once."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import psutil

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write

from .run import HERE, activated, check, evaluate

BASE = HERE / "milp_failure_replay"
FORMAL = HERE / "milp/formal"
SCRIPT = Path(__file__)


def check_manifest(manifest):
    if activated() != manifest["environment"] or sha(SCRIPT) != manifest["script_sha256"]:
        raise RuntimeError("MILP replay environment or script changed")
    for name, expected in manifest["formal_sha256"].items():
        if sha(FORMAL / name) != expected:
            raise RuntimeError("Frozen MILP formal registration changed: " + name)
    if sha(HERE / "milp/FINAL_AUDIT.json") != manifest["formal_audit_sha256"]:
        raise RuntimeError("MILP formal audit changed")
    check("milp", read(FORMAL / "manifest.json"))
    for item in manifest["jobs"]:
        if sha(ROOT / item["formal_failure_source"]) != item["formal_failure_sha256"]:
            raise RuntimeError("Original MILP failure changed: " + item["key"])


def register():
    path = BASE / "manifest.json"
    if path.exists():
        manifest = read(path)
        check_manifest(manifest)
        return manifest
    formal_manifest = read(FORMAL / "manifest.json")
    formal_index = read(FORMAL / "index.json")
    audit = read(HERE / "milp/FINAL_AUDIT.json")
    if formal_index["status"] != "terminal" or not audit["passed"] or audit["registered"] != 50:
        raise RuntimeError("MILP formal campaign is not terminal and audited")
    jobs = []
    for job in formal_manifest["jobs"]:
        key = job["key"]
        state = formal_index["jobs"][key]
        if state["status"] != "failed":
            continue
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("MILP formal artifact SHA mismatch: " + key)
        jobs.append({"key": key, "job": job, "formal_failure_source": state["source"],
                     "formal_failure_sha256": state["artifact_sha256"]})
    if len(jobs) != 38:
        raise RuntimeError(f"Expected 38 failed MILP keys, got {len(jobs)}")
    manifest = {"registered_at": now(), "purpose": "MILP_online_failure_replay",
                "environment": activated(), "max_workers": 1, "timeout_wall_s": 7200,
                "max_attempts_per_key": 1, "jobs": jobs,
                "formal_sha256": {name: sha(FORMAL / name) for name in ("manifest.json", "index.json")},
                "formal_audit_sha256": sha(HERE / "milp/FINAL_AUDIT.json"),
                "script_sha256": sha(SCRIPT),
                "interpretation": "Diagnostic replay only; original MILP formal results immutable"}
    check_manifest(manifest)
    write(path, manifest)
    return manifest


def worker(key):
    manifest_path = BASE / "manifest.json"
    manifest = read(manifest_path)
    item = next(x for x in manifest["jobs"] if x["key"] == key)
    target = BASE / "runs" / key
    started = time.perf_counter()
    try:
        check_manifest(manifest)
        row = evaluate("milp", item["job"])
        check_manifest(manifest)
        throughput = row["output_throughput_tokens_per_s"]
        if len(row["query_samples"]) != row["arrivals"] or throughput <= 0:
            raise RuntimeError("Invalid query population or throughput")
        row.update(status="completed", job=item["job"], campaign="milp",
                   manifest_sha256=sha(manifest_path),
                   formal_failure_sha256=item["formal_failure_sha256"],
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) / throughput,
                   elapsed_wall_s=time.perf_counter() - started, finished_at=now())
        write(target / "result.json", row)
    except BaseException as error:
        write(target / "failure.json", {"status": "failed", "job": item["job"],
              "campaign": "milp", "formal_failure_sha256": item["formal_failure_sha256"],
              "error": repr(error), "traceback": traceback.format_exc(),
              "elapsed_wall_s": time.perf_counter() - started, "finished_at": now()})
        traceback.print_exc()
        raise SystemExit(1)


def worker_alive(pid, key):
    try:
        command = " ".join(psutil.Process(pid).cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    return ("experiments.reviewer_v2.completion_20261101.replay_milp_failed" in command
            and "--worker" in command and key in command)


def queue(resume):
    manifest = register()
    index_path = BASE / "index.json"
    if index_path.exists():
        if not resume:
            raise RuntimeError("MILP replay index exists; inspect workers and use --resume")
        index = read(index_path)
        if index["status"] == "terminal":
            return
        if index["manifest_sha256"] != sha(BASE / "manifest.json"):
            raise RuntimeError("MILP replay manifest changed")
        active = [(key, state) for key, state in index["jobs"].items()
                  if state["status"] == "running"]
        for key, state in active:
            if worker_alive(state["pid"], key):
                raise RuntimeError("MILP replay worker still running: " + key)
        if active:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            recovery = BASE / ("recovery_" + stamp)
            recovery.mkdir(parents=True, exist_ok=False)
            shutil.copy2(index_path, recovery / "original_index.json")
            write(recovery / "amendment.json", {"interrupted": [key for key, _ in active],
                  "original_index_sha256": sha(recovery / "original_index.json")})
            for key, state in active:
                target = BASE / "runs" / key
                artifact = next((p for p in (target / "result.json", target / "failure.json")
                                 if p.exists()), None)
                if artifact is None:
                    artifact = target / "failure.json"
                    item = next(x for x in manifest["jobs"] if x["key"] == key)
                    write(artifact, {"status": "failed", "job": item["job"],
                          "campaign": "milp", "classification": "controller_interrupted",
                          "formal_failure_sha256": item["formal_failure_sha256"],
                          "finished_at": now()})
                state.update(status="completed" if artifact.name == "result.json" else "failed",
                             source=artifact.relative_to(ROOT).as_posix(),
                             artifact_sha256=sha(artifact), finished_at=now())
        index["controller_pid"] = os.getpid()
        write(index_path, index)
    else:
        if resume:
            raise RuntimeError("No MILP replay index to resume")
        prior = HERE / "failed_replay_retry_v2/FINAL_AUDIT.json"
        if not prior.exists() or not read(prior)["passed"]:
            raise RuntimeError("Wait for E5a/E6 bounded retry audit")
        index = {"status": "running", "controller_pid": os.getpid(),
                 "manifest_sha256": sha(BASE / "manifest.json"), "started_at": now(),
                 "jobs": {x["key"]: {"status": "pending"} for x in manifest["jobs"]}}
        write(index_path, index)
    for item in manifest["jobs"]:
        key = item["key"]
        if index["jobs"][key]["status"] != "pending":
            continue
        check_manifest(manifest)
        target = BASE / "runs" / key
        target.mkdir(parents=True, exist_ok=False)
        with (target / "worker.log").open("x", encoding="utf-8") as log:
            proc = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.completion_20261101.replay_milp_failed",
                "--worker", key], cwd=ROOT, env=dict(os.environ, **ENV),
                stdout=log, stderr=subprocess.STDOUT)
            index["jobs"][key] = {"status": "running", "pid": proc.pid, "started_at": now()}
            write(index_path, index)
            try:
                code = proc.wait(timeout=manifest["timeout_wall_s"])
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        result, failure = target / "result.json", target / "failure.json"
        artifact = result if code == 0 and result.exists() else failure
        if not artifact.exists():
            write(artifact, {"status": "failed", "job": item["job"],
                  "campaign": "milp", "classification": "native_or_abnormal_exit", "exit_code": code,
                  "formal_failure_sha256": item["formal_failure_sha256"], "finished_at": now()})
        index["jobs"][key].update(status="completed" if artifact == result else "failed",
                                  source=artifact.relative_to(ROOT).as_posix(),
                                  artifact_sha256=sha(artifact), exit_code=code,
                                  finished_at=now())
        write(index_path, index)
        print(key, index["jobs"][key]["status"], flush=True)
    check_manifest(manifest)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    else:
        queue(args.resume)


if __name__ == "__main__":
    main()

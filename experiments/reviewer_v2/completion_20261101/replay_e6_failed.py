"""Independently replay each failed E6 completion window once."""
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

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write

from .run import HERE, activated, check, evaluate

BASE = HERE / "e6_failure_replay"
FORMAL = HERE / "e6/formal"
SCRIPT = Path(__file__)


def check_manifest(manifest):
    if activated()["conda_prefix"] != manifest["environment"]["conda_prefix"]:
        raise RuntimeError("Conda environment changed")
    if sha(SCRIPT) != manifest["script_sha256"]:
        raise RuntimeError("Frozen replay script changed")
    original_manifest = FORMAL / "manifest.json"
    original_index = FORMAL / "index.json"
    if (sha(original_manifest) != manifest["formal_manifest_sha256"]
            or sha(original_index) != manifest["formal_index_sha256"]):
        raise RuntimeError("Frozen E6 formal registration changed")
    check("e6", read(original_manifest))
    for item in manifest["jobs"]:
        if sha(ROOT / item["original_failure_source"]) != item["original_failure_sha256"]:
            raise RuntimeError("Original failure changed: " + item["key"])


def register():
    path = BASE / "manifest.json"
    if path.exists():
        manifest = read(path)
        check_manifest(manifest)
        return manifest
    formal_manifest = read(FORMAL / "manifest.json")
    formal_index = read(FORMAL / "index.json")
    audit = read(HERE / "e6/FINAL_AUDIT.json")
    if (formal_index["status"] != "terminal" or not audit["passed"]
            or audit["registered"] != 60):
        raise RuntimeError("Original E6 formal campaign is not audited")
    jobs = []
    for job in formal_manifest["jobs"]:
        key = job["key"]
        state = formal_index["jobs"][key]
        if state["status"] != "failed":
            continue
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("Formal artifact SHA mismatch: " + key)
        jobs.append({"key": key, "job": job,
                     "original_failure_source": state["source"],
                     "original_failure_sha256": state["artifact_sha256"]})
    if len(jobs) != 29:
        raise RuntimeError(f"Expected 29 failed E6 keys, got {len(jobs)}")
    manifest = {"registered_at": now(), "purpose": "E6_failure_replay",
                "environment": activated(), "max_workers": 1,
                "timeout_wall_s": 7200, "jobs": jobs,
                "formal_manifest_sha256": sha(FORMAL / "manifest.json"),
                "formal_index_sha256": sha(FORMAL / "index.json"),
                "script_sha256": sha(SCRIPT),
                "failure_policy": "Original E6 formal artifacts remain immutable"}
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
        row = evaluate("e6", item["job"])
        check_manifest(manifest)
        throughput = row["output_throughput_tokens_per_s"]
        if len(row["query_samples"]) != row["arrivals"] or throughput <= 0:
            raise RuntimeError("Invalid query population or throughput")
        row.update(status="completed", job=item["job"], campaign="e6",
                   manifest_sha256=sha(manifest_path),
                   original_failure_sha256=item["original_failure_sha256"],
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values())
                   / throughput, elapsed_wall_s=time.perf_counter() - started,
                   finished_at=now())
        write(target / "result.json", row)
    except BaseException as error:
        write(target / "failure.json", {"status": "failed", "job": item["job"],
              "campaign": "e6", "original_failure_sha256":
              item["original_failure_sha256"], "error": repr(error),
              "traceback": traceback.format_exc(),
              "elapsed_wall_s": time.perf_counter() - started, "finished_at": now()})
        traceback.print_exc()
        raise SystemExit(1)


def queue(resume):
    manifest = register()
    index_path = BASE / "index.json"
    if index_path.exists():
        if not resume:
            raise RuntimeError("Replay index exists; use --resume after inspecting workers")
        index = read(index_path)
        if index["status"] == "terminal":
            return
        if index["manifest_sha256"] != sha(BASE / "manifest.json"):
            raise RuntimeError("Replay manifest changed")
        active = [(key, state) for key, state in index["jobs"].items()
                  if state["status"] == "running"]
        for key, state in active:
            listing = subprocess.run(["tasklist", "/FI", f"PID eq {state['pid']}"],
                                     capture_output=True, text=True).stdout
            if str(state["pid"]) in listing:
                raise RuntimeError("Replay worker still running: " + key)
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
                    original = next(x for x in manifest["jobs"] if x["key"] == key)
                    write(artifact, {"status": "failed", "job": original["job"],
                          "campaign": "e6", "classification": "controller_interrupted",
                          "original_failure_sha256": original["original_failure_sha256"],
                          "finished_at": now()})
                state.update(status="completed" if artifact.name == "result.json" else "failed",
                             source=artifact.relative_to(ROOT).as_posix(),
                             artifact_sha256=sha(artifact), finished_at=now())
        index["controller_pid"] = os.getpid()
        write(index_path, index)
    else:
        if resume:
            raise RuntimeError("No replay index to resume")
        if read(HERE / "e5a/formal/index.json")["status"] != "terminal":
            raise RuntimeError("Wait for E5a formal campaign to finish")
        index = {"status": "running", "controller_pid": os.getpid(),
                 "manifest_sha256": sha(BASE / "manifest.json"),
                 "started_at": now(),
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
                "experiments.reviewer_v2.completion_20261101.replay_e6_failed",
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
                  "campaign": "e6", "classification": "native_or_abnormal_exit",
                  "exit_code": code, "original_failure_sha256":
                  item["original_failure_sha256"], "finished_at": now()})
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
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.register:
        register()
    else:
        queue(args.resume)


if __name__ == "__main__":
    main()

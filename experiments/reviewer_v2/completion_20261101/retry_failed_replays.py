"""One bounded, independent second run of failed E5a/E6 replay keys."""
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

from .run import HERE, activated, evaluate
from .replay_e5a_failed import check_manifest as check_e5a
from .replay_e6_failed import check_manifest as check_e6

BASE = HERE / "failed_replay_retry_v2"
SCRIPT = Path(__file__)
PARENTS = {
    "e5a": HERE / "e5a_failure_replay",
    "e6": HERE / "e6_failure_replay",
}


def check_manifest(manifest):
    if activated() != manifest["environment"] or sha(SCRIPT) != manifest["script_sha256"]:
        raise RuntimeError("Retry environment or script changed")
    for campaign, base in PARENTS.items():
        parent = manifest["parents"][campaign]
        for name in ("manifest.json", "index.json", "FINAL_AUDIT.json"):
            if sha(base / name) != parent[name]:
                raise RuntimeError(f"Parent {campaign}/{name} changed")
        (check_e5a if campaign == "e5a" else check_e6)(read(base / "manifest.json"))
    for item in manifest["jobs"]:
        if sha(ROOT / item["parent_failure_source"]) != item["parent_failure_sha256"]:
            raise RuntimeError("Parent failure changed: " + item["key"])


def register():
    path = BASE / "manifest.json"
    if path.exists():
        manifest = read(path)
        check_manifest(manifest)
        return manifest
    parents = {}
    jobs = []
    for campaign, base in PARENTS.items():
        parent_manifest = read(base / "manifest.json")
        parent_index = read(base / "index.json")
        audit = read(base / "FINAL_AUDIT.json")
        if parent_index["status"] != "terminal" or not audit["passed"]:
            raise RuntimeError(f"Parent {campaign} is not terminal and audited")
        parents[campaign] = {name: sha(base / name) for name in
                             ("manifest.json", "index.json", "FINAL_AUDIT.json")}
        for item in parent_manifest["jobs"]:
            key = item["key"]
            state = parent_index["jobs"][key]
            if state["status"] != "failed":
                continue
            source = ROOT / state["source"]
            if sha(source) != state["artifact_sha256"]:
                raise RuntimeError("Parent artifact SHA mismatch: " + key)
            jobs.append({"key": key, "campaign": campaign, "job": item["job"],
                         "parent_failure_source": state["source"],
                         "parent_failure_sha256": state["artifact_sha256"],
                         "formal_failure_sha256": item["original_failure_sha256"]})
    if not jobs:
        raise RuntimeError("No failed replay keys to retry")
    manifest = {"registered_at": now(), "purpose": "bounded_failed_replay_retry_v2",
                "environment": activated(), "max_workers": 1, "max_attempts_per_key": 1,
                "timeout_wall_s": 7200, "jobs": jobs, "parents": parents,
                "script_sha256": sha(SCRIPT),
                "interpretation": "Diagnostic retry only; formal and first replay results immutable"}
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
        row = evaluate(item["campaign"], item["job"])
        check_manifest(manifest)
        throughput = row["output_throughput_tokens_per_s"]
        if len(row["query_samples"]) != row["arrivals"] or throughput <= 0:
            raise RuntimeError("Invalid query population or throughput")
        row.update(status="completed", job=item["job"], campaign=item["campaign"],
                   retry_campaign="failed_replay_retry_v2", manifest_sha256=sha(manifest_path),
                   parent_failure_sha256=item["parent_failure_sha256"],
                   formal_failure_sha256=item["formal_failure_sha256"],
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values())
                   / throughput, elapsed_wall_s=time.perf_counter() - started,
                   finished_at=now())
        write(target / "result.json", row)
    except BaseException as error:
        write(target / "failure.json", {"status": "failed", "job": item["job"],
              "campaign": item["campaign"], "retry_campaign": "failed_replay_retry_v2",
              "parent_failure_sha256": item["parent_failure_sha256"],
              "formal_failure_sha256": item["formal_failure_sha256"],
              "error": repr(error), "traceback": traceback.format_exc(),
              "elapsed_wall_s": time.perf_counter() - started, "finished_at": now()})
        traceback.print_exc()
        raise SystemExit(1)


def queue(resume):
    manifest = register()
    index_path = BASE / "index.json"
    if index_path.exists():
        if not resume:
            raise RuntimeError("Retry index exists; inspect workers and use --resume")
        index = read(index_path)
        if index["status"] == "terminal":
            return
        if index["manifest_sha256"] != sha(BASE / "manifest.json"):
            raise RuntimeError("Retry manifest changed")
        active = [(key, state) for key, state in index["jobs"].items()
                  if state["status"] == "running"]
        for key, state in active:
            listing = subprocess.run(["tasklist", "/FI", f"PID eq {state['pid']}"],
                                     capture_output=True, text=True).stdout
            if str(state["pid"]) in listing:
                raise RuntimeError("Retry worker still running: " + key)
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
                          "campaign": item["campaign"], "retry_campaign": "failed_replay_retry_v2",
                          "classification": "controller_interrupted",
                          "parent_failure_sha256": item["parent_failure_sha256"],
                          "formal_failure_sha256": item["formal_failure_sha256"],
                          "finished_at": now()})
                state.update(status="completed" if artifact.name == "result.json" else "failed",
                             source=artifact.relative_to(ROOT).as_posix(),
                             artifact_sha256=sha(artifact), finished_at=now())
        index["controller_pid"] = os.getpid()
        write(index_path, index)
    else:
        if resume:
            raise RuntimeError("No retry index to resume")
        index = {"status": "running", "controller_pid": os.getpid(),
                 "manifest_sha256": sha(BASE / "manifest.json"), "started_at": now(),
                 "jobs": {item["key"]: {"status": "pending"} for item in manifest["jobs"]}}
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
                "experiments.reviewer_v2.completion_20261101.retry_failed_replays",
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
                  "campaign": item["campaign"], "retry_campaign": "failed_replay_retry_v2",
                  "classification": "native_or_abnormal_exit", "exit_code": code,
                  "parent_failure_sha256": item["parent_failure_sha256"],
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

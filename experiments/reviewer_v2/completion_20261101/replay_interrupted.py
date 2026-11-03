"""Replay the three host-reboot interruptions in separate artifact paths."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write

from .run import HERE, activated, check, evaluate

BASE = HERE / "interrupted_replay"
INCIDENT = "recovery_20261101_195930"
CAMPAIGNS = ("e5a", "e6", "milp")


def check_manifest(manifest):
    if activated()["conda_prefix"] != manifest["environment"]["conda_prefix"]:
        raise RuntimeError("Conda environment changed")
    if sha(Path(__file__)) != manifest["script_sha256"]:
        raise RuntimeError("Frozen interruption replay script changed")
    for item in manifest["jobs"]:
        campaign, key = item["campaign"], item["key"]
        base = HERE / campaign / "formal"
        old_manifest_path = base / "manifest.json"
        if sha(old_manifest_path) != item["formal_manifest_sha256"]:
            raise RuntimeError("Original formal manifest changed: " + campaign)
        check(campaign, read(old_manifest_path))
        failure = ROOT / item["original_failure_source"]
        if sha(failure) != item["original_failure_sha256"]:
            raise RuntimeError("Original interruption changed: " + key)
        amendment = base / INCIDENT / "amendment.json"
        if sha(amendment) != item["recovery_amendment_sha256"]:
            raise RuntimeError("Recovery amendment changed: " + key)


def register():
    path = BASE / "manifest.json"
    if path.exists():
        manifest = read(path)
        check_manifest(manifest)
        return manifest
    jobs = []
    for campaign in CAMPAIGNS:
        base = HERE / campaign / "formal"
        amendment_path = base / INCIDENT / "amendment.json"
        amendment = read(amendment_path)
        if len(amendment["interrupted"]) != 1:
            raise RuntimeError("Expected one interrupted key: " + campaign)
        key = amendment["interrupted"][0]["key"]
        old_manifest_path = base / "manifest.json"
        old_manifest = read(old_manifest_path)
        job = next(x for x in old_manifest["jobs"] if x["key"] == key)
        state = read(base / "index.json")["jobs"][key]
        failure = ROOT / state["source"]
        original = read(failure)
        if (state["status"] != "failed" or sha(failure) != state["artifact_sha256"]
                or original.get("classification") != "controller_interrupted"
                or original.get("key") != key):
            raise RuntimeError("Original interruption not verified: " + key)
        jobs.append({"campaign": campaign, "key": key, "job": job,
                     "formal_manifest_sha256": sha(old_manifest_path),
                     "original_failure_source": state["source"],
                     "original_failure_sha256": state["artifact_sha256"],
                     "recovery_amendment_sha256": sha(amendment_path)})
    manifest = {"registered_at": now(), "purpose": "independent_host_reboot_replay",
                "environment": activated(), "jobs": jobs, "max_workers": 1,
                "script_sha256": sha(Path(__file__)),
                "timeout_wall_s": 7200,
                "failure_policy": "Original formal failures remain immutable"}
    check_manifest(manifest)
    write(path, manifest)
    return manifest


def worker(campaign, key):
    manifest_path = BASE / "manifest.json"
    manifest = read(manifest_path)
    item = next(x for x in manifest["jobs"]
                if x["campaign"] == campaign and x["key"] == key)
    target = BASE / "runs" / campaign / key
    start = time.perf_counter()
    try:
        check_manifest(manifest)
        row = evaluate(campaign, item["job"])
        check_manifest(manifest)
        if len(row["query_samples"]) != row["arrivals"]:
            raise RuntimeError("Query sample population mismatch")
        throughput = row["output_throughput_tokens_per_s"]
        if throughput <= 0:
            raise RuntimeError("Zero output throughput")
        row.update(status="completed", job=item["job"], campaign=campaign,
                   manifest_sha256=sha(manifest_path),
                   original_failure_sha256=item["original_failure_sha256"],
                   gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values())
                   / throughput, elapsed_wall_s=time.perf_counter() - start,
                   finished_at=now())
        write(target / "result.json", row)
    except BaseException as error:
        write(target / "failure.json", {"status": "failed", "job": item["job"],
              "campaign": campaign, "original_failure_sha256":
              item["original_failure_sha256"], "error": repr(error),
              "traceback": traceback.format_exc(),
              "elapsed_wall_s": time.perf_counter() - start, "finished_at": now()})
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    index_path = BASE / "index.json"
    if index_path.exists():
        raise RuntimeError("Replay index exists; inspect before recovery")
    index = {"status": "running", "controller_pid": os.getpid(),
             "manifest_sha256": sha(BASE / "manifest.json"), "started_at": now(),
             "jobs": {f"{x['campaign']}/{x['key']}": {"status": "pending"}
                      for x in manifest["jobs"]}}
    write(index_path, index)
    for item in manifest["jobs"]:
        check_manifest(manifest)
        campaign, key = item["campaign"], item["key"]
        identity = f"{campaign}/{key}"
        target = BASE / "runs" / identity
        target.mkdir(parents=True, exist_ok=False)
        with (target / "worker.log").open("x", encoding="utf-8") as log:
            proc = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.completion_20261101.replay_interrupted",
                "--worker", campaign, key], cwd=ROOT, env=dict(os.environ, **ENV),
                stdout=log, stderr=subprocess.STDOUT)
            index["jobs"][identity] = {"status": "running", "pid": proc.pid,
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
            write(artifact, {"status": "failed", "job": item["job"],
                  "campaign": campaign, "classification": "native_or_abnormal_exit",
                  "exit_code": code, "original_failure_sha256":
                  item["original_failure_sha256"], "finished_at": now()})
        index["jobs"][identity].update(
            status="completed" if artifact == result else "failed",
            source=artifact.relative_to(ROOT).as_posix(),
            artifact_sha256=sha(artifact), exit_code=code,
            finished_at=now())
        write(index_path, index)
        print(identity, index["jobs"][identity]["status"], flush=True)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker", nargs=2, metavar=("CAMPAIGN", "KEY"))
    args = parser.parse_args()
    if args.worker:
        worker(*args.worker)
    elif args.register:
        register()
    else:
        queue()


if __name__ == "__main__":
    main()

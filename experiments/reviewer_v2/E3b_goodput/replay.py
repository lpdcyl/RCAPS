"""Replay failed E3b keys once in an independent directory.

The frozen formal manifest, index, and original failure artifacts are read only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .evaluate import evaluate
from .run import ENV, HERE, ROOT, check, now, read, rel, sha, write

FORMAL = HERE / "formal"
REPLAY = HERE / "failure_replay"


def original_failures():
    manifest_path = FORMAL / "manifest.json"
    index_path = FORMAL / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    check(manifest)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Original E3b batch is not terminal or manifest differs")
    jobs = {job["key"]: job for job in manifest["jobs"]}
    failures = {}
    for key, state in index["jobs"].items():
        if state["status"] != "failed":
            continue
        artifact = ROOT / state["source"]
        if sha(artifact) != state["artifact_sha256"]:
            raise RuntimeError(f"Original failure artifact changed: {key}")
        failures[key] = dict(job=jobs[key], source=state["source"],
                             artifact_sha256=state["artifact_sha256"])
    return manifest_path, index_path, manifest, failures


def worker(key):
    manifest = read(REPLAY / "manifest.json")
    if key not in manifest["original_failures"]:
        raise RuntimeError(f"Unregistered replay key: {key}")
    check(read(FORMAL / "manifest.json"))
    original = manifest["original_failures"][key]
    if sha(ROOT / original["source"]) != original["artifact_sha256"]:
        raise RuntimeError(f"Original failure changed: {key}")
    job = original["job"]
    dest = REPLAY / "runs" / key
    start = time.perf_counter()
    try:
        row = evaluate(job["scenario"], job["load"], job["method"], job["seed"])
        check(read(FORMAL / "manifest.json"))
        row.update(status="completed", job=job, replay_manifest_sha256=sha(REPLAY / "manifest.json"),
                   elapsed_wall_s=time.perf_counter()-start, finished_at=now())
        write(dest / "result.json", row)
    except BaseException as error:
        write(dest / "failure.json", dict(status="failed", job=job, error=repr(error),
            traceback=traceback.format_exc(), replay_manifest_sha256=sha(REPLAY / "manifest.json"),
            elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def replay_one(key):
    folder = REPLAY / "runs" / key
    folder.mkdir(parents=True, exist_ok=False)
    with (folder / "worker.log").open("x", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
            "experiments.reviewer_v2.E3b_goodput.replay", "--worker", key],
            cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
        return_code = process.wait()
    result = folder / "result.json"
    artifact = result if return_code == 0 and result.exists() else folder / "failure.json"
    if not artifact.exists():
        write(artifact, dict(status="failed", job=read(REPLAY / "manifest.json")["original_failures"][key]["job"],
                             exit_code=return_code, classification="native_or_abnormal_exit", finished_at=now()))
    return key, dict(status="completed" if artifact == result else "failed", exit_code=return_code,
                     source=rel(artifact), artifact_sha256=sha(artifact), finished_at=now())


def main():
    original_manifest, original_index, source, failures = original_failures()
    if not failures:
        print("No original failures", flush=True)
        return
    if REPLAY.exists():
        raise RuntimeError("Replay directory already exists; inspect before recovery")
    manifest = dict(registered_at=now(), phase="independent_failure_replay",
        protocol=source["protocol"], original_manifest_sha256=sha(original_manifest),
        original_index_sha256=sha(original_index), original_failures=failures,
        source_hashes=source["sources_sha256"], max_workers=6,
        policy="One replay per original failed key; preserve all original results")
    write(REPLAY / "manifest.json", manifest)
    index = dict(status="running", started_at=now(), controller_pid=os.getpid(),
                 manifest_sha256=sha(REPLAY / "manifest.json"),
                 jobs={key: dict(status="pending") for key in failures})
    write(REPLAY / "index.json", index)
    with ThreadPoolExecutor(max_workers=manifest["max_workers"]) as pool:
        futures = {pool.submit(replay_one, key): key for key in failures}
        for future in as_completed(futures):
            key, state = future.result()
            index["jobs"][key] = state
            write(REPLAY / "index.json", index)
            print(key, state["status"], flush=True)
    index.update(status="terminal", finished_at=now())
    write(REPLAY / "index.json", index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    args = parser.parse_args()
    worker(args.worker) if args.worker else main()

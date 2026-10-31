"""One independent replay of original E2a failures without touching their artifacts."""
from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

from .run import ENV, HERE, ROOT, check, now, read, rel, sha, write


def main():
    original_manifest_path = HERE / "tuning/manifest.json"
    original_index_path = HERE / "tuning/index.json"
    original_manifest = read(original_manifest_path)
    check(original_manifest)
    original_index = read(original_index_path)
    if original_index["status"] != "terminal":
        raise RuntimeError("Original tuning batch must be terminal")
    jobs_by_key = {job["key"]: job for job in original_manifest["jobs"]}
    failures = [(key, value) for key, value in original_index["jobs"].items()
                if value["status"] == "failed"]
    if not failures:
        print("No E2a tuning failures to replay")
        return
    dest = HERE / "failure_replay"
    manifest_path = dest / "manifest.json"
    if manifest_path.exists() or (dest / "index.json").exists():
        raise RuntimeError("Failure replay already exists; inspect before running")
    manifest = copy.deepcopy(original_manifest)
    manifest["phase"] = "failure_replay"
    manifest["registered_at"] = now()
    manifest["jobs"] = [jobs_by_key[key] for key, _ in failures]
    manifest["original_manifest_sha256"] = sha(original_manifest_path)
    manifest["original_index_sha256"] = sha(original_index_path)
    manifest["original_failures"] = {
        key: dict(source=value["source"], artifact_sha256=value["artifact_sha256"])
        for key, value in failures}
    manifest["failure_policy"] = "Single independent replay; original failure artifacts retained"
    write(manifest_path, manifest)
    index = dict(status="running", started_at=now(), manifest_sha256=sha(manifest_path),
                 jobs={key: dict(status="pending") for key, _ in failures})
    write(dest / "index.json", index)
    for key, _ in failures:
        check(manifest)
        folder = dest / "runs" / key
        folder.mkdir(parents=True, exist_ok=False)
        log_path = folder / "worker.log"
        with log_path.open("x", encoding="utf-8") as log:
            command = [sys.executable, "-u", "-X", "faulthandler", "-c",
                       "from experiments.reviewer_v2.E2a_helix_tuning.run import worker; "
                       f"worker('failure_replay', {key!r})"]
            index["jobs"][key] = dict(status="running", started_at=now())
            write(dest / "index.json", index)
            code = subprocess.run(command, cwd=ROOT, env=dict(os.environ, **ENV),
                                  stdout=log, stderr=log).returncode
        artifact = folder / ("result.json" if code == 0 else "failure.json")
        if not artifact.exists():
            write(artifact, dict(status="failed", job=jobs_by_key[key], exit_code=code,
                                 classification="native_or_abnormal_exit", finished_at=now()))
        index["jobs"][key] = dict(status="completed" if code == 0 else "failed",
                                  exit_code=code, source=rel(artifact),
                                  artifact_sha256=sha(artifact), finished_at=now())
        write(dest / "index.json", index)
        print(key, index["jobs"][key]["status"], flush=True)
    index.update(status="terminal", finished_at=now())
    write(dest / "index.json", index)


if __name__ == "__main__":
    main()

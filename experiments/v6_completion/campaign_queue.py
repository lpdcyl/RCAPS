"""Small immutable-manifest worker queue for new V6 simulation campaigns."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, relative, sha, write


def worker(here, phase, key, evaluate):
    manifest = read(here / phase / "manifest.json")
    job = next(item for item in manifest["jobs"] if item["key"] == key)
    folder = here / phase / "runs" / key
    start = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job)
        check(manifest)
        assert len(row["query_samples"]) == row["arrivals"]
        row.update(status="completed", job=job,
                   manifest_sha256=sha(here / phase / "manifest.json"),
                   elapsed_wall_s=time.perf_counter() - start, finished_at=now())
        write(folder / "result.json", row)
    except BaseException as error:
        write(folder / "failure.json", dict(status="failed", job=job,
              error=repr(error), traceback=traceback.format_exc(),
              manifest_sha256=sha(here / phase / "manifest.json"),
              elapsed_wall_s=time.perf_counter() - start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(here, module_name, phase, workers, register, report):
    manifest = register(phase, workers)
    folder = here / phase
    index_path = folder / "index.json"
    if index_path.exists():
        index = read(index_path)
        assert index["manifest_sha256"] == sha(folder / "manifest.json")
        assert not any(entry["status"] == "running" for entry in index["jobs"].values())
    else:
        index = dict(status="running", controller_pid=os.getpid(), registered_at=now(),
                     manifest_sha256=sha(folder / "manifest.json"),
                     jobs={job["key"]: {"status": "pending"} for job in manifest["jobs"]})
    pending = [job for job in manifest["jobs"] if index["jobs"][job["key"]]["status"] == "pending"]
    active = {}
    write(index_path, index)
    while pending or active:
        while pending and len(active) < manifest["worker_limit"]:
            job = pending.pop(0)
            run_folder = folder / "runs" / job["key"]
            run_folder.mkdir(parents=True, exist_ok=False)
            log = (run_folder / "worker.log").open("x", encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                                        module_name, "--phase", phase, "--worker", job["key"]],
                                       cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
            active[job["key"]] = (process, log, time.monotonic())
            index["jobs"][job["key"]] = dict(status="running", pid=process.pid, started_at=now())
            write(index_path, index)
        for key, (process, log, started) in list(active.items()):
            code = process.poll()
            timeout = code is None and time.monotonic() - started > manifest["timeout_wall_s"]
            if timeout:
                process.kill()
                code = process.wait()
            if code is None:
                continue
            log.close()
            del active[key]
            run_folder = folder / "runs" / key
            passed = code == 0 and (run_folder / "result.json").exists()
            artifact = run_folder / ("result.json" if passed else "failure.json")
            if not artifact.exists():
                write(artifact, dict(status="failed", classification="timeout" if timeout else "abnormal_exit",
                                     exit_code=code, finished_at=now()))
            index["jobs"][key].update(status="completed" if passed else "failed", exit_code=code,
                                      source=relative(artifact), artifact_sha256=sha(artifact), finished_at=now())
            write(index_path, index)
            print("END", key, index["jobs"][key]["status"], flush=True)
        if active:
            time.sleep(2)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)
    if phase == "formal":
        report()

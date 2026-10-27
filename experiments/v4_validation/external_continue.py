"""Continue unattempted high-load external windows after user-authorized failures.

This is a new continuation protocol. The original halted queue and its failure
records remain immutable; this queue never overwrites an existing attempt and
continues dispatch after a worker failure.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from experiments.v4_formal.run import ROOT, read, write, digest, stamp
from experiments.v4_external.run import validate as validate_external

HERE = Path(__file__).resolve().parent
SOURCE_INDEX = HERE / "external_index.json"
INDEX = HERE / "external_continue_index.json"


def jobs():
    original = read(SOURCE_INDEX)
    attempted = set(original["jobs"])
    all_jobs = []
    for scenario, load in (("single", 700), ("multi", 320)):
        for method in ("swarm", "separate"):
            for seed in (0, 1, 2):
                key = f"{scenario}/load{load}/{method}/seed{seed}"
                if key not in attempted:
                    all_jobs.append({"key": key, "scenario": scenario,
                                     "load": load, "method": method, "seed": seed})
    return all_jobs


def validate():
    validate_external()
    assert SOURCE_INDEX.exists() and read(SOURCE_INDEX)["status"] == "halted"
    return jobs()


def queue():
    pending = validate()
    if INDEX.exists():
        raise RuntimeError("Continuation already registered; preserve its record")
    index = {"status": "running", "started_at": stamp(), "parent_index_sha256": digest(SOURCE_INDEX),
             "failure_policy": "continue after every worker failure; preserve all attempts",
             "jobs": {}, "pending_initial": [j["key"] for j in pending]}
    write(INDEX, index)
    active = []
    while pending or active:
        while pending and len(active) < 2:
            job = pending.pop(0)
            directory = HERE / "external_runs" / job["key"]
            directory.mkdir(parents=True, exist_ok=True)
            log = (directory / "continuation_worker.log").open("x", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, "-u", "-X", "faulthandler", "-m",
                 "experiments.v4_validation.external_high", "--phase", "one",
                 "--key", job["key"]], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            active.append((process, log, job))
            index["jobs"][job["key"]] = {"status": "running", "pid": process.pid,
                                          "started_at": stamp()}
            write(INDEX, index)
            print("START", job["key"], process.pid, flush=True)
        for process, log, job in list(active):
            code = process.poll()
            if code is None:
                continue
            log.close()
            active.remove((process, log, job))
            result = HERE / "external_runs" / job["key"] / "result.json"
            failure = result.with_name("failure.json")
            ok = code == 0 and result.exists()
            index["jobs"][job["key"]].update(
                {"status": "completed" if ok else "failed", "exit_code": code,
                 "finished_at": stamp(),
                 "result_sha256": digest(result) if ok else None,
                 "failure_sha256": digest(failure) if failure.exists() else None})
            write(INDEX, index)
            print("DONE" if ok else "FAILED", job["key"], code, flush=True)
        if active:
            time.sleep(2)
    index.update({"status": "completed", "finished_at": stamp(),
                  "pending": [j["key"] for j in pending]})
    write(INDEX, index)
    print("CONTINUATION_COMPLETED", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["queue"], required=True)
    args = parser.parse_args()
    queue()

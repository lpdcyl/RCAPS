"""One authorized second attempt, followed by previously unstarted windows."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from experiments.v4_formal import run as core

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
INDEX = HERE / "index.json"
RETRY = "C2/load160/v4/seed1"


def validate():
    core.validate()
    m = core.read(MANIFEST)
    assert core.digest(core.MANIFEST) == m["core_manifest_sha256"]
    assert core.digest(core.INDEX) == m["original_index_sha256"]
    assert core.environment() == m["environment"]
    for p, h in m["sources_sha256"].items():
        assert core.digest(core.ROOT / p) == h, p
    for p, h in m["original_failure_files_sha256"].items():
        assert core.digest(core.ROOT / p) == h, p
    assert core.digest(core.ROOT / m["predecessor_index"]) == m["predecessor_index_sha256"]
    return m


def register():
    assert not MANIFEST.exists() and not INDEX.exists(), "Recovery already registered"
    frozen = core.validate()
    old = core.read(core.INDEX)
    assert old["queue_status"] == "halted"
    predecessor_path = core.ROOT / "experiments/v4_recovery/index.json"
    predecessor = core.read(predecessor_path)
    assert predecessor["queue_status"] == "halted"
    failed = [k for k,v in predecessor["jobs"].items() if v["status"] == "failed"]
    assert failed == [RETRY]
    jobs = [j for j in frozen["jobs"] if j["key"] == RETRY]
    jobs += [j for j in frozen["jobs"] if j["key"] not in old["jobs"] and j["key"] not in predecessor["jobs"]]
    assert len(jobs) == 8
    paths = list(HERE.glob("*.py")) + [HERE / "README.md"]
    failure = core.ROOT / "experiments/v4_recovery/runs" / RETRY / "worker.log"
    core.write(MANIFEST, {
        "registered_at":core.stamp(),
        "authorization":"User: 重新运行就是. One second attempt for C2/load160/v4/seed1 and continuation of 7 unstarted cells. Both earlier failures retained.",
        "core_manifest_sha256":core.digest(core.MANIFEST),
        "original_index_sha256":core.digest(core.INDEX),
        "predecessor_index":predecessor_path.relative_to(core.ROOT).as_posix(),
        "predecessor_index_sha256":core.digest(predecessor_path),
        "original_failure_files_sha256":{failure.relative_to(core.ROOT).as_posix():core.digest(failure)},
        "environment":core.environment(),"jobs":jobs,"retry_keys":[RETRY],
        "protocol":frozen["protocol"],
        "amendment":"The explicit user-authorized second attempt overrides the original no-retry rule only for the listed failed key. No automatic repeated retries. Any new failure stops dispatch. No claim that native crash or historical TypeError is fixed.",
        "sources_sha256":{p.relative_to(core.ROOT).as_posix():core.digest(p) for p in paths}})
    print("RECOVERY_REGISTERED", len(jobs), core.digest(MANIFEST), flush=True)


def one(key):
    m = validate()
    assert key in {j["key"] for j in m["jobs"]}
    destination = HERE / "runs" / key
    assert not any((destination / n).exists() for n in ("result.json","failure.json","parity_mismatch_result.json"))
    original_write = core.write
    original_directory = core.HERE / "runs" / key

    def record(path, value):
        path = Path(path)
        assert path.parent == original_directory, "Only result output redirection is authorized"
        target = destination / path.name
        assert not target.exists(), "Never replace any attempt output"
        value = dict(value, recovery_manifest_sha256=core.digest(MANIFEST),
                     attempt_number=2 if key in m["retry_keys"] else 1,
                     recovery_authorization=m["authorization"])
        original_write(target, value)

    # Evaluation, inputs, environment and validation all remain the frozen code.
    # Only its output writer changes destination; the original attempt is untouched.
    core.write = record
    try:
        core.run_one(key)
    finally:
        core.write = original_write
    validate()


def queue():
    m = validate()
    assert not INDEX.exists(), "One controller attempt only; preserve previous index"
    index = {"manifest_sha256":core.digest(MANIFEST),"queue_pid":os.getpid(),
             "selected_windows":len(m["jobs"]),"queue_status":"running",
             "queue_started_at":core.stamp(),"jobs":{}}
    core.write(INDEX,index)
    pending, active, halted = list(m["jobs"]), [], False
    while pending or active:
        limit = 2 if index["jobs"].get(RETRY,{}).get("status") == "completed" else 1
        while pending and len(active) < limit and not halted:
            validate()
            job = pending.pop(0)
            key = job["key"]
            directory = HERE / "runs" / key
            directory.mkdir(parents=True,exist_ok=True)
            log = (directory / "worker.log").open("x",encoding="utf-8")
            cmd = [sys.executable,"-u","-X","faulthandler","-m","experiments.v4_recovery2.run","one","--key",key]
            proc = subprocess.Popen(cmd,cwd=core.ROOT,stdout=log,stderr=subprocess.STDOUT)
            active.append((proc,log,key))
            index["jobs"][key] = {"status":"running","pid":proc.pid,"started_at":core.stamp(),
                                  "command":cmd,"attempt_number":2 if key == RETRY else 1}
            core.write(INDEX,index)
            print("START",key,proc.pid,flush=True)
        for proc,log,key in list(active):
            code = proc.poll()
            if code is None:
                continue
            log.close()
            active.remove((proc,log,key))
            output = HERE / "runs" / key / "result.json"
            ok = code == 0 and output.exists()
            index["jobs"][key].update(status="completed" if ok else "failed",exit_code=code,
                                      finished_at=core.stamp(),result_sha256=core.digest(output) if ok else None)
            halted |= not ok
            index["queue_status"] = "halting_after_failure" if halted else "running"
            core.write(INDEX,index)
            print("DONE" if ok else "FAILED",key,code,flush=True)
        if halted and not active:
            break
        if active:
            time.sleep(2)
    index.update(queue_status="halted" if halted else "completed",queue_finished_at=core.stamp(),unstarted_windows=len(pending))
    core.write(INDEX,index)
    if halted:
        raise SystemExit("Recovery stopped after preserved failure; no automatic retry")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("register","validate","queue","one"))
    parser.add_argument("--key")
    args = parser.parse_args()
    if args.phase == "one": one(args.key)
    elif args.phase == "register": register()
    elif args.phase == "queue": queue()
    else: print("RECOVERY_VALID",len(validate()["jobs"]))

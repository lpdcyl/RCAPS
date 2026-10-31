"""Independent replay; preserve original V4 seed 3/4 failures and frozen runner."""
import argparse
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v4_paper_seed45 import run as base

OUT = Path(__file__).resolve().parent / "retry_env"
MANIFEST = OUT / "manifest.json"
INDEX = OUT / "index.json"


def register():
    source = base.check_manifest()
    old = base.read(base.INDEX)
    if old["status"] != "terminal":
        raise RuntimeError("Original batch still running")
    if not MANIFEST.exists():
        jobs = []
        for job in source["jobs"]:
            entry = old["jobs"][job["key"]]
            if entry["status"] == "failed":
                path = base.ROOT / entry["source"]
                if base.sha(path) != entry["artifact_sha256"]:
                    raise RuntimeError("Original failure changed")
                jobs.append({"job": job, "original_failure": entry["source"],
                             "original_failure_sha256": entry["artifact_sha256"]})
        base.write(MANIFEST, {"registered_at": base.stamp(), "jobs": jobs,
                "original_manifest_sha256": base.sha(base.MANIFEST),
                "original_index_sha256": base.sha(base.INDEX),
                "amendment": "Restore MPLBACKEND after simulator sets Agg; no simulator inputs changed"})
    return check()


def check():
    source = base.check_manifest()
    manifest = base.read(MANIFEST)
    if base.sha(base.MANIFEST) != manifest["original_manifest_sha256"] or base.sha(base.INDEX) != manifest["original_index_sha256"]:
        raise RuntimeError("Frozen original manifest or index changed")
    for item in manifest["jobs"]:
        if base.sha(base.ROOT / item["original_failure"]) != item["original_failure_sha256"]:
            raise RuntimeError("Original failure changed")
    if base.environment() != source["environment"]:
        raise RuntimeError("Startup environment differs from frozen manifest")
    return manifest


def worker(key):
    manifest = check()
    job = next(item["job"] for item in manifest["jobs"] if item["job"]["key"] == key)
    folder = OUT / "runs" / key
    if (folder / "result.json").exists() or (folder / "failure.json").exists():
        raise RuntimeError("Replay already attempted")
    t = time.perf_counter()
    initial = os.environ.get("MPLBACKEND")
    try:
        row = base.evaluate(job)
        row["environment_after_evaluation"] = base.environment()
        if initial is None:
            os.environ.pop("MPLBACKEND", None)
        else:
            os.environ["MPLBACKEND"] = initial
        check()
        row["replay_amendment"] = manifest["amendment"]
        row["elapsed_wall_s"] = time.perf_counter() - t
        base.write(folder / "result.json", row)
    except BaseException as exc:
        base.write(folder / "failure.json", {"status": "failed", "job": job,
                   "error": repr(exc), "traceback": traceback.format_exc(),
                   "elapsed_wall_s": time.perf_counter() - t, "finished_at": base.stamp()})
        raise


def queue():
    manifest = register()
    if INDEX.exists():
        raise RuntimeError("Replay queue already started")
    index = {"status": "running", "manifest_sha256": base.sha(MANIFEST),
             "jobs": {item["job"]["key"]: {"status": "pending"} for item in manifest["jobs"]}}
    base.write(INDEX, index)
    pending = list(manifest["jobs"])
    active = {}
    while pending or active:
        while pending and len(active) < 2:
            item = pending.pop(0)
            key = item["job"]["key"]
            folder = OUT / "runs" / key
            folder.mkdir(parents=True, exist_ok=True)
            log = (folder / "worker.log").open("x", encoding="utf-8")
            proc = subprocess.Popen([sys.executable, "-u", "-m", "experiments.v4_paper_seed45.replay_env", "--worker", key],
                                    cwd=base.ROOT, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT)
            active[key] = (proc, log)
            index["jobs"][key] = {"status": "running", "pid": proc.pid, "started_at": base.stamp()}
            base.write(INDEX, index)
            print("START", key, proc.pid, flush=True)
        for key, (proc, log) in list(active.items()):
            code = proc.poll()
            if code is None:
                continue
            log.close()
            del active[key]
            folder = OUT / "runs" / key
            result, failure = folder / "result.json", folder / "failure.json"
            if code == 0 and result.exists():
                path, status = result, "completed"
            elif failure.exists():
                path, status = failure, "failed"
            else:
                path, status = failure, "failed"
                base.write(failure, {"status": "failed", "classification": "native_process_exit",
                                     "exit_code": code, "finished_at": base.stamp()})
            index["jobs"][key] = {"status": status, "exit_code": code,
                                   "source": path.relative_to(base.ROOT).as_posix(),
                                   "artifact_sha256": base.sha(path), "finished_at": base.stamp()}
            base.write(INDEX, index)
            print("END", key, status, code, flush=True)
        if active:
            time.sleep(2)
    index["status"] = "terminal"
    index["finished_at"] = base.stamp()
    base.write(INDEX, index)
    base.write(OUT / "FINAL_AUDIT.json", {"passed": True, "replays": len(manifest["jobs"]),
               "counts": dict(Counter(x["status"] for x in index["jobs"].values())),
               "original_manifest_sha256": base.sha(base.MANIFEST),
               "original_index_sha256": base.sha(base.INDEX),
               "replay_manifest_sha256": base.sha(MANIFEST), "replay_index_sha256": base.sha(INDEX)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.wait:
        base.check_manifest()
        while base.read(base.INDEX)["status"] != "terminal":
            time.sleep(30)
        queue()
    elif args.queue:
        queue()
    else:
        parser.error("choose --wait, --queue, or --worker")

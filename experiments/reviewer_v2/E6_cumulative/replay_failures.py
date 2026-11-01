"""Serial, independent replay of E6 formal failures; original batch is read-only."""
import argparse
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write
from . import run

HERE = Path(__file__).resolve().parent
BATCH = HERE / "failure_replay"
MANIFEST = BATCH / "manifest.json"
INDEX = BATCH / "index.json"
FORMAL = HERE / "formal"


def activated():
    prefix = Path(os.environ.get("CONDA_PREFIX", "")).resolve()
    if (os.environ.get("CONDA_DEFAULT_ENV") != "gllm" or prefix.name.lower() != "gllm"
            or Path(sys.executable).resolve().parent != prefix):
        raise RuntimeError("Activate conda gllm before E6 replay")


def register():
    activated()
    if MANIFEST.exists() or INDEX.exists() or BATCH.exists():
        raise RuntimeError("Replay registration exists; inspect it, do not overwrite")
    original = read(FORMAL / "index.json")
    if original["status"] != "terminal" or original["manifest_sha256"] != sha(FORMAL / "manifest.json"):
        raise RuntimeError("Original E6 formal batch not terminal or changed")
    failed = []
    for key, state in original["jobs"].items():
        if state["status"] != "failed":
            continue
        source = ROOT / state["source"]
        if sha(source) != state["artifact_sha256"]:
            raise RuntimeError("Original failure artifact changed: " + key)
        failed.append({"key": key, "job": read(source)["job"], "original_source": state["source"],
                       "original_sha256": state["artifact_sha256"]})
    if len(failed) != 13:
        raise RuntimeError(f"Expected 13 original failed jobs, found {len(failed)}")
    BATCH.mkdir()
    write(MANIFEST, {"formal_manifest_sha256": sha(FORMAL / "manifest.json"),
        "formal_index_sha256": sha(FORMAL / "index.json"),
        "formal_source_sha256": sha(HERE / "run.py"),
        "policy": "independent serial replay; original formal untouched", "jobs": failed})
    write(INDEX, {"status": "registered", "manifest_sha256": sha(MANIFEST),
                  "jobs": {j["key"]: {"status": "pending"} for j in failed}})


def verify():
    activated()
    manifest = read(MANIFEST)
    original = read(FORMAL / "index.json")
    if (sha(MANIFEST) != read(INDEX)["manifest_sha256"]
            or manifest["formal_manifest_sha256"] != sha(FORMAL / "manifest.json")
            or manifest["formal_index_sha256"] != sha(FORMAL / "index.json")
            or manifest["formal_source_sha256"] != sha(HERE / "run.py")
            or original["status"] != "terminal"):
        raise RuntimeError("Frozen E6 lineage changed")
    for item in manifest["jobs"]:
        if sha(ROOT / item["original_source"]) != item["original_sha256"]:
            raise RuntimeError("Original failure changed: " + item["key"])
    return manifest


def worker(key):
    manifest = verify()
    item = next(x for x in manifest["jobs"] if x["key"] == key)
    job = item["job"]
    folder = BATCH / "runs" / key
    start = time.perf_counter()
    try:
        run.check(read(FORMAL / "manifest.json"), FORMAL / "manifest.json")
        from benchmarks.layout import scenario as physical
        from experiments.v5_core_supplement.run import paths
        from rcaps.v4_method import evaluate_variant
        scenario = job["scenario"]
        solution, cluster, _ = paths(scenario, "RR")
        config = read(FORMAL / "manifest.json")["stages"][job["stage"]]
        row = evaluate_variant(scenario, job["load"], job["duration_s"], 0, job["seed"],
            solution, cluster, physical_cluster=physical(scenario)[0],
            admission=config["admission"], chunk_bytes=config["chunk_bytes"],
            routing_state=config["routing_state"], mechanism=True)
        if len(row["query_samples"]) != row["arrivals"] or not row["output_throughput_tokens_per_s"]:
            raise RuntimeError("Missing request samples or zero output")
        row.update(status="completed", job=job, origin="E6_independent_failure_replay",
            original_failure_sha256=item["original_sha256"],
            trace_sha256=row["trace_sha256"], solution_sha256=sha(solution),
            sim_cluster_sha256=sha(cluster), physical_cluster_sha256=sha(physical(scenario)[0]),
            gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"],
            formal_manifest_sha256=sha(FORMAL / "manifest.json"),
            replay_manifest_sha256=sha(MANIFEST), finished_at=now(),
            elapsed_wall_s=time.perf_counter() - start)
        write(folder / "result.json", row)
    except BaseException as error:
        write(folder / "failure.json", {"status": "failed", "job": job,
            "error": repr(error), "traceback": traceback.format_exc(),
            "origin": "E6_independent_failure_replay",
            "original_failure_sha256": item["original_sha256"],
            "replay_manifest_sha256": sha(MANIFEST), "finished_at": now(),
            "elapsed_wall_s": time.perf_counter() - start})
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = verify()
    index = read(INDEX)
    if index["status"] != "registered":
        raise RuntimeError("Replay already started; inspect index")
    index["status"] = "running"
    index["controller_pid"] = os.getpid()
    write(INDEX, index)
    for item in manifest["jobs"]:
        key = item["key"]
        folder = BATCH / "runs" / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "worker.log").open("x", encoding="utf-8") as stream:
            proc = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.E6_cumulative.replay_failures", "--worker", key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=stream, stderr=subprocess.STDOUT)
            index["jobs"][key] = {"status": "running", "pid": proc.pid, "started_at": now()}
            write(INDEX, index)
            try:
                code = proc.wait(timeout=7200)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        result, failure = folder / "result.json", folder / "failure.json"
        artifact = result if code == 0 and result.exists() else failure
        if not artifact.exists():
            write(artifact, {"status": "failed", "job": item["job"],
                "classification": "native_or_abnormal_exit", "exit_code": code,
                "original_failure_sha256": item["original_sha256"], "finished_at": now()})
        index["jobs"][key].update(status="completed" if artifact == result else "failed",
            exit_code=code, source=artifact.relative_to(ROOT).as_posix(),
            artifact_sha256=sha(artifact), finished_at=now())
        write(INDEX, index)
        print(key, index["jobs"][key]["status"], flush=True)
    index.update(status="terminal", finished_at=now(),
        summary=dict(Counter(x["status"] for x in index["jobs"].values())))
    write(INDEX, index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.register:
        register()
    elif args.worker:
        worker(args.worker)
    else:
        queue()

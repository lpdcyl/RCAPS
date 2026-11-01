"""Run one unresolved E6 key in a new directory after replay audit."""
import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write
from . import replay_failures as replay, run

HERE = Path(__file__).resolve().parent
AUDIT = HERE / "failure_replay/FINAL_AUDIT.json"


def verified_key(key):
    replay.activated()
    audit = read(AUDIT)
    index = read(replay.INDEX)
    if (not audit["passed"] or index["status"] != "terminal"
            or audit["replay_index_sha256"] != sha(replay.INDEX)):
        raise RuntimeError("E6 replay has not passed its final audit")
    row = next((r for r in audit["rows"] if r["key"] == key), None)
    if row is None or row["replay_status"] != "failed":
        raise RuntimeError("Key is not an audited unresolved E6 failure: " + key)
    if sha(ROOT / row["replay_source"]) != row["replay_sha256"]:
        raise RuntimeError("E6 replay lineage changed")
    replay.verify()
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--internal", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    row = verified_key(args.key)
    dest = args.output.resolve()
    if not dest.is_relative_to(ROOT / "experiments"):
        raise RuntimeError("Output must be inside this project's experiments directory")
    folder = dest / "runs" / args.key
    if args.internal:
        from benchmarks.layout import scenario as physical
        from experiments.v5_core_supplement.run import paths
        from rcaps.v4_method import evaluate_variant
        frozen = read(replay.FORMAL / "manifest.json")
        job = next(x["job"] for x in frozen["jobs"] if x["key"] == args.key)
        scenario = job["scenario"]
        config = frozen["stages"][job["stage"]]
        solution, cluster, _ = paths(scenario, "RR")
        start = time.perf_counter()
        try:
            run.check(frozen, replay.FORMAL / "manifest.json")
            result = evaluate_variant(scenario, job["load"], job["duration_s"], 0,
                job["seed"], solution, cluster, physical_cluster=physical(scenario)[0],
                admission=config["admission"], chunk_bytes=config["chunk_bytes"],
                routing_state=config["routing_state"], mechanism=True)
            if (len(result["query_samples"]) != result["arrivals"]
                    or not result["output_throughput_tokens_per_s"]):
                raise RuntimeError("Missing request samples or zero output")
            reference = frozen["old_rows"][f"{scenario}/load{job['load']}/V4/seed{job['seed']}"]
            if (result["trace_sha256"] != reference["trace_sha256"]
                    or sha(solution) != reference["solution_sha256"]
                    or sha(cluster) != reference["sim_cluster_sha256"]):
                raise RuntimeError("Trace or deployment changed")
            result.update(status="completed", job=job, origin="E6_manual_independent_rerun",
                original_failure_sha256=row["original_sha256"],
                previous_replay_failure_sha256=row["replay_sha256"],
                gpu_seconds_per_output_token=sum(result["gpu_busy_fraction"].values()) / result["output_throughput_tokens_per_s"],
                finished_at=now(), elapsed_wall_s=time.perf_counter() - start)
            write(folder / "result.json", result)
        except BaseException as error:
            write(folder / "failure.json", {"status": "failed", "job": job,
                "error": repr(error), "traceback": traceback.format_exc(),
                "origin": "E6_manual_independent_rerun", "finished_at": now(),
                "original_failure_sha256": row["original_sha256"],
                "previous_replay_failure_sha256": row["replay_sha256"]})
            traceback.print_exc()
            raise SystemExit(1)
        return
    if dest.exists():
        raise RuntimeError("Output directory exists: " + str(dest))
    if args.validate_only:
        print({"valid": True, "key": args.key, "output": str(dest)})
        return
    folder.mkdir(parents=True, exist_ok=False)
    write(dest / "lineage.json", {"key": args.key, "original_sha256": row["original_sha256"],
        "replay_sha256": row["replay_sha256"], "replay_audit_sha256": sha(AUDIT),
        "conda_prefix": os.environ["CONDA_PREFIX"], "executable": sys.executable,
        "started_at": now()})
    cmd = [sys.executable, "-u", "-X", "faulthandler", "-m",
           "experiments.reviewer_v2.E6_cumulative.manual_rerun", "--key", args.key,
           "--output", str(dest), "--internal"]
    with (folder / "worker.log").open("x", encoding="utf-8") as stream:
        code = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, **ENV),
                              stdout=stream, stderr=subprocess.STDOUT).returncode
    result, failure = folder / "result.json", folder / "failure.json"
    artifact = result if code == 0 and result.exists() else failure
    if not artifact.exists():
        write(artifact, {"status": "failed", "key": args.key, "classification":
            "native_or_abnormal_exit", "exit_code": code, "finished_at": now()})
    write(dest / "index.json", {"key": args.key,
        "status": "completed" if artifact == result else "failed",
        "artifact": artifact.relative_to(dest).as_posix(), "artifact_sha256": sha(artifact),
        "original_sha256": row["original_sha256"],
        "replay_sha256": row["replay_sha256"], "exit_code": code, "finished_at": now()})
    print(read(dest / "index.json"))
    if artifact != result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

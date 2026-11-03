"""Run one audited, still-failed completion key into a fresh directory."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write

from .run import HERE, activated, evaluate
from .retry_failed_replays import check_manifest as check_retry
from .replay_milp_failed import check_manifest as check_milp


SOURCES = {
    "e5a": (HERE / "failed_replay_retry_v2", HERE / "e5a/formal"),
    "e6": (HERE / "failed_replay_retry_v2", HERE / "e6/formal"),
    "milp": (HERE / "milp_failure_replay", HERE / "milp/formal"),
}


def selected(campaign: str, key: str):
    replay_base, formal_base = SOURCES[campaign]
    manifest_path = replay_base / "manifest.json"
    index_path = replay_base / "index.json"
    audit_path = replay_base / "FINAL_AUDIT.json"
    manifest, index, audit = read(manifest_path), read(index_path), read(audit_path)
    (check_milp if campaign == "milp" else check_retry)(manifest)
    if (index["status"] != "terminal" or not audit["passed"]
            or audit["index_sha256"] != sha(index_path)
            or index["manifest_sha256"] != sha(manifest_path)):
        raise RuntimeError("Independent source is not terminal and audited")
    items = [item for item in manifest["jobs"] if item["key"] == key
             and (campaign == "milp" or item["campaign"] == campaign)]
    if len(items) != 1:
        raise RuntimeError("Key is not registered exactly once")
    item = items[0]
    state = index["jobs"][key]
    if state["status"] != "failed" or sha(ROOT / state["source"]) != state["artifact_sha256"]:
        raise RuntimeError("Latest failure is absent or changed")
    formal_index_path = formal_base / "index.json"
    formal_index = read(formal_index_path)
    formal_state = formal_index["jobs"][key]
    if (formal_index["status"] != "terminal" or formal_state["status"] != "failed"
            or sha(ROOT / formal_state["source"]) != formal_state["artifact_sha256"]):
        raise RuntimeError("Original formal failure is absent or changed")
    if item["formal_failure_sha256"] != formal_state["artifact_sha256"]:
        raise RuntimeError("Formal lineage changed")
    return item, state, formal_state, {"manifest": sha(manifest_path),
                                      "index": sha(index_path), "audit": sha(audit_path),
                                      "formal_index": sha(formal_index_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", choices=SOURCES, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--internal", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    activated()
    item, state, formal, source_sha = selected(args.campaign, args.key)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "experiments"):
        raise RuntimeError("Output must be inside the project experiments directory")
    if args.validate_only:
        if output.exists():
            raise RuntimeError("Output already exists")
        print({"valid": True, "campaign": args.campaign, "key": args.key,
               "output": str(output)})
        return
    if args.internal:
        started = time.perf_counter()
        try:
            row = evaluate(args.campaign, item["job"])
            selected(args.campaign, args.key)
            if (len(row.get("query_samples", {})) != row.get("arrivals")
                    or row.get("output_throughput_tokens_per_s", 0) <= 0):
                raise RuntimeError("Invalid query population or throughput")
            row.update(status="completed", job=item["job"], campaign=args.campaign,
                       origin="manual_independent_failure_key", source_sha256=source_sha,
                       formal_failure_sha256=formal["artifact_sha256"],
                       prior_failure_sha256=state["artifact_sha256"],
                       elapsed_wall_s=time.perf_counter() - started, finished_at=now())
            write(output / "result.json", row)
        except BaseException as error:
            write(output / "failure.json", {"status": "failed", "job": item["job"],
                  "campaign": args.campaign, "origin": "manual_independent_failure_key",
                  "source_sha256": source_sha,
                  "formal_failure_sha256": formal["artifact_sha256"],
                  "prior_failure_sha256": state["artifact_sha256"],
                  "error": repr(error), "traceback": traceback.format_exc(),
                  "elapsed_wall_s": time.perf_counter() - started, "finished_at": now()})
            traceback.print_exc()
            raise SystemExit(1)
        return
    output.mkdir(parents=True, exist_ok=False)
    write(output / "lineage.json", {"campaign": args.campaign, "key": args.key,
          "job": item["job"], "source_sha256": source_sha,
          "formal_failure": formal, "prior_failure": state,
          "script_sha256": sha(Path(__file__)), "environment": activated(),
          "started_at": now()})
    command = [sys.executable, "-u", "-X", "faulthandler", "-m",
               "experiments.reviewer_v2.completion_20261101.manual_failed_key",
               "--campaign", args.campaign, "--key", args.key,
               "--output", str(output), "--internal"]
    with (output / "worker.log").open("x", encoding="utf-8") as stream:
        process = subprocess.run(command, cwd=ROOT, env=dict(os.environ, **ENV),
                                 stdout=stream, stderr=subprocess.STDOUT)
    result, failure = output / "result.json", output / "failure.json"
    artifact = result if process.returncode == 0 and result.exists() else failure
    if not artifact.exists():
        write(artifact, {"status": "failed", "job": item["job"],
              "campaign": args.campaign, "origin": "manual_independent_failure_key",
              "classification": "native_or_abnormal_exit", "exit_code": process.returncode,
              "source_sha256": source_sha,
              "formal_failure_sha256": formal["artifact_sha256"],
              "prior_failure_sha256": state["artifact_sha256"], "finished_at": now()})
    status = "completed" if artifact == result else "failed"
    write(output / "index.json", {"campaign": args.campaign, "key": args.key,
          "status": status, "exit_code": process.returncode,
          "artifact": artifact.name, "artifact_sha256": sha(artifact),
          "lineage_sha256": sha(output / "lineage.json"), "finished_at": now()})
    print({"campaign": args.campaign, "key": args.key, "status": status,
           "output": str(output), "exit_code": process.returncode})
    if status == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

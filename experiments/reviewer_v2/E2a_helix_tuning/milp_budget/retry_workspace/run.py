"""Replay the four MILP budget jobs with separate empty layout workspaces."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from experiments.v3_search_efficiency.worker import ROOT, run_helix
from experiments.reviewer_v2.E2a_helix_tuning.milp_budget.run import (
    ENV, HERE as PARENT, check, read, register, sha, write,
)

HERE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def prepare():
    original_manifest_path = PARENT / "formal/manifest.json"
    original_index_path = PARENT / "formal/index.json"
    original = read(original_manifest_path)
    check(original)
    index = read(original_index_path)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(original_manifest_path):
        raise RuntimeError("Original MILP formal batch is not terminal")
    failures = {}
    for job in original["jobs"]:
        key = job["key"]
        state = index["jobs"][key]
        if state["status"] != "failed" or sha(ROOT/state["source"]) != state["artifact_sha256"]:
            raise RuntimeError("Original failure missing or changed: "+key)
        if "Workspace path is not empty!" not in read(ROOT/state["source"]).get("error", ""):
            raise RuntimeError("Unexpected original failure: "+key)
        failures[key] = dict(source=state["source"], artifact_sha256=state["artifact_sha256"])
    return original_manifest_path, original_index_path, original, failures


def worker(key):
    from simulator.initial_layout.ilp_layout.ilp_layout import ILPLayout

    manifest = read(HERE/"formal/manifest.json")
    original = read(PARENT/"formal/manifest.json")
    check(original)
    if sha(PARENT/"formal/manifest.json") != manifest["original_manifest_sha256"]:
        raise RuntimeError("Original manifest changed")
    job = next(x for x in manifest["jobs"] if x["key"] == key)
    original_search = ILPLayout.search_layout
    budget = job["callback_budget_s"]
    def patched(self, max_run_time, early_stop_threshold, early_stop_time, *args, **kwargs):
        if (max_run_time, early_stop_threshold, early_stop_time) != (36000, 0.95, 100):
            raise RuntimeError("Original Helix policy changed")
        return original_search(self, budget, early_stop_threshold, early_stop_time, *args, **kwargs)
    folder = HERE/"formal/runs"/key
    layout = folder/"layout"
    started = time.perf_counter()
    try:
        with patch.object(ILPLayout, "search_layout", patched):
            result = run_helix(job["case"], layout, solver_budget_s=None)
        result.update(job=job, callback_budget_s=budget,
                      replay_manifest_sha256=sha(HERE/"formal/manifest.json"),
                      elapsed_wall_s=time.perf_counter()-started, finished_at=now())
        check(original)
        write(folder/"result.json", result)
        if result["status"] != "passed":
            raise SystemExit(2)
    except SystemExit:
        raise
    except BaseException as error:
        write(folder/"failure.json", dict(status="failed", job=job,error=repr(error),
            traceback=traceback.format_exc(),elapsed_wall_s=time.perf_counter()-started,finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def main():
    orig_path, idx_path, original, failures = prepare()
    manifest_path = HERE/"formal/manifest.json"
    index_path = HERE/"formal/index.json"
    if manifest_path.exists() or index_path.exists():
        raise RuntimeError("Replay already exists; inspect before recovery")
    manifest = dict(registered_at=now(), original_manifest_sha256=sha(orig_path),
        original_index_sha256=sha(idx_path), original_failures=failures,
        jobs=original["jobs"],callback_budgets_s=[120,480],
        fix="empty layout subdirectory; logs outside",
        sources_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in (
            Path(__file__), HERE/"PLAN_CN.md")})
    write(manifest_path, manifest)
    index=dict(status="running",started_at=now(),controller_pid=os.getpid(),
               manifest_sha256=sha(manifest_path),jobs={j["key"]:dict(status="pending") for j in manifest["jobs"]})
    write(index_path,index)
    for job in manifest["jobs"]:
        check(original)
        key=job["key"]
        folder=HERE/"formal/runs"/key
        folder.mkdir(parents=True,exist_ok=False)
        index["jobs"][key]=dict(status="running",started_at=now())
        write(index_path,index)
        cmd=[sys.executable,"-u","-X","faulthandler","-m",
             "experiments.reviewer_v2.E2a_helix_tuning.milp_budget.retry_workspace.run","--worker",key]
        started=time.perf_counter()
        with (folder/"stdout.txt").open("x",encoding="utf-8") as out, (
             folder/"stderr.txt").open("x",encoding="utf-8") as err:
            try:
                code=subprocess.run(cmd,cwd=ROOT,env=dict(os.environ,**ENV),stdout=out,stderr=err,
                    timeout=job["external_timeout_s"]).returncode
                timeout=False
            except subprocess.TimeoutExpired:
                code,timeout=None,True
        result=folder/"result.json"
        failure=folder/"failure.json"
        passed=code==0 and result.exists() and read(result)["status"]=="passed"
        artifact=result if passed else failure if failure.exists() else result
        if not artifact.exists():
            write(failure,dict(status="failed",job=job,exit_code=code,
                classification="external_timeout" if timeout else "native_or_abnormal_exit",finished_at=now()))
            artifact=failure
        index["jobs"][key]=dict(status="completed" if passed else "failed",
            exit_code=code,timed_out=timeout,source=artifact.relative_to(ROOT).as_posix(),
            artifact_sha256=sha(artifact),stdout_sha256=sha(folder/"stdout.txt"),
            stderr_sha256=sha(folder/"stderr.txt"),elapsed_wall_s=time.perf_counter()-started,finished_at=now())
        write(index_path,index)
        print(key,index["jobs"][key]["status"],flush=True)
    index.update(status="terminal",finished_at=now())
    write(index_path,index)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker")
    args=parser.parse_args()
    worker(args.worker) if args.worker else main()

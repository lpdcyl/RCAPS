"""Independent, frozen Helix ILP callback budget diagnosis."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from experiments.v3_search_efficiency.worker import HELIX, ROOT, run_helix

HERE = Path(__file__).resolve().parent
ENV = dict(PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg",
           OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
JOBS = [dict(key=f"{case}/{budget}", case=case, callback_budget_s=budget,
             external_timeout_s=budget+180)
        for case in ("C1_single", "C1_multi") for budget in (120, 480)]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    part.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sources():
    paths = [HERE / "PLAN_CN.md", Path(__file__), ROOT / "experiments/v3_search_efficiency/worker.py",
             ROOT / "simulator/initial_layout/ilp_layout/ilp_layout.py",
             ROOT / "simulator/initial_layout/layout_synthesizer.py",
             ROOT / "rcaps/v3/planning_inputs.json"]
    for case in HELIX.values():
        paths.extend(case[k] for k in ("script", "physical", "profile", "warm_start"))
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}


def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT/name) != digest:
            raise RuntimeError("Frozen MILP input changed: "+name)


def register():
    path = HERE / "formal/manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    manifest = dict(registered_at=now(), purpose="offline_milp_budget_diagnosis_only",
        jobs=JOBS, early_stop_time_s=100, early_stop_threshold=0.95,
        same_original_gurobi_model=True, gurobi_TimeLimit=None,
        original_0995_upper_bound_callback=True,
        environment=dict(executable=sys.executable, python=sys.version,
                         gurobipy=importlib.metadata.version("gurobipy"), env=ENV),
        sources_sha256=sources())
    write(path, manifest)
    return manifest


def worker(key):
    from simulator.initial_layout.ilp_layout.ilp_layout import ILPLayout

    manifest = read(HERE / "formal/manifest.json")
    check(manifest)
    job = next(x for x in manifest["jobs"] if x["key"] == key)
    budget = job["callback_budget_s"]
    original = ILPLayout.search_layout

    def callback_budget(self, max_run_time, early_stop_threshold, early_stop_time, *args, **kwargs):
        if (max_run_time != 36000 or early_stop_threshold != 0.95 or early_stop_time != 100):
            raise RuntimeError("Unexpected original Helix callback settings")
        return original(self, budget, early_stop_threshold, early_stop_time, *args, **kwargs)

    folder = HERE / "formal/runs" / key
    started = time.perf_counter()
    try:
        with patch.object(ILPLayout, "search_layout", callback_budget):
            result = run_helix(job["case"], folder, solver_budget_s=None)
        result.update(status=result["status"], job=job, callback_budget_s=budget,
                      formal_manifest_sha256=sha(HERE / "formal/manifest.json"),
                      elapsed_wall_s=time.perf_counter()-started, finished_at=now())
        check(manifest)
        write(folder / "result.json", result)
        if result["status"] != "passed":
            raise SystemExit(2)
    except SystemExit:
        raise
    except BaseException as error:
        write(folder / "failure.json", dict(status="failed", job=job, error=repr(error),
            traceback=traceback.format_exc(), elapsed_wall_s=time.perf_counter()-started, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def main():
    manifest = register()
    index_path = HERE / "formal/index.json"
    if index_path.exists():
        raise RuntimeError("MILP index already exists; inspect before recovery")
    index = dict(status="running", started_at=now(), controller_pid=os.getpid(),
                 manifest_sha256=sha(HERE / "formal/manifest.json"),
                 jobs={j["key"]:dict(status="pending") for j in manifest["jobs"]})
    write(index_path, index)
    for job in manifest["jobs"]:
        check(manifest)
        key = job["key"]
        folder = HERE / "formal/runs" / key
        folder.mkdir(parents=True, exist_ok=False)
        index["jobs"][key] = dict(status="running", started_at=now())
        write(index_path, index)
        cmd = [sys.executable, "-u", "-X", "faulthandler", "-m",
               "experiments.reviewer_v2.E2a_helix_tuning.milp_budget.run", "--worker", key]
        started = time.perf_counter()
        with (folder/"stdout.txt").open("x",encoding="utf-8") as stdout, (
                folder/"stderr.txt").open("x",encoding="utf-8") as stderr:
            try:
                code = subprocess.run(cmd,cwd=ROOT,env=dict(os.environ,**ENV),
                    stdout=stdout,stderr=stderr,timeout=job["external_timeout_s"]).returncode
                timed_out=False
            except subprocess.TimeoutExpired:
                code, timed_out = None, True
        result = folder/"result.json"
        failure = folder/"failure.json"
        passed = code == 0 and result.exists() and read(result)["status"] == "passed"
        artifact = result if passed else failure if failure.exists() else result
        if not artifact.exists():
            write(failure,dict(status="failed",job=job,exit_code=code,
                 classification="external_timeout" if timed_out else "native_or_abnormal_exit",
                 elapsed_wall_s=time.perf_counter()-started,finished_at=now()))
            artifact=failure
        index["jobs"][key] = dict(status="completed" if passed else "failed",
            exit_code=code, timed_out=timed_out, source=artifact.relative_to(ROOT).as_posix(),
            artifact_sha256=sha(artifact), elapsed_wall_s=time.perf_counter()-started, finished_at=now())
        write(index_path,index)
        print(key,index["jobs"][key]["status"],flush=True)
    index.update(status="terminal",finished_at=now())
    write(index_path,index)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker")
    args=parser.parse_args()
    worker(args.worker) if args.worker else main()

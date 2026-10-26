"""Supplementary external baselines; does not mutate frozen V4 code."""
from __future__ import annotations

import argparse
import faulthandler
import os
import subprocess
import sys
import time
from pathlib import Path

from experiments.v4_formal.run import ROOT, capture, digest, environment, read, stamp, validate as validate_core, write
from .evaluate import ADAPTERS, evaluate

HERE = Path(__file__).resolve().parent
MANIFEST, INDEX = HERE / "manifest.json", HERE / "index.json"
FIELDS = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s", "ttft_p95_s",
          "tpot_p95_s", "completion_fraction", "backlog_at_window_end", "route_counts", "query_samples")


def jobs():
    result = []
    for scenario, load in (("single", 350), ("multi", 160)):
        for method in ("helix", "swarm", "separate"):
            for seed in (0, 1, 2):
                result.append(dict(scenario=scenario, load=load, method=method, seed=seed))
    for scenario, load, method in (("single", 350, "rcaps_v3"),
                                    ("single", 700, "helix"), ("multi", 320, "helix")):
        for seed in (0, 1, 2):
            result.append(dict(scenario=scenario, load=load, method=method, seed=seed))
    for row in result:
        row["key"] = f"{row['scenario']}/load{row['load']}/{row['method']}/seed{row['seed']}"
    return result


def historical(job):
    if job["load"] == {"single": 350, "multi": 160}[job["scenario"]]:
        return ROOT / "experiments/v3_four_method_comparison/runs" / job["scenario"] / f"seed{job['seed']}" / f"{job['method']}.json"
    return ROOT / "experiments/v3_load_boundary/runs" / job["scenario"] / f"load{job['load']}" / f"seed{job['seed']}" / f"{job['method']}.json"


def preflight():
    checks = []
    for scenario, load in (("single", 350), ("multi", 160)):
        for method in ("helix", "swarm", "separate"):
            adapter = ADAPTERS[method]
            solution, cluster = adapter.layout(scenario, ROOT)
            old = adapter.evaluate(scenario, load, 60, 0, 0, solution, cluster)
            new = evaluate(scenario, method, load, 60, 0, ROOT)
            assert all(old[k] == new[k] for k in FIELDS), (scenario, method)
            assert new["gpu_busy_fraction"] and new["gpu_seconds_per_output_token"] > 0
            checks.append({"scenario": scenario, "method": method, "seed": 0,
                           "duration_s": 60, "status": "passed"})
            print("EXTERNAL_PARITY", checks[-1], flush=True)
    write(HERE / "preflight.json", {"kind": "engineering_not_formal", "status": "passed", "checks": checks,
                                     "adapter_sha256": digest(HERE / "evaluate.py")})


def freeze():
    validate_core()
    check = read(HERE / "preflight.json")
    assert check["status"] == "passed" and check["adapter_sha256"] == digest(HERE / "evaluate.py")
    paths = set(HERE.glob("*.py")) | {HERE / "protocol.json", HERE / "preflight.json"}
    for job in jobs():
        solution, cluster = ADAPTERS[job["method"]].layout(job["scenario"], ROOT)
        paths.update((solution, cluster, historical(job)))
        if job["method"] == "separate":
            for entry in read(solution)["groups"].values():
                paths.update(ROOT / entry[k]["path"] for k in ("physical", "profile", "solution", "sim_cluster"))
        else:
            from benchmarks.layout import scenario
            paths.update(scenario(job["scenario"])[:2])
    content = {"core_manifest_sha256": digest(ROOT / "experiments/v4_formal/manifest.json"),
               "environment": environment(), "protocol": read(HERE / "protocol.json"),
               "jobs": jobs(), "sources_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}}
    if MANIFEST.exists():
        assert content == read(MANIFEST), "Frozen external manifest differs"
    else:
        write(MANIFEST, content)
    print("EXTERNAL_FROZEN", len(jobs()), digest(MANIFEST), flush=True)


def validate():
    validate_core()
    frozen = read(MANIFEST)
    if digest(ROOT / "experiments/v4_formal/manifest.json") != frozen["core_manifest_sha256"]:
        raise RuntimeError("Core manifest changed")
    for name, expected in frozen["sources_sha256"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError(f"External source changed: {name}")
    return frozen


def one(key):
    faulthandler.enable()
    output = HERE / "runs" / key / "result.json"
    if output.exists() or output.with_name("failure.json").exists():
        raise RuntimeError("Attempt already exists; no automatic replacement")
    start = time.perf_counter()
    try:
        frozen = validate()
        job = next(j for j in frozen["jobs"] if j["key"] == key)
        row = evaluate(job["scenario"], job["method"], job["load"], 1800, job["seed"], ROOT)
        old = read(historical(job))
        differences = [k for k in FIELDS if row[k] != old[k]]
        row.update({"job": job, "manifest_sha256": digest(MANIFEST), "environment": environment(),
                    "historical_parity": {"passed": not differences, "differences": differences,
                                           "source": historical(job).relative_to(ROOT).as_posix()},
                    "elapsed_wall_s": time.perf_counter()-start, "finished_at": stamp()})
        if differences:
            write(output.with_name("parity_mismatch_result.json"), row)
            raise RuntimeError(f"External semantic parity mismatch: {differences}")
        validate()
        write(output, row)
    except BaseException as error:
        write(output.with_name("failure.json"), dict(capture(error), key=key, pid=os.getpid(), finished_at=stamp()))
        raise


def queue():
    frozen = validate()
    if INDEX.exists():
        raise RuntimeError("External queue attempt already exists")
    index = {"manifest_sha256": digest(MANIFEST), "queue_pid": os.getpid(), "jobs": {},
             "queue_status": "running", "started_at": stamp(), "selected_windows": len(frozen["jobs"])}
    pending, active, halted = list(frozen["jobs"]), [], False
    write(INDEX, index)
    while pending or active:
        core = read(ROOT / "experiments/v4_formal/index.json")
        if core["queue_status"] in {"halted", "halting_after_failure"}:
            halted = True
            index["halt_reason"] = "Core formal queue failed; new external dispatch stopped"
        while pending and len(active) < frozen["protocol"]["concurrency"] and not halted:
            job = pending.pop(0)
            directory = HERE / "runs" / job["key"]
            directory.mkdir(parents=True, exist_ok=True)
            stream = (directory / "worker.log").open("x", encoding="utf-8")
            command = [sys.executable, "-u", "-X", "faulthandler", "-m", "experiments.v4_external.run", "--phase", "one", "--key", job["key"]]
            process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            active.append((process, stream, job))
            index["jobs"][job["key"]] = {"status": "running", "pid": process.pid, "started_at": stamp()}
            write(INDEX, index)
            print("START", job["key"], process.pid, flush=True)
        for process, stream, job in list(active):
            code = process.poll()
            if code is None:
                continue
            stream.close()
            active.remove((process, stream, job))
            target = HERE / "runs" / job["key"] / "result.json"
            success = code == 0 and target.exists()
            index["jobs"][job["key"]].update({"status": "completed" if success else "failed", "exit_code": code,
                                               "result_sha256": digest(target) if success else None, "finished_at": stamp()})
            halted |= not success
            write(INDEX, index)
            print("DONE" if success else "FAILED", job["key"], code, flush=True)
        if halted and not active:
            break
        if active:
            time.sleep(2)
    index.update({"queue_status": "halted" if halted else "completed", "finished_at": stamp(), "unstarted_windows": len(pending)})
    write(INDEX, index)
    if halted:
        raise SystemExit("External queue halted; failure retained")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=("preflight", "freeze", "one", "queue"), required=True)
    p.add_argument("--key")
    a = p.parse_args()
    if a.phase == "preflight": preflight()
    elif a.phase == "freeze": freeze()
    elif a.phase == "one": one(a.key)
    else: queue()


if __name__ == "__main__": main()

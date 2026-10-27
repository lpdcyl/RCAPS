"""Registered, resumable, continue-on-failure core experiment queue."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import faulthandler
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

from experiments.v4_formal.run import ROOT, read, write, digest, environment, stamp, capture
from experiments.v4_validation.validation_run import validate as validate_previous

HERE = Path(__file__).resolve().parent
MANIFEST, INDEX = HERE / "manifest.json", HERE / "index.json"
MODULE = "experiments.v4_core_validation.run"


def sources():
    return [HERE / name for name in ("__init__.py", "core.py", "run.py", "PROTOCOL_CN.md")]


def hashes(paths):
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def jobs():
    rows = []
    for scenario, load in (("single", 700), ("multi", 320)):
        for seed in (0, 1, 2):
            rows.append(dict(experiment="session", scenario=scenario, load=load, seed=seed,
                             boundary_cost_s=0.0, cell="no_session"))
    for ms in (1, 10, 100):
        for seed in (0, 1, 2):
            rows.append(dict(experiment="boundary_cost", scenario="multi", load=320,
                             seed=seed, boundary_cost_s=ms / 1000, cell=f"hold_{ms}ms"))
    for row in rows:
        row.update(duration=5400, arrival_horizon=1800)
        row["key"] = (f"{row['experiment']}/{row['scenario']}/load{row['load']}/"
                      f"{row['cell']}/seed{row['seed']}")
    return rows


def references():
    directory = ROOT / "experiments/v4_validation"
    index = read(directory / "diagnostic_index.json")
    records = []
    for scenario, load, cell in (("single", 700, "v4"), ("multi", 320, "v4"),
                                  ("multi", 320, "spatial")):
        for seed in (0, 1, 2):
            key = f"cohort_tail/{scenario}/load{load}/{cell}/seed{seed}"
            path = directory / "diagnostic_runs" / key / "result.json"
            entry, row = index["jobs"][key], read(path)
            assert entry["status"] == "completed" and entry["result_sha256"] == digest(path)
            assert row["duration_s"] == 5400 and row["warmup_s"] == 0
            assert row["validation_protocol"]["arrival_horizon_s"] == 1800
            assert row["cohort"]["completed"] and row["seed"] == seed
            assert row["manifest_sha256"] == digest(directory / "diagnostic_manifest.json")
            records.append(dict(scenario=scenario, load=load, cell=cell, seed=seed,
                path=path.relative_to(ROOT).as_posix(), sha256=digest(path),
                trace_sha256=row["trace_sha256"], arrivals=row["arrivals"],
                target_output_tokens=row["cohort"]["target_output_tokens"]))
    return records


def preflight():
    validate_previous()
    if MANIFEST.exists():
        raise RuntimeError("Already registered; cannot repeat or overwrite preflight")
    attempt = HERE / "engineering" / time.strftime("%Y%m%d_%H%M%S")
    attempt.mkdir(parents=True, exist_ok=False)
    before = hashes(sources())
    started = time.perf_counter()
    # Preserve the actual test output, including failed engineering attempts.
    from contextlib import redirect_stdout, redirect_stderr
    with (attempt / "preflight.log").open("x", encoding="utf-8") as stream:
        try:
            from .core import engineering_checks
            with redirect_stdout(stream), redirect_stderr(stream):
                report = engineering_checks()
            assert before == hashes(sources()), "Source changed during engineering checks"
            report.update(finished_at=stamp(), elapsed_wall_s=time.perf_counter() - started,
                          sources_sha256=before, environment=environment())
            write(attempt / "checks.json", report)
            write(HERE / "preflight.json", dict(report, attempt=attempt.relative_to(ROOT).as_posix()))
            print("PREFLIGHT_PASSED", str(attempt), flush=True)
        except BaseException as error:
            report = dict(status="failed", kind="engineering_only", **capture(error),
                          sources_sha256=before, finished_at=stamp())
            write(attempt / "checks.json", report)
            print("PREFLIGHT_FAILED", str(attempt), flush=True)
            raise


def freeze():
    validate_previous()
    if MANIFEST.exists():
        raise RuntimeError("Manifest already exists; never refreeze a registered batch")
    check = read(HERE / "preflight.json")
    assert check["status"] == "passed" and check["sources_sha256"] == hashes(sources())
    paths = sources() + [HERE / "preflight.json",
        ROOT / "experiments/v4_validation/diagnostic_manifest.json",
        ROOT / "experiments/v4_validation/diagnostic_index.json"]
    registered = dict(registered_at=stamp(), environment=environment(),
        jobs=jobs(), references=references(), sources_sha256=hashes(paths),
        protocol=dict(concurrency=2, seeds=[0, 1, 2], no_automatic_retry=True,
            arrival_horizon_s=1800, observation_horizon_s=5400,
            boundary_cost_ms=[1, 10, 100], cost_is_measured=False,
            failure_policy="Record every failure; continue independent windows; no tuning",
            pairing="Same scenario/load/seed, exact arrival trace and complete-work cohort",
            baseline_reuse="Frozen cohort_tail full RCAPS and no-chunk records, with hashes",
            final_reconciliation="Once after all registered attempts are terminal"))
    write(MANIFEST, registered)
    print("CORE_REGISTERED", len(registered["jobs"]), digest(MANIFEST), flush=True)


def validate():
    validate_previous()
    registered = read(MANIFEST)
    assert environment() == registered["environment"], "Environment drift"
    for path, expected in registered["sources_sha256"].items():
        assert digest(ROOT / path) == expected, f"Frozen source drift: {path}"
    for ref in registered["references"]:
        assert digest(ROOT / ref["path"]) == ref["sha256"], f"Reference drift: {ref['path']}"
    return registered


def alive(pid, created=None):
    if pid is None:
        return False
    try:
        p = psutil.Process(pid)
        return p.is_running() and (created is None or abs(p.create_time() - created) < .01)
    except psutil.Error:
        return False


def worker_processes():
    """Conservative cap: any other Python process may be a simulation worker."""
    found = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            if p.pid == os.getpid() or "python" not in (p.info["name"] or "").lower():
                continue
            cmd = p.info["cmdline"] or []
            # A queue controller does no simulation. Preflight and one do.
            phase = cmd[cmd.index("--phase") + 1] if "--phase" in cmd else None
            if phase in {"queue", "status"}:
                continue
            found.append(p.info)
        except (psutil.Error, IndexError):
            continue
    return found


def one(key):
    faulthandler.enable()
    directory = HERE / "runs" / key
    output, failure = directory / "result.json", directory / "failure.json"
    if output.exists() or failure.exists() or (directory / "worker_started.json").exists():
        raise RuntimeError("Existing attempt; no retry or overwrite")
    started = time.perf_counter()
    write(directory / "worker_started.json", dict(pid=os.getpid(),
        create_time=psutil.Process().create_time(), started_at=stamp(), key=key))
    job = None
    try:
        frozen = validate()
        job = next(j for j in frozen["jobs"] if j["key"] == key)
        from .core import evaluate, validate_row
        print("EVALUATING", key, flush=True)
        row = evaluate(job)
        checks = validate_row(row)
        validate()
        row.update(job=job, status="completed", finished_at=stamp(),
            elapsed_wall_s=time.perf_counter() - started,
            manifest_sha256=digest(MANIFEST), environment=environment(), integrity_checks=checks)
        write(output, row)
        write(directory / "worker_done.json", dict(status="completed", exit_code=0,
            result_sha256=digest(output), finished_at=stamp()))
        print("COMPLETE", key, flush=True)
    except BaseException as error:
        write(failure, dict(**capture(error), job=job, key=key,
            finished_at=stamp(), elapsed_wall_s=time.perf_counter() - started))
        write(directory / "worker_done.json", dict(status="failed", failure_sha256=digest(failure),
            finished_at=stamp()))
        raise


@contextmanager
def queue_lock():
    # OS releases this byte-range lock even on an abrupt controller exit.
    import msvcrt
    with (HERE / "queue.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def queue():
    frozen = validate()
    with queue_lock():
        if INDEX.exists():
            index = read(INDEX)
            assert index["manifest_sha256"] == digest(MANIFEST)
            if index["status"] == "completed":
                print("QUEUE_ALREADY_TERMINAL", flush=True)
                return
        else:
            index = dict(status="running", started_at=stamp(),
                manifest_sha256=digest(MANIFEST), jobs={j["key"]: dict(status="pending")
                                                       for j in frozen["jobs"]})
        index.update(pid=os.getpid(), create_time=psutil.Process().create_time(),
                     controller_started_at=stamp())
        write(INDEX, index)
        owned = {}
        while True:
            changed = False
            for key, entry in index["jobs"].items():
                if entry["status"] not in {"starting", "running"}:
                    continue
                directory = HERE / "runs" / key
                if not entry.get("pid") and (directory / "worker_started.json").exists():
                    started = read(directory / "worker_started.json")
                    entry.update(pid=started["pid"], create_time=started["create_time"])
                    changed = True
                if alive(entry.get("pid"), entry.get("create_time")):
                    continue
                if key in owned:
                    process, log = owned.pop(key)
                    exit_code = process.poll()
                    log.close()
                else:
                    exit_code = None  # adopted process: no invented OS exit code
                out, failure = directory / "result.json", directory / "failure.json"
                done_path = directory / "worker_done.json"
                done = read(done_path) if done_path.exists() else {}
                ok = (exit_code in (0, None) and done.get("status") == "completed"
                      and out.exists() and not failure.exists()
                      and done.get("result_sha256") == digest(out))
                if not ok and not failure.exists():
                    write(failure, dict(kind="process_failure", key=key, exit_code=exit_code,
                        finished_at=stamp(), note="No validated worker completion; prior files retained"))
                entry.update(status="completed" if ok else "failed", exit_code=exit_code,
                    finished_at=stamp(), result_sha256=digest(out) if out.exists() else None,
                    failure_sha256=digest(failure) if failure.exists() else None)
                print("DONE" if ok else "FAILED", key, exit_code, flush=True)
                changed = True
            if changed:
                write(INDEX, index)
            pending = [j for j in frozen["jobs"] if index["jobs"][j["key"]]["status"] == "pending"]
            active = [e for e in index["jobs"].values() if e["status"] in {"starting", "running"}]
            if not pending and not active:
                index.update(status="completed", finished_at=stamp())
                write(INDEX, index)
                print("CORE_QUEUE_FINISHED", flush=True)
                return
            capacity = max(0, 2 - len(worker_processes()))
            for job in pending[:capacity]:
                key = job["key"]
                directory = HERE / "runs" / key
                entry = index["jobs"][key]
                try:
                    if directory.exists():
                        raise RuntimeError("Unindexed attempt exists; retain it, do not overwrite")
                    directory.mkdir(parents=True)
                    entry.update(status="starting", started_at=stamp())
                    write(INDEX, index)
                    log = (directory / "worker.log").open("x", encoding="utf-8")
                    process = subprocess.Popen([sys.executable, "-u", "-X", "utf8", "-X",
                        "faulthandler", "-m", MODULE, "--phase", "one", "--key", key],
                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    owned[key] = process, log
                    entry.update(status="running", pid=process.pid,
                                 create_time=psutil.Process(process.pid).create_time())
                    write(INDEX, index)
                    print("START", key, process.pid, flush=True)
                except BaseException as error:
                    failure = directory / "dispatch_failure.json"
                    if not failure.exists():
                        write(failure, dict(**capture(error), key=key, finished_at=stamp()))
                    entry.update(status="failed", finished_at=stamp(),
                                 dispatch_failure_sha256=digest(failure))
                    write(INDEX, index)
                    print("DISPATCH_FAILED", key, flush=True)
            time.sleep(3)


def status():
    from collections import Counter
    if not INDEX.exists():
        print("NOT_STARTED")
        return
    index = read(INDEX)
    print(dict(status=index["status"], counts=dict(Counter(j["status"] for j in index["jobs"].values())),
        controller_alive=alive(index.get("pid"), index.get("create_time")),
        running=[dict(key=k, **v) for k, v in index["jobs"].items() if v["status"] == "running"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["preflight", "freeze", "one", "queue", "status"], required=True)
    parser.add_argument("--key")
    args = parser.parse_args()
    if args.phase == "one":
        one(args.key)
    else:
        globals()[args.phase]()

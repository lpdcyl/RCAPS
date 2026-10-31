"""Pre-registered diagnostic replay of failed paper-relevant V5 windows.

All original formal registries and artifacts remain immutable. A replay is a
second attempt, never a new seed and never an automatic replacement result.
"""

import argparse
import csv
import importlib
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, relative, sha, write


HERE = Path(__file__).resolve().parent
FORMAL = HERE / "formal"
CAMPAIGNS = (
    "v5_seed_completion", "v5_kv_stress", "v5_link_models",
    "v5_parallax", "v5_model30b_pools", "v5_model30b",
)
WORKER_LIMIT = 28


def register():
    path = FORMAL / "manifest.json"
    if path.exists():
        manifest = read(path)
        assert manifest["replay_script_sha256"] == sha(Path(__file__))
        return manifest
    jobs = []
    sources = {}
    for campaign in CAMPAIGNS:
        formal = ROOT / "experiments" / campaign / "formal"
        original_manifest = read(formal / "manifest.json")
        check(original_manifest)
        index = read(formal / "index.json")
        assert index["status"] == "terminal"
        assert index["manifest_sha256"] == sha(formal / "manifest.json")
        sources[campaign] = {
            "index_sha256": sha(formal / "index.json"),
            "manifest_sha256": index["manifest_sha256"],
            "archive_sha256": sha(formal / "frozen_runtime_inputs.zip")
            if (formal / "frozen_runtime_inputs.zip").exists() else None,
        }
        for job in original_manifest["jobs"]:
            if campaign == "v5_model30b" and job["cell"] != "V4":
                continue  # This old merged-pool Helix adaptation was superseded.
            key = job["key"]
            entry = index["jobs"][key]
            if entry["status"] not in ("failed", "reused_failure"):
                continue
            source = ROOT / entry["source"]
            assert sha(source) == entry["artifact_sha256"]
            failure = read(source)
            cause = failure.get("classification") or failure.get("error") or str(failure.get("exit_code"))
            jobs.append({
                "key": campaign + "/" + key,
                "campaign": campaign,
                "original_key": key,
                "job": job,
                "prior_status": entry["status"],
                "prior_failure": entry["source"],
                "prior_failure_sha256": entry["artifact_sha256"],
                "prior_cause": cause,
                "original_manifest_sha256": index["manifest_sha256"],
                "priority": 0 if cause == "controller_and_worker_interrupted" else 1,
            })
    jobs.sort(key=lambda j: (j["priority"], CAMPAIGNS.index(j["campaign"]), j["original_key"]))
    assert len(jobs) == 99, len(jobs)
    manifest = {
        "registered_at": now(),
        "scope": "One diagnostic replay of every failed paper-relevant V5 formal window, including inherited failures; superseded 30B merged-pool Helix adaptation excluded.",
        "policy": "Retry all selected failed keys once, predeclared before outcomes. Preserve original attempt, use identical model, traffic, placement, seed, duration and source inputs. A retry is never an independent seed or silent replacement.",
        "jobs": jobs,
        "source_registries": sources,
        "replay_script_sha256": sha(Path(__file__)),
        "worker_limit": WORKER_LIMIT,
        "timeout_wall_s": 14400,
        "environment": {"executable": sys.executable, "python": sys.version, "env": ENV},
    }
    write(path, manifest)
    print("REGISTERED", len(jobs), "interrupted", sum(j["priority"] == 0 for j in jobs), flush=True)
    return manifest


def verify(job, manifest):
    assert manifest["replay_script_sha256"] == sha(Path(__file__))
    campaign = job["campaign"]
    formal = ROOT / "experiments" / campaign / "formal"
    source = manifest["source_registries"][campaign]
    assert sha(formal / "index.json") == source["index_sha256"]
    assert sha(formal / "manifest.json") == source["manifest_sha256"]
    if source["archive_sha256"] is not None:
        assert sha(formal / "frozen_runtime_inputs.zip") == source["archive_sha256"]
    assert sha(ROOT / job["prior_failure"]) == job["prior_failure_sha256"]
    check(read(formal / "manifest.json"))


def evaluate(job, directory):
    campaign = job["campaign"]
    module = importlib.import_module("experiments." + campaign + ".run")
    original = job["job"]
    if campaign in ("v5_model30b_pools", "v5_model30b"):
        return module.evaluate(
            original["scenario"], original["load"], original["seed"],
            original["cell"], original["duration"], directory / "kv.csv.gz",
        )
    return module.evaluate(original, directory / "kv.csv.gz")


def worker(key):
    manifest = read(FORMAL / "manifest.json")
    job = next(j for j in manifest["jobs"] if j["key"] == key)
    directory = FORMAL / "runs" / key
    start = time.perf_counter()
    try:
        verify(job, manifest)
        row = evaluate(job, directory)
        verify(job, manifest)
        assert len(row["query_samples"]) == row["arrivals"]
        row.update(
            status="completed", job=job["job"], diagnostic_replay_of=job["prior_failure"],
            original_manifest_sha256=job["original_manifest_sha256"],
            replay_manifest_sha256=sha(FORMAL / "manifest.json"),
            elapsed_wall_s=time.perf_counter() - start, finished_at=now(),
        )
        if (directory / "kv.csv.gz").exists():
            row["kv_series_sha256"] = sha(directory / "kv.csv.gz")
        write(directory / "result.json", row)
    except BaseException as error:
        write(directory / "failure.json", {
            "status": "failed", "job": job["job"],
            "diagnostic_replay_of": job["prior_failure"],
            "error": repr(error), "traceback": traceback.format_exc(),
            "replay_manifest_sha256": sha(FORMAL / "manifest.json"),
            "elapsed_wall_s": time.perf_counter() - start, "finished_at": now(),
        })
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    index_path = FORMAL / "index.json"
    if index_path.exists():
        index = read(index_path)
        assert index["manifest_sha256"] == sha(FORMAL / "manifest.json")
        assert not any(e["status"] == "running" for e in index["jobs"].values())
    else:
        index = {
            "status": "running", "controller_pid": os.getpid(), "registered_at": now(),
            "manifest_sha256": sha(FORMAL / "manifest.json"),
            "jobs": {j["key"]: {"status": "pending"} for j in manifest["jobs"]},
        }
    pending = [j for j in manifest["jobs"] if index["jobs"][j["key"]]["status"] == "pending"]
    active = {}
    write(index_path, index)
    while pending or active:
        while pending and len(active) < manifest["worker_limit"]:
            job = pending.pop(0)
            key = job["key"]
            directory = FORMAL / "runs" / key
            directory.mkdir(parents=True, exist_ok=False)
            log = (directory / "worker.log").open("x", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, "-u", "-X", "faulthandler", "-m", "experiments.v5_failure_replay.run", "--worker", key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log,
            )
            active[key] = (process, log, time.monotonic())
            index["jobs"][key] = {"status": "running", "pid": process.pid, "started_at": now()}
            write(index_path, index)
            print("START", key, flush=True)
        for key, (process, log, start) in list(active.items()):
            code = process.poll()
            timeout = code is None and time.monotonic() - start > manifest["timeout_wall_s"]
            if timeout:
                process.kill()
                code = process.wait()
            if code is None:
                continue
            log.close()
            del active[key]
            directory = FORMAL / "runs" / key
            passed = code == 0 and (directory / "result.json").exists()
            artifact = directory / ("result.json" if passed else "failure.json")
            if not artifact.exists():
                write(artifact, {"status": "failed", "classification": "timeout" if timeout else "abnormal_exit",
                                 "exit_code": code, "finished_at": now()})
            index["jobs"][key].update(
                status="completed" if passed else "failed", exit_code=code, finished_at=now(),
                source=relative(artifact), artifact_sha256=sha(artifact),
            )
            write(index_path, index)
            print("END", key, "success" if passed else "failure", flush=True)
        if active:
            time.sleep(2)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)
    report(manifest, index)
    print("TERMINAL", dict(Counter(e["status"] for e in index["jobs"].values())), flush=True)


def report(manifest=None, index=None):
    manifest = manifest or read(FORMAL / "manifest.json")
    index = index or read(FORMAL / "index.json")
    assert index["status"] == "terminal"
    rows = []
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        assert entry["status"] in ("completed", "failed")
        artifact = ROOT / entry["source"]
        assert sha(artifact) == entry["artifact_sha256"]
        outcome = read(artifact)
        rows.append({
            "campaign": job["campaign"], "key": job["original_key"],
            "prior_status": job["prior_status"], "prior_cause": job["prior_cause"],
            "replay_status": entry["status"],
            "replay_cause": outcome.get("error", outcome.get("classification", "")),
            "prior_source": job["prior_failure"], "replay_source": entry["source"],
            "replay_sha256": entry["artifact_sha256"],
        })
    with (HERE / "diagnostic_summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    by_campaign = {}
    for campaign in CAMPAIGNS:
        selected = [r for r in rows if r["campaign"] == campaign]
        by_campaign[campaign] = dict(Counter(r["replay_status"] for r in selected))
    lines = [
        "# V5 失败窗口独立诊断重跑", "",
        "这 99 个键在看到重跑结果之前预登记。原正式结果、失败 JSON、日志和冻结输入不覆盖；重跑成功也不自动替换原始一次尝试或算作新种子。",
        "", "| 批次 | 重跑成功 | 重跑失败 |", "|---|---:|---:|",
    ]
    for campaign, count in by_campaign.items():
        lines.append(f"| {campaign} | {count.get('completed', 0)} | {count.get('failed', 0)} |")
    lines += [
        "", "逐键前后状态、原因和 SHA256 见 diagnostic_summary.csv。容量不足等重复失败是可重复的科学结果，不得改为零或选择性删除。",
        "旧 30B 合并池 Helix 适配已被原分池正式协议取代，本批未重跑那 6 项过时失败。",
    ]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", {
        "passed": True, "at": now(), "registered_windows": len(rows),
        "counts": dict(Counter(r["replay_status"] for r in rows)),
        "source_registry_sha256": manifest["source_registries"],
        "manifest_sha256": sha(FORMAL / "manifest.json"),
        "summary_sha256": sha(HERE / "diagnostic_summary.csv"),
        "artifacts": rows,
    })
    print("REPORT", by_campaign, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.register:
        register()
    elif args.worker:
        worker(args.worker)
    elif args.report:
        report()
    else:
        queue()

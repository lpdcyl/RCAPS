"""One independent diagnostic replay of every failed V6 formal window."""
from __future__ import annotations

import argparse
import csv
import importlib
import sys
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, sha, write
from experiments.v6_completion.campaign_queue import queue, worker

BASE = Path(__file__).resolve().parent
HERE = BASE / "failure_replay"
CAMPAIGNS = ("generalization", "session_cost", "robustness", "weight_online",
             "session_capacity", "bandwidth_threshold", "scalability")


def category(outcome):
    if outcome.get("status") == "completed":
        return "completed"
    message = outcome.get("error", "") + "\n" + outcome.get("traceback", "")
    if "Exceed KV-cache capacity" in message:
        return "actual_kv_allocation_overflow"
    if "No next level node meets scheduling requirement" in message:
        return "helix_admission_no_eligible_next_node"
    if "outside profile range" in message:
        return "profiling_range_exceeded"
    if "LinkBounded" in message:
        return "link_reservation_assertion"
    if outcome.get("classification"):
        return outcome["classification"]
    return outcome.get("error", "unknown")[:140]


def evaluate(job):
    module = importlib.import_module("experiments.v6_completion." + job["campaign"])
    return module.evaluate(job["original_job"])


def register(phase, workers):
    assert phase == "formal"
    path = HERE / phase / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    sources = dict(read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")
                   ["sources_sha256"])
    jobs = []
    for campaign in CAMPAIGNS:
        folder = BASE / campaign / "formal"
        manifest, index = read(folder / "manifest.json"), read(folder / "index.json")
        assert index["status"] == "terminal", campaign
        sources.update(manifest["sources_sha256"])
        for original in manifest["jobs"]:
            entry = index["jobs"][original["key"]]
            if entry["status"] != "failed":
                continue
            prior = ROOT / entry["source"]
            assert sha(prior) == entry["artifact_sha256"]
            jobs.append(dict(key=f"{campaign}/{original['key']}", campaign=campaign,
                             original_job=original, prior_source=entry["source"],
                             prior_sha256=entry["artifact_sha256"],
                             original_manifest_sha256=sha(folder / "manifest.json")))
    for name in ("experiments/v6_completion/failure_replay.py",
                 "experiments/v6_completion/campaign_queue.py"):
        sources[name] = sha(ROOT / name)
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
                    sources_sha256=sources, worker_limit=workers,
                    timeout_wall_s=14400,
                    scope="Independent repeat of every V6 failed formal key; original results unchanged",
                    failure_policy="Exactly one replay per key; recovery does not become a new seed",
                    environment=dict(executable=sys.executable, env=ENV))
    write(path, manifest)
    return manifest


def report():
    folder = HERE / "formal"
    manifest, index = read(folder / "manifest.json"), read(folder / "index.json")
    assert index["status"] == "terminal"
    rows = []
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        original = ROOT / job["prior_source"]
        replay = ROOT / entry["source"]
        assert sha(original) == job["prior_sha256"]
        assert sha(replay) == entry["artifact_sha256"]
        before, after = read(original), read(replay)
        rows.append(dict(campaign=job["campaign"], original_key=job["original_job"]["key"],
                         original_cause=category(before), replay_status=entry["status"],
                         replay_cause=category(after), original_source=job["prior_source"],
                         original_sha256=job["prior_sha256"], replay_source=entry["source"],
                         replay_sha256=entry["artifact_sha256"]))
    if rows:
        with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as out:
            writer = csv.DictWriter(out, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    counts = Counter((r["campaign"], r["original_cause"], r["replay_status"],
                      r["replay_cause"]) for r in rows)
    lines = ["# V6 失败窗口独立重放", "",
             "每个首次正式失败键只重放一次，原结果与失败记录不覆盖；重放成功不计为新种子。", "",
             "| 批次 | 原因 | 重放状态 | 重放原因 | 窗口数 |",
             "|---|---|---|---|---:|"]
    for key, value in sorted(counts.items()):
        lines.append("| " + " | ".join(map(str, (*key, value))) + " |")
    lines += ["", "逐键来源与 SHA256 见 individual.csv。容量不足可复现时属于有效的容量边界，不填零。"]
    (HERE / "RESULTS_CN.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, windows=len(rows),
          counts=dict(Counter(r["replay_status"] for r in rows)),
          manifest_sha256=sha(folder / "manifest.json"),
          index_sha256=sha(folder / "index.json"),
          report_sha256=sha(HERE / "RESULTS_CN.md"),
          individual_sha256=sha(HERE / "individual.csv") if rows else None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("formal",), default="formal")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, evaluate)
    else:
        queue(HERE, "experiments.v6_completion.failure_replay", args.phase,
              args.workers, register, report)


if __name__ == "__main__":
    main()

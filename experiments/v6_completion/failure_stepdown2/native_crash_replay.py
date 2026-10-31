"""Retry stepdown2 workers that exited natively before producing artifacts."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from experiments.v5_core_supplement.run import now, read, sha, write
from experiments.v6_completion.failure_stepdown import evaluate

BASE = Path(__file__).resolve().parent
OUT = BASE / "native_crash_replay"
KEYS = tuple([f"30b_multi_rate525/HH/seed{i}" for i in range(5)] +
             ["30b_multi_rate525/V4/seed0"])


def worker(key: str) -> int:
    manifest_path = BASE / "formal/manifest.json"
    jobs = {job["key"]: job for job in read(manifest_path)["jobs"]}
    job = jobs[key]
    folder = OUT / "runs" / key
    try:
        row = evaluate(job)
        row.update(status="completed", job=job, manifest_sha256=sha(manifest_path), replayed_at=now())
        write(folder / "result.json", row)
        return 0
    except BaseException as error:
        write(folder / "failure.json", dict(status="failed", classification="python_exception",
              job=job, error=repr(error), traceback=traceback.format_exc(),
              manifest_sha256=sha(manifest_path), replayed_at=now()))
        traceback.print_exc()
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker(args.worker))

    primary = read(BASE / "formal/index.json")
    source_manifest = BASE / "formal/manifest.json"
    jobs = {job["key"]: job for job in read(source_manifest)["jobs"]}
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    if not manifest_path.exists():
        for key in KEYS:
            assert primary["jobs"][key]["status"] == "failed"
            original = read(ROOT / primary["jobs"][key]["source"])
            assert original.get("classification") == "abnormal_exit" or "AttributeError" in original.get("error", "")
        write(manifest_path, dict(created_at=now(), purpose="Diagnose failed stepdown2 seeds",
              source_formal_manifest_sha256=sha(source_manifest),
              source_formal_index_sha256=sha(BASE / "formal/index.json"),
              keys=[jobs[key] for key in KEYS],
              protocol="Repeat exact registered conditions and seeds in isolated worker processes"))
    replay_manifest = read(manifest_path)
    assert replay_manifest["source_formal_manifest_sha256"] == sha(source_manifest)
    assert [job["key"] for job in replay_manifest["keys"]] == list(KEYS)

    for key in KEYS:
        folder = OUT / "runs" / key
        folder.mkdir(parents=True, exist_ok=True)
        artifacts = (folder / "result.json", folder / "failure.json")
        if any(path.exists() for path in artifacts):
            continue
        old_log = folder / "worker.log"
        if old_log.exists():
            preserved = folder / f"worker.interrupted.{now().replace(':', '-')}.log"
            old_log.rename(preserved)
            write(folder / "interruption.json", dict(status="interrupted", key=key,
                  reason="Controller ended before worker produced an artifact",
                  log=preserved.relative_to(ROOT).as_posix(), log_sha256=sha(preserved),
                  recorded_at=now()))
        with (folder / "worker.log").open("wb") as log:
            process = subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), "--worker", key],
                                     cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT)
        if not any(path.exists() for path in artifacts):
            write(folder / "failure.json", dict(status="failed", classification="native_process_crash",
                  job=jobs[key], exit_code=process.returncode,
                  error=f"Worker exited without Python result artifact (exit={process.returncode})",
                  manifest_sha256=sha(source_manifest), replayed_at=now()))
        result = read(folder / ("result.json" if (folder / "result.json").exists() else "failure.json"))
        print("END", key, result["status"], result.get("classification", result.get("error", "completed")), flush=True)

    rows = []
    for key in KEYS:
        folder = OUT / "runs" / key
        artifact = folder / ("result.json" if (folder / "result.json").exists() else "failure.json")
        result = read(artifact)
        assert result["job"] == jobs[key]
        assert result["manifest_sha256"] == sha(source_manifest)
        rows.append(dict(key=key, status=result["status"],
                         classification=result.get("classification", "completed"),
                         error=result.get("error"), source=artifact.relative_to(ROOT).as_posix(),
                         sha256=sha(artifact), tpot_p95_s=result.get("tpot_p95_s"),
                         ttft_p95_s=result.get("ttft_p95_s"),
                         completion_fraction=result.get("completion_fraction")))
    lines = ["# 30B 早期异常窗口诊断重放", "",
             "与正式窗口同条件、同种子；重放不覆盖正式失败，也不产生新种子。", "",
             "| 键 | 状态 | 原因 | P95 TPOT s | P95 TTFT s | 完成率 |", "|---|---|---|---:|---:|---:|"]
    for row in rows:
        fmt = lambda value: "未观测" if value is None else f"{value:.4f}"
        lines.append(f"| {row['key']} | {row['status']} | {row['error'] or row['classification']} | "
                     f"{fmt(row['tpot_p95_s'])} | {fmt(row['ttft_p95_s'])} | "
                     f"{fmt(row['completion_fraction'])} |")
    (OUT / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(OUT / "FINAL_AUDIT.json", dict(passed=True, windows=len(rows),
          counts=dict(Counter(row["status"] for row in rows)), rows=rows,
          source_formal_manifest_sha256=sha(source_manifest),
          replay_manifest_sha256=sha(manifest_path),
          results_sha256=sha(OUT / "RESULTS_CN.md")))


if __name__ == "__main__":
    main()

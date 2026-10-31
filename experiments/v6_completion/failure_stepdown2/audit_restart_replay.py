"""Audit the two separate reruns after the computer restart."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from experiments.v5_core_supplement.run import now, read, sha, write

BASE = Path(__file__).resolve().parent
OUT = BASE / "restart_replay"
KEYS = ("30b_multi_rate525/HHplus/seed3", "30b_multi_rate525/V4/seed3")


def main() -> None:
    primary = read(BASE / "formal/index.json")
    original_manifest = BASE / "formal/manifest.json"
    audit = read(BASE / "FINAL_AUDIT.json")
    rows = []
    expected = {job["key"]: job for job in read(original_manifest)["jobs"]}
    for key in KEYS:
        folder = OUT / "runs" / key
        candidates = [folder / "result.json", folder / "failure.json"]
        artifact = next(path for path in candidates if path.exists())
        result = read(artifact)
        job = expected[key]
        assert result["job"] == job
        assert result["manifest_sha256"] == sha(original_manifest)
        rows.append(dict(key=key, status=result["status"], job=job,
                         source=artifact.relative_to(ROOT).as_posix(),
                         sha256=sha(artifact), error=result.get("error"),
                         tpot_p95_s=result.get("tpot_p95_s"),
                         ttft_p95_s=result.get("ttft_p95_s"),
                         completion_fraction=result.get("completion_fraction"),
                         output_throughput_tokens_per_s=result.get("output_throughput_tokens_per_s")))
    statuses = {row["key"]: row["status"] for row in rows}
    assert statuses == {KEYS[0]: "completed", KEYS[1]: "failed"}
    assert "KV-cache capacity" in rows[1]["error"]
    assert primary["status"] == "terminal" and audit["passed"]

    write(OUT / "manifest.json", dict(created_at=now(), purpose="Replay restart-interrupted keys",
          source_formal_manifest_sha256=sha(original_manifest),
          source_formal_final_audit_sha256=sha(BASE / "FINAL_AUDIT.json"),
          source_script_sha256=sha(BASE / "restart_replay.py"), keys=[expected[key] for key in KEYS],
          protocol="Same registered condition and seed; separate artifacts; never overwrite the formal attempt"))
    lines = ["# 电脑重启中断窗口的独立重放", "",
             "相同正式 manifest 条件和 seed，独立保存；不覆盖正式索引中的首轮中断记录。", "",
             "| 条件/方法/seed | 重放状态 | P95 TPOT (s) | P95 TTFT (s) | 完成率 | 原因 |", "|---|---|---:|---:|---:|---|"]
    for row in rows:
        def fmt(value):
            return "未观测" if value is None else f"{value:.4f}"
        lines.append(f"| {row['key']} | {row['status']} | {fmt(row['tpot_p95_s'])} | "
                     f"{fmt(row['ttft_p95_s'])} | {fmt(row['completion_fraction'])} | "
                     f"{row['error'] or '完成'} |")
    (OUT / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(OUT / "FINAL_AUDIT.json", dict(passed=True, windows=len(rows), rows=rows,
          source_formal_manifest_sha256=sha(original_manifest),
          source_formal_final_audit_sha256=sha(BASE / "FINAL_AUDIT.json"),
          replay_manifest_sha256=sha(OUT / "manifest.json"), results_sha256=sha(OUT / "RESULTS_CN.md")))


if __name__ == "__main__":
    main()

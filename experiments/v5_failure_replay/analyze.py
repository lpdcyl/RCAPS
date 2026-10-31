"""Classify independent diagnostic replays without rewriting formal evidence."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha, write

HERE = Path(__file__).resolve().parent
FORMAL = HERE / "formal"


def cause(item):
    text = " ".join(str(item.get(k, "")) for k in ("classification", "error", "traceback", "exit_code"))
    if "controller_and_worker_interrupted" in text:
        return "controller_worker_interrupted"
    if "Exceed KV-cache capacity" in text or "Exceed KV-cache" in text:
        return "actual_kv_allocation_overflow"
    if "No next level node meets scheduling requirement" in text or "Fail-KV" in text:
        return "helix_admission_no_eligible_next_node"
    if "3221225477" in text or "-1073741819" in text:
        return "windows_native_access_violation"
    if "timeout" in text.lower():
        return "timeout"
    if "Placement has no source-to-sink layer route" in text:
        return "route_unavailable"
    return "other"


def main():
    manifest, index = read(FORMAL / "manifest.json"), read(FORMAL / "index.json")
    assert index["status"] == "terminal"
    assert index["manifest_sha256"] == sha(FORMAL / "manifest.json")
    rows = []
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        assert entry["status"] in ("completed", "failed")
        source = ROOT / entry["source"]
        prior_source = ROOT / job["prior_failure"]
        assert sha(source) == entry["artifact_sha256"]
        assert sha(prior_source) == job["prior_failure_sha256"]
        outcome = read(source)
        prior = read(prior_source)
        row = {"campaign": job["campaign"], "key": job["original_key"],
               "original_cause": cause(prior), "replay_status": entry["status"],
               "replay_cause": "completed" if entry["status"] == "completed" else cause(outcome),
               "original_source": job["prior_failure"], "replay_source": entry["source"],
               "replay_sha256": entry["artifact_sha256"]}
        if entry["status"] == "completed":
            assert len(outcome["query_samples"]) == outcome["arrivals"]
            row["replay_trace_sha256"] = outcome["trace_sha256"]
        else:
            row["replay_trace_sha256"] = ""
        rows.append(row)
    with (HERE / "cause_classification.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    count = Counter((r["original_cause"], r["replay_status"], r["replay_cause"]) for r in rows)
    per_campaign = defaultdict(Counter)
    for row in rows:
        per_campaign[row["campaign"]][row["replay_status"]] += 1
    lines = ["# 失败窗口重放原因分类", "",
             "所有 99 个原失败键仅独立重放一次；原正式索引与原始失败记录不改。重放成功不是新种子，也不自动替换首轮结果。",
             "分类依据原始与重放 failure.json/worker 退出状态；逐键证据及 SHA256 见 cause_classification.csv。", "",
             "| 批次 | 重放成功 | 重放失败 |", "|---|---:|---:|"]
    for campaign, statuses in per_campaign.items():
        lines.append(f"| {campaign} | {statuses['completed']} | {statuses['failed']} |")
    lines += ["", "| 原因（原始） | 重放状态 | 重放原因 | 窗口数 |", "|---|---|---|---:|"]
    for key, n in sorted(count.items()):
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {n} |")
    lines += ["", "解释：controller_worker_interrupted 是控制器与 worker 同时退出留下的未完成尝试，"
              "后续成功仅说明该窗口可重现运行；actual_kv_allocation_overflow 是仿真中真实 KV 分配越界；"
              "helix_admission_no_eligible_next_node 是 Helix 预期 KV 高水位过滤后没有可接纳下游。"
              "Windows 原生访问冲突只能归类为环境或原生运行时崩溃，不能据此推断算法缺陷。"
              "失败不能填零，不能用幸存种子生成完整五种子统计。"]
    (HERE / "CAUSES_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "CAUSE_AUDIT.json", dict(passed=True, windows=len(rows),
          index_sha256=sha(FORMAL / "index.json"),
          manifest_sha256=sha(FORMAL / "manifest.json"),
          classification_sha256=sha(HERE / "cause_classification.csv")))


if __name__ == "__main__":
    main()

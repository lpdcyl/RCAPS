"""Derive Decode batch statistics directly from completed P1-3 raw probes."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ROOT, read, sha, write

HERE = Path(__file__).resolve().parent / "session_cost"


def batch_stats(result):
    gpu = result["phase_link_profile"]["gpu"]
    histogram = defaultdict(int)
    for item in gpu.values():
        for size, count in item["decode_batch_histogram"].items():
            histogram[int(size)] += int(count)
    events = sum(histogram.values())
    tokens = sum(size * count for size, count in histogram.items())
    assert events > 0 and tokens > 0
    return tokens / events, sum(size * size * count for size, count in histogram.items()) / tokens


def main():
    manifest, index = read(HERE / "formal/manifest.json"), read(HERE / "formal/index.json")
    assert index["status"] == "terminal"
    rows = []
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        row = {key: job[key] for key in ("scenario", "load", "variant", "seed")}
        row.update(status=entry["status"], source=entry["source"])
        source = ROOT / entry["source"]
        assert sha(source) == entry["artifact_sha256"]
        if entry["status"] == "completed":
            event_mean, token_mean = batch_stats(read(source))
            row.update(event_mean_decode_batch=event_mean,
                       token_weighted_mean_decode_batch=token_mean)
        else:
            row.update(event_mean_decode_batch=None, token_weighted_mean_decode_batch=None)
        rows.append(row)
    with (HERE / "decode_batch.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 会话定价变体 Decode 批量", "",
             "逐 GPU Decode batch 直方图从正式 result.json 重新聚合。按 layer execution 事件加权及按 token 加权的两个口径均列出。",
             "失败行留空；不足五种子不报告完整组统计。", "",
             "| 拓扑 | 变体 | 成功 | 事件均值 | token 加权均值 |",
             "|---|---|---:|---:|---:|"]
    for scenario in ("single", "multi"):
        for variant in manifest["variants"]:
            subset = [r for r in rows if r["scenario"] == scenario and
                      r["variant"] == variant and r["status"] == "completed"]
            if len(subset) == 5:
                event = f"{mean(r['event_mean_decode_batch'] for r in subset):.3f} ± {stdev(r['event_mean_decode_batch'] for r in subset):.3f}"
                token = f"{mean(r['token_weighted_mean_decode_batch'] for r in subset):.3f} ± {stdev(r['token_weighted_mean_decode_batch'] for r in subset):.3f}"
            else:
                event = token = "未汇总"
            lines.append(f"| {scenario} | {variant} | {len(subset)}/5 | {event} | {token} |")
    (HERE / "BATCH_RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "BATCH_AUDIT.json", dict(passed=True, jobs=len(rows),
          source_index_sha256=sha(HERE / "formal/index.json"),
          csv_sha256=sha(HERE / "decode_batch.csv"),
          report_sha256=sha(HERE / "BATCH_RESULTS_CN.md")))


if __name__ == "__main__":
    main()

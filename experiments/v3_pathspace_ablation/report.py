"""Audit and report the V3 full-DAG versus canonical-route experiment."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from benchmarks.compare import MATCH_FIELDS, common_cohort
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from experiments.m2_multistage_candidate.placement import digest

from .run import CASES, HERE, LOADS, ROOT, SEEDS, SOURCE, audit, read, rel, write


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
NAMES = ("吞吐 token/s", "P95 TTFT s", "P95 TPOT s", "完成率", "末端积压")


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def build() -> dict:
    index = read(HERE / "formal_index.json")
    frozen = read(SOURCE / "formal_reuse_index.json")
    graph = audit()
    result = {"experiment": "V3 same-layout canonical versus full DAG routing",
              "protocol": {"seeds": list(SEEDS), "duration_s": 1800, "warmup_s": 0,
                           "tail_drain": False, "loads": LOADS},
              "audit": graph, "failures": index["failures"], "cases": {}}
    lines = ["# V3 层兼容 DAG 路径空间核心消融", "",
             "两组均使用冻结的 V3 `multi_any` 部署、纯图 M1 和同一实时 M3 代价、"
             "平局顺序、Decode 固定路径及传输合并。只改变 Prompt 可选的合法边："
             "规范路径组禁止在同一层段的副本间切换；完整 DAG 组允许所有层兼容边。"
             "完整 DAG 的正式窗口来自 V3 冻结结果，经原始哈希复用。", "",
             "| 拓扑 | 规范边/路径 | 完整 DAG 边/路径 |",
             "| --- | ---: | ---: |"]
    for case in CASES:
        g = graph["cases"][case]
        lines.append(f"| {case} | {g['canonical_edges']}/{g['canonical_paths']} | "
                     f"{g['full_edges']}/{g['full_paths']} |")
    lines += ["", "## 逐种子配对结果", "",
              "| 拓扑 | 种子 | 路径集合 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 实际路径数 | 待完成驻留 P95 s |",
              "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in CASES:
        topo = case.removeprefix("C1_")
        result["cases"][case] = {}
        for seed in SEEDS:
            key = f"{case}/seed{seed}"
            item = index["jobs"].get(key)
            if not item or item["status"] != "passed":
                result["cases"][case][str(seed)] = {"status": "failed",
                    "error": index["failures"].get(key, "missing result")}
                continue
            canon_path = ROOT / item["source"]
            if digest(canon_path) != item["sha256"]:
                raise ValueError(f"Canonical raw SHA mismatch: {canon_path}")
            canon = read(canon_path)
            entry = next(x for x in frozen if x["scenario"] == topo and x["seed"] == seed)
            full_path = ROOT / entry["released"]
            if digest(full_path) != entry["released_sha256"]:
                raise ValueError(f"Frozen V3 raw SHA mismatch: {full_path}")
            full = read(full_path)
            if any(canon.get(k) != full.get(k) for k in MATCH_FIELDS):
                raise ValueError(f"Unpaired protocol or trace: {key}")
            if canon["physical_sha256"] != graph["cases"][case]["physical_sha256"] or \
                    canon["solution_sha256"] != graph["cases"][case]["solution_sha256"] or \
                    canon["sim_cluster_sha256"] != graph["cases"][case]["sim_cluster_sha256"]:
                raise ValueError(f"Canonical layout changed: {key}")
            if full["solution_sha256"] != canon["solution_sha256"] or \
                    full["sim_cluster_sha256"] != canon["sim_cluster_sha256"]:
                raise ValueError(f"Compared layouts differ: {key}")
            cohort = common_cohort(full, canon)
            common = common_completed(canon, full)
            pair = {"status": "passed", "sources": {
                "canonical": {"path": rel(canon_path), "sha256": item["sha256"]},
                "full_dag": {"path": rel(full_path), "sha256": entry["released_sha256"]}},
                "trace_sha256": canon["trace_sha256"], "paired_cohort": cohort,
                "common_completed": common,
                "metrics": {name: {"canonical": canon[name], "full_dag": full[name],
                                   "delta_full_minus_canonical": full[name] - canon[name]}
                            for name in METRICS},
                "pending": {"canonical": pending(canon), "full_dag": pending(full)},
                "paths": {"canonical": canon["path_use_audit"],
                          "full_dag": full.get("path_use_audit")}}
            result["cases"][case][str(seed)] = pair
            for label, row in (("规范路径", canon), ("完整 DAG", full)):
                paths = row.get("path_use_audit", {}).get("actual_distinct_paths", "—")
                lines.append(f"| {case} | {seed} | {label} | " +
                             " | ".join(_fmt(row[name]) for name in METRICS[:-1]) +
                             f" | {row['backlog_at_window_end']} | {paths} | "
                             f"{_fmt(pending(row)['p95_s'])} |")
    lines += ["", "## 三种子均值与配对方向", "",
              "| 拓扑 | 指标 | 规范路径均值 | 完整 DAG 均值 | 完整 DAG − 规范路径均值 | 逐种子差值 |",
              "| --- | --- | ---: | ---: | ---: | --- |"]
    for case in CASES:
        pairs = [p for p in result["cases"][case].values() if p["status"] == "passed"]
        for name, label in zip(METRICS, NAMES):
            if not pairs:
                continue
            a = [p["metrics"][name]["canonical"] for p in pairs]
            b = [p["metrics"][name]["full_dag"] for p in pairs]
            diff = [y - x for x, y in zip(a, b)]
            lines.append(f"| {case} | {label} | {_fmt(mean(a))} | {_fmt(mean(b))} | "
                         f"{_fmt(mean(diff))} | {', '.join(_fmt(x) for x in diff)} |")
    lines += ["", "## 实际路径使用", "",
              "| 拓扑 | 种子 | 规范路径实际使用 | 完整 DAG 实际使用 | 完整 DAG 跨副本请求比例 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for case in CASES:
        for seed, pair in result["cases"][case].items():
            if pair["status"] != "passed":
                continue
            canonical = pair["paths"]["canonical"]
            full = pair["paths"]["full_dag"]
            lines.append(f"| {case} | {seed} | {canonical['actual_distinct_paths']} | "
                         f"{full['actual_distinct_paths']} | "
                         f"{_fmt(full['cross_replica_fraction'])} |")
    lines += ["", "## 共同完成请求的尾延迟", "",
              "| 拓扑 | 种子 | 共同完成 | P95 TTFT 规范→完整 s | P95 TPOT 规范→完整 s |",
              "| --- | ---: | ---: | --- | --- |"]
    for case in CASES:
        for seed, pair in result["cases"][case].items():
            if pair["status"] != "passed":
                continue
            common = pair["common_completed"]
            lines.append(f"| {case} | {seed} | {common['count']} | "
                         f"{_fmt(common['ttft_s']['left_p95_s'])}→{_fmt(common['ttft_s']['right_p95_s'])} | "
                         f"{_fmt(common['tpot_s']['left_p95_s'])}→{_fmt(common['tpot_s']['right_p95_s'])} |")
    lines += ["", "## 判定", "",
              "单集群的三个种子中，规范路径在吞吐、TPOT、完成率和积压上均优于完整 DAG；"
              "共同完成请求的 TPOT 方向也一致。完整 DAG 在该拓扑使用了更多不同路径，"
              "但不能据此主张其路径灵活性改善性能。三集群的三个种子中，完整 DAG 在吞吐、"
              "TTFT、TPOT、完成率和积压上均优于规范路径；共同完成请求的尾延迟方向相同。"
              "因此本轮只支持路径灵活性在三集群网络条件下有用，不能宣称普遍增益。", "",
              "主指标仍需结合完成率、积压和未完成请求驻留时长解读，"
              "避免固定窗口截尾偏差。三个种子只描述方向与波动，不构成统计显著性证明。"
              "这项实验隔离的是完整 DAG 路径集合的在线效果，不单独证明 M1 图建模的性能收益。", ""]
    if index["failures"]:
        lines += ["## 失败记录", "", "```json",
                  json.dumps(index["failures"], indent=2, ensure_ascii=False), "```", ""]
    write(HERE / "formal_analysis.json", result)
    (HERE / "formal_report.md").write_text("\n".join(lines), encoding="utf-8")
    return result


if __name__ == "__main__":
    data = build()
    print(HERE / "formal_report.md")
    print("failures", len(data["failures"]))

"""Global fixed-window metrics and paired common-completion accounting for T2."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np


METRICS = (
    ("output_throughput_tokens_per_s", "吞吐 token/s"),
    ("ttft_p95_s", "P95 TTFT s"),
    ("tpot_p95_s", "P95 TPOT s"),
    ("completion_fraction", "完成率"),
    ("backlog_at_window_end", "末端积压"),
    ("common_completed_ttft_p95_s", "共同完成 P95 TTFT s"),
    ("common_completed_tpot_p95_s", "共同完成 P95 TPOT s"),
)


def p95(values):
    return float(np.percentile(values, 95)) if values else None


def mean_std(values):
    return {"mean": statistics.mean(values), "sample_std": statistics.stdev(values)}


def global_metrics(root: Path, index: dict, cases, seeds):
    formal = {key: json.loads((root / item["path"]).read_text(encoding="utf-8"))
              for key, item in index["jobs"].items()}
    result = {}
    lines = ["## 全局窗口指标", "", "配对差为完整 DAG 减规范路径；三种子标准差为样本标准差。不进行显著性检验。", ""]
    for case in cases:
        result[case] = {"paired_seeds": {}, "summaries": {}}
        for seed in seeds:
            canonical = formal[f"{case}/canonical/seed{seed}"]
            full = formal[f"{case}/full/seed{seed}"]
            canonical_queries = canonical["query_samples"]
            full_queries = full["query_samples"]
            common = sorted(uid for uid in canonical_queries.keys() & full_queries.keys()
                            if canonical_queries[uid]["completed"] and full_queries[uid]["completed"])
            pair = {"common_completed_queries": len(common), "canonical": {}, "full": {}, "difference": {}}
            for metric, _ in METRICS[:5]:
                pair["canonical"][metric] = canonical[metric]
                pair["full"][metric] = full[metric]
            for label, field in (("ttft", "ttft_s"), ("tpot", "tpot_s")):
                key = f"common_completed_{label}_p95_s"
                for variant, samples in (("canonical", canonical_queries), ("full", full_queries)):
                    values = [samples[uid][field] for uid in common if samples[uid][field] is not None]
                    pair[variant][key] = p95(values)
            for metric, _ in METRICS:
                a, b = pair["canonical"][metric], pair["full"][metric]
                pair["difference"][metric] = b - a if a is not None and b is not None else None
            result[case]["paired_seeds"][str(seed)] = pair
        lines += [f"### {case}", "", "| 指标 | 种子 | 规范路径 | 完整 DAG | 配对差 |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for metric, label in METRICS:
            values = {"canonical": [], "full": [], "difference": []}
            for seed in seeds:
                pair = result[case]["paired_seeds"][str(seed)]
                a = pair["canonical"][metric]
                b = pair["full"][metric]
                d = pair["difference"][metric]
                lines.append(f"| {label} | {seed} | {a:.6f} | {b:.6f} | {d:+.6f} |")
                values["canonical"].append(a)
                values["full"].append(b)
                values["difference"].append(d)
            stats = {variant: mean_std(series) for variant, series in values.items()}
            result[case]["summaries"][metric] = stats
            lines.append(f"| {label} 均值 ± SD | — | {stats['canonical']['mean']:.6f} ± {stats['canonical']['sample_std']:.6f} | {stats['full']['mean']:.6f} ± {stats['full']['sample_std']:.6f} | {stats['difference']['mean']:+.6f} ± {stats['difference']['sample_std']:.6f} |")
        lines += ["", "共同完成请求数：" + "；".join(
            f"种子 {seed} = {result[case]['paired_seeds'][str(seed)]['common_completed_queries']}"
            for seed in seeds), ""]
    return result, lines

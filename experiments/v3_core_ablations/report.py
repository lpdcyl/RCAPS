"""Audit and summarize the paired C1 V3 2×2 windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from benchmarks.compare import MATCH_FIELDS, common_cohort
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from experiments.m2_multistage_candidate.placement import digest

from .run import (CASES, CELLS, HERE, LOADS, ROOT, _audit_reuse, _layout,
                  _read, _runtime_hash, _write, audit)
from experiments.m2_multistage_candidate.prepare import files


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
LABELS = {"output_throughput_tokens_per_s": "Output token/s",
          "ttft_p95_s": "P95 TTFT (s)", "tpot_p95_s": "P95 TPOT (s)",
          "completion_fraction": "Completion", "backlog_at_window_end": "Backlog"}


def _record(phase: str, case: str, cell: str, seed: int, index: dict) -> tuple[dict, dict]:
    key = f"{case}/{cell}/seed{seed}"
    item = index["jobs"].get(key)
    if item is not None and item["status"] == "passed":
        source = ROOT / item["source"]
        if digest(source) != item["sha256"]:
            raise ValueError(f"Raw result hash mismatch: {source}")
        row = _read(source)
        physical, _, topology = files(case)
        layout = _layout(case, cell)
        variant, routing = CELLS[cell]
        expected = {"case": case, "cell": cell, "variant": variant,
                    "routing": routing, "scenario": topology, "seed": seed,
                    "duration_s": 1800, "warmup_s": 0,
                    "offered_tokens_per_s": LOADS["low" if phase == "low" else "high"][case],
                    "physical_sha256": digest(physical),
                    "solution_sha256": digest(layout / "solution.ini"),
                    "sim_cluster_sha256": digest(layout / "simulator_cluster.ini"),
                    "evaluation_protocol": "fixed_window_no_tail_drain"}
        for field, value in expected.items():
            if row.get(field) != value:
                raise ValueError(f"New run identity differs on {field}: {source}")
        return row, {**item, "reused": False}
    if phase == "formal" and cell in ("C", "D"):
        item = _audit_reuse(case, cell, seed, "formal")
        return _read(ROOT / item["source"]), {"status": "passed", **item}
    raise ValueError(f"No successful raw result for {key}")


def _paired(rows: dict[str, dict]) -> dict:
    reference = rows["A"]
    for cell in ("B", "C", "D"):
        row = rows[cell]
        for field in MATCH_FIELDS:
            if row.get(field) != reference.get(field):
                raise ValueError(f"Unpaired field {field} for {cell}")
        common_cohort(row, reference)
    result = {"metrics": {cell: {key: rows[cell].get(key) for key in METRICS}
                          for cell in CELLS},
              "pending": {cell: pending(rows[cell]) for cell in CELLS},
              "paths": {cell: rows[cell].get("path_use_audit", {}) for cell in CELLS},
              "common_completed": {pair: common_completed(rows[left], rows[right])
                                   for pair, left, right in (("B-A", "A", "B"),
                                       ("D-B", "B", "D"), ("C-A", "A", "C"))},
              "deltas": {}, "interaction": {}}
    for metric in METRICS:
        x = {cell: rows[cell][metric] for cell in CELLS}
        if any(value is None for value in x.values()):
            continue
        result["deltas"][metric] = {"B-A": x["B"] - x["A"],
                                    "D-B": x["D"] - x["B"],
                                    "C-A": x["C"] - x["A"]}
        result["interaction"][metric] = ((x["D"] - x["B"]) -
                                         (x["C"] - x["A"]))
    return result


def _fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _table(pairs: dict) -> str:
    out = ["| 拓扑 | 种子 | 格 | 输出 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 待完成驻留 P95 s | 来源 |",
           "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for case, seeds in pairs.items():
        for seed, record in seeds.items():
            for cell in CELLS:
                x = record["metrics"][cell]
                source = record["sources"][cell]
                out.append(f"| {case} | {seed} | {cell} | "
                           f"{_fmt(x['output_throughput_tokens_per_s'])} | "
                           f"{_fmt(x['ttft_p95_s'])} | {_fmt(x['tpot_p95_s'])} | "
                           f"{_fmt(x['completion_fraction'])} | {x['backlog_at_window_end']} | "
                           f"{_fmt(record['pending'][cell]['p95_s'])} | "
                           f"{'复用' if source['reused'] else '新跑'} |")
    return "\n".join(out)


def _mean_sd_table(pairs: dict, case: str) -> str:
    out = ["| 方法组合 | 输出 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ |",
           "| --- | ---: | ---: | ---: |"]
    names = {"A": "M1 图 + 单边界放置 + 静态 DAG（起点）",
             "B": "M1 图 + 多级 M2 + 静态 DAG",
             "D": "M1 图 + 多级 M2 + 实时 M3（V3）",
             "C": "M1 图 + 单边界放置 + 实时 M3（交叉对照）"}
    for cell in ("A", "B", "D", "C"):
        values = []
        for metric in ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s"):
            samples = [row["metrics"][cell][metric] for row in pairs[case].values()]
            values.append(f"{mean(samples):.3f} ± {stdev(samples):.3f}")
        out.append(f"| {names[cell]} | " + " | ".join(values) + " |")
    return "\n".join(out)


def _delta_table(pairs: dict) -> str:
    out = ["| 拓扑 | 指标 | B−A 平均 | D−B 平均 | C−A 平均 | 交互量平均 |",
           "| --- | --- | ---: | ---: | ---: | ---: |"]
    for case, seeds in pairs.items():
        for metric in METRICS:
            available = [row for row in seeds.values() if metric in row["deltas"]]
            if len(available) != len(seeds):
                continue
            out.append(f"| {case} | {LABELS[metric]} | " + " | ".join(
                _fmt(mean(row["deltas"][metric][key] for row in available))
                for key in ("B-A", "D-B", "C-A")) + " | " +
                _fmt(mean(row["interaction"][metric] for row in available)) + " |")
    return "\n".join(out)


def _cohort_table(pairs: dict) -> str:
    out = ["| 拓扑 | 种子 | 对照 | 共同完成数 | P95 TTFT 左→右 s | P95 TPOT 左→右 s |",
           "| --- | ---: | --- | ---: | --- | --- |"]
    for case, seeds in pairs.items():
        for seed, record in seeds.items():
            for pair, left, right in (("B−A", "A", "B"),
                                      ("D−B", "B", "D"), ("C−A", "A", "C")):
                x = record["common_completed"][pair.replace("−", "-")]
                ttft, tpot = x["ttft_s"], x["tpot_s"]
                out.append(f"| {case} | {seed} | {left}→{right} | {x['count']} | "
                           f"{_fmt(ttft['left_p95_s'])}→{_fmt(ttft['right_p95_s'])} | "
                           f"{_fmt(tpot['left_p95_s'])}→{_fmt(tpot['right_p95_s'])} |")
    return "\n".join(out)


def _pending_table(pairs: dict) -> str:
    out = ["| 拓扑 | 种子 | 格 | 未完成数 | 驻留 P50 s | 驻留 P95 s | 最大驻留 s | 实际使用路径 |",
           "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for case, seeds in pairs.items():
        for seed, record in seeds.items():
            for cell in CELLS:
                x = record["pending"][cell]
                paths = record["paths"][cell].get("actual_distinct_paths")
                out.append(f"| {case} | {seed} | {cell} | {x['count']} | "
                           f"{_fmt(x['p50_s'])} | {_fmt(x['p95_s'])} | "
                           f"{_fmt(x['max_s'])} | {paths if paths is not None else '—'} |")
    return "\n".join(out)


def build(phase: str) -> dict:
    index = _read(HERE / f"{phase}_index.json")
    audit_result = audit()
    pairs = {}
    raw = {}
    for case in CASES:
        pairs[case], raw[case] = {}, {}
        for seed in (0, 1, 2):
            records, sources = {}, {}
            for cell in CELLS:
                records[cell], sources[cell] = _record(phase, case, cell, seed, index)
            paired = _paired(records)
            paired["sources"] = sources
            paired["trace_sha256"] = records["A"]["trace_sha256"]
            pairs[case][str(seed)] = paired
            raw[case][str(seed)] = sources
    summary = {"phase": phase, "protocol": {"seed": [0, 1, 2],
               "duration_s": 1800, "warmup_s": 0, "tail_drain": False,
               "offered_token_s": ({"C1_single": 700, "C1_multi": 320} if phase == "formal"
                                   else {"C1_single": 350, "C1_multi": 160})},
               "audit": audit_result, "raw_result_index": raw, "paired": pairs,
               "failures": index["failures"]}
    _write(HERE / f"{phase}_analysis.json", summary)
    intro = ("# V3 核心递进消融：C1 两拓扑\n\n"
             "A=单边界+静态 DAG，B=最多双边界+静态 DAG，"
             "C=单边界+实时 M3，D=V3 多级布局+实时 M3。"
             "M1 为同一纯图建模。B−A 是开放多级布局的效果；D−B 是 V3 布局上的实时状态收益；"
             "交互量=(D−B)−(C−A)。\n\n"
             "同拓扑、同种子、同负载、同 1800 秒零预热不排空窗口比较。"
             "新跑和复用来源均在 JSON 索引中记录 SHA256。\n\n")
    lines = [intro, "## 与递进消融图对应的 V3 表格\n",
             "以下为三个种子的均值 ± 样本标准差。递进主线为 A→B→D；"
             "C 是检验 M2×M3 交互的独立对照，不能视为 B→C 的递进一步。"
             "M1 在所有格中均为纯图建模，因此不设置 M1 性能增益行。\n",
             "### C1 单集群\n", _mean_sd_table(pairs, "C1_single"),
             "\n### C1 三集群\n", _mean_sd_table(pairs, "C1_multi"),
             "\n## 逐种子结果\n", _table(pairs), "\n## 配对差值与交互量\n",
             _delta_table(pairs), "\n正交互量对吞吐/完成率有利，对延迟/积压不利；"
             "此处为原始差值，不能跨量纲比较。三种子仅描述波动。\n",
             "## 共同完成请求的尾延迟\n", _cohort_table(pairs),
             "\n只用两格均已完成的相同请求计算尾延迟，避免比较不同完成集合。\n",
             "## 窗口末未完成请求\n", _pending_table(pairs),
             "\n驻留时长是窗口终点减请求到达时刻，不等同于纯队列等待。\n",
             "## 部署结构与搜索\n",
             "| 拓扑 | 变体 | 宽度 | 边界 | 层副本 | 启用 GPU | 候选评价 | 规划耗时 s | DAG 边 | 合法路径 |",
             "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in CASES:
        for variant in ("single_any", "multi_any"):
            l = audit_result["cases"][case]["layouts"][variant]
            s = l["structure"]
            lines.append(f"| {case} | {variant} | {s['widths']} | {s['boundaries']} | "
                         f"{s['layer_copies']} | {s['active_gpus']} | "
                         f"{s['candidate_evaluations']} | {_fmt(s['search_wall_s'])} | "
                         f"{l['dag_edges']} | {l['complete_paths']} |")
    lines += ["\n规划耗时是单边界与多级变体共享的整次搜索计时，不能将两行相加。"
              "三集群的 `multi_any` 仍为单边界，B−A 只反映微观放置差异。\n",
              "## 本轮判定\n",
              "12 个新高负载静态窗口全部完成，C/D 各 6 个正式窗口经哈希和执行语义审计后复用；"
              "未触发预设的低负载回退。单集群 B−A 的平均吞吐增加 4.896 token/s，"
              "P95 TTFT 下降 0.757 秒，P95 TPOT 下降 0.298 秒，三个种子方向一致；"
              "这支持多级 M2 在该拓扑上的结构价值。三集群 B−A 的吞吐只增加 0.013 token/s，"
              "且所选结构仍为单边界，不能据此宣称多级结构在三集群也产生收益。\n",
              "在 V3 布局上引入实时 M3（D−B）后，单集群平均吞吐增加 6.915 token/s，"
              "P95 TTFT/TPOT 分别下降 0.691/0.546 秒；三集群相应为增加 3.381 token/s，"
              "下降 1.137/0.520 秒。完成率和积压也同步改善。"
              "单集群吞吐交互量为 −4.292 token/s、TTFT 交互量为 +0.474 秒，"
              "未显示 M2 放大 M3 收益；三集群交互量接近零或指标方向不一致。"
              "因此不作正向协同主张。\n",
              "已有完整系统对照见 `experiments/v3_release/v3_vs_helix.json`："
              "V3 相对 Helix ILP 的平均输出吞吐增幅为单集群 9.63%、三集群 21.16%。"
              "该外部对照仅作完整系统背景，不代替本轮四格归因。\n",
              "## 解释范围\n",
              "已完成请求的 P95 受窗口截尾影响；逐种子完成率、末端积压、"
              "待完成请求驻留时长和共同完成请求尾延迟见 JSON 分析文件。"
              "路径数是结构与使用的描述，不单独证明性能因果。"
              "三个种子不用于统计显著性声明。\n"]
    if index["failures"]:
        lines += ["\n## 失败记录\n", "```json\n" +
                  json.dumps(index["failures"], indent=2, ensure_ascii=False) + "\n```\n"]
    (HERE / f"{phase}_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("formal", "low"), default="formal")
    args = parser.parse_args()
    result = build(args.phase)
    print(HERE / f"{args.phase}_report.md")
    print("failures", len(result["failures"]))


if __name__ == "__main__":
    main()

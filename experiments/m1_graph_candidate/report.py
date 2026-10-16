"""Report graph-only M1 and audited seed-0/1/2 paired evidence."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.m1_simplification.evidence import LOADS, SEEDS, digest, paired
from experiments.m1_simplification.report import (METRICS, common_completed,
                                                   describe, pending)

from .run import HERE, ROOT, SYSTEMS, choose, reuse_gate


LABELS = {"m1_graph_candidate": "纯图 M1 + 静态 M2",
          "v2_reference": "冻结 V2（迁移参考）"}


def collect() -> dict:
    audit = json.loads((HERE / "layout_audit.json").read_text(encoding="utf-8"))
    parity = json.loads((HERE / "route_parity.json").read_text(encoding="utf-8"))
    index = json.loads((HERE / "run_index.json").read_text(encoding="utf-8"))
    paths = json.loads((HERE / "path_analysis.json").read_text(encoding="utf-8"))
    stress = json.loads((HERE / "stress_route_parity.json").read_text(encoding="utf-8"))
    if not all(row["passed"] for row in stress["rows"]):
        raise ValueError("Offered-load M3 parity failed")
    indexed = {(row["scenario"], row["seed"]): row for row in index}
    path_indexed = {(row["scenario"], row["seed"]): row for row in paths["rows"]}
    rows = []
    for name in LOADS:
        gate = reuse_gate(name, parity, audit)
        for seed in SEEDS:
            selection = {system: choose(name, seed, system, gate)
                         for system in SYSTEMS}
            saved = indexed[name, seed]
            for system in SYSTEMS:
                source = selection[system][1]
                if (selection[system][0] is None or
                        source["sha256"] != saved["sources"][system]["sha256"] or
                        source["source"] != saved["sources"][system]["source"]):
                    raise ValueError(f"Stale formal index: {name}/seed{seed}/{system}")
            path_row = path_indexed[name, seed]
            if (path_row["source_sha256"] != saved["sources"]["m1_graph_candidate"]["sha256"]
                    or not path_row["all_recorded_paths_valid"]):
                raise ValueError(f"Stale path audit: {name}/seed{seed}")
            candidate, reference = (selection[system][0] for system in SYSTEMS)
            pair = paired(candidate, reference)
            rows.append({"scenario": name, "seed": seed,
                         "sources": {system: selection[system][1]
                                     for system in SYSTEMS},
                         "paired_trace": pair,
                         "metrics": {system: {key: selection[system][0][key]
                                              for key in METRICS}
                                     for system in SYSTEMS},
                         "candidate_minus_v2": {
                             key: candidate[key] - reference[key]
                             for key in METRICS},
                         "common_completed": common_completed(candidate, reference),
                         "pending": {system: pending(selection[system][0])
                                     for system in SYSTEMS}})
    aggregate = {}
    for name in LOADS:
        subset = [row for row in rows if row["scenario"] == name]
        aggregate[name] = {
            system: {key: describe([row["metrics"][system][key]
                                    for row in subset]) for key in METRICS}
            for system in SYSTEMS}
        aggregate[name]["candidate_minus_v2"] = {
            key: describe([row["candidate_minus_v2"][key] for row in subset])
            for key in METRICS}
    return {"protocol": {"model": "LLaMA-70B", "loads": LOADS,
                         "seeds": SEEDS, "duration_s": 1800, "warmup_s": 0,
                         "tail_drain": False,
                         "candidate_scheduler":
                         "GraphModeledQueueAwareDagScheduler",
                         "reference_scheduler": "QueueAwareDagScheduler"},
            "layout_audit": audit, "route_parity": parity,
            "path_analysis": paths, "stress_route_parity": stress,
            "rows": rows, "aggregate": aggregate,
            "source_code_sha256": {
                "resource_graph": digest(ROOT / "rcaps/placement/resource_graph.py"),
                "static_M2": digest(ROOT / "rcaps/placement/static_resource.py"),
                "adaptive_search": digest(ROOT / "rcaps/placement/adaptive.py"),
                "M3_adapter": digest(HERE / "scheduler.py")}}


def fmt(value, digits=3):
    return "—" if value is None else f"{value:.{digits}f}"


def markdown(result: dict) -> str:
    lines = ["# M1 纯图建模：独立候选验证", "",
             "M1 只表示异构 GPU、物理链路及给定布局的层兼容 DAG。"
             "M2 沿用已验证的强静态代价、0.40／0.35／0.25 权重、参考布局与搜索规则；"
             "M3 保持实时路径代价及 Decode 传输语义。新调用链不模拟六请求事件。", "",
             "## 图与布局一致性", "",
             "| 拓扑 | 物理有向边 | 层兼容边 | 合法完整路径 | 共享 GPU／层／后缀 | 候选评价数 | 规划秒数 |",
             "| --- | ---: | ---: | ---: | --- | ---: | ---: |"]
    for name, label in (("single", "单集群"), ("multi", "三集群")):
        item = result["layout_audit"][name]
        lines.append(f"| {label} | {item['physical_directed_edges']} | "
                     f"{item['compatibility_edges']} | {item['compatible_paths']} | "
                     f"{item['shared_gpus']}／{item['shared_layers']}／"
                     f"{item['canonical_suffixes']} | "
                     f"{item['candidate_evaluations']} | "
                     f"{fmt(item['planning_s'], 2)} |")
    lines.extend(["", "两个拓扑的评分、评分参考、布局语义及两份部署文件 SHA256 均与第一阶段"
                  "强静态候选一致。现有布局审计通过层覆盖、显存、KV 容量、物理链路及"
                  "导出边检查。固定轨迹上，M3 新旧入口的逐请求路由、指标、运行时 DAG "
                  "边数与路径数一致；详见 `route_parity.json`。规划时间是本次单次墙钟"
                  "测量，不作为稳定加速比。", "",
                  "## 实际执行路径", "",
                  "正式窗口原始记录的每条路径均经过 M1 图逐边及层连续性核验。"
                  "下表分母为窗口内已分配路径的请求；少量到达请求在窗口末尚未分配路径。"
                  "‘跨后缀’指连续两张 GPU 属于不同规范后缀，不包括共享前缀到后缀的边。", "",
                  "| 拓扑 | 种子 | 已路由／到达请求 | 实际不同路径 | 非规范路径占比 | 已用／合法跨后缀边 | 跨后缀请求占比 | GPU 忙碌率范围 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in result["path_analysis"]["rows"]:
        label = "单集群" if row["scenario"] == "single" else "三集群"
        busy = list(row["gpu_busy_fraction"].values())
        busy_range = (f"{min(busy):.1%}–{max(busy):.1%}" if busy else "未记录")
        lines.append(f"| {label} | {row['seed']} | "
                     f"{row['routed_requests']}／{row['arrivals']} | "
                     f"{row['distinct_used_paths']} | "
                     f"{row['noncanonical_path_fraction_of_routed']:.1%} | "
                     f"{row['distinct_used_cross_suffix_edges']}／"
                     f"{row['legal_cross_suffix_edges']} | "
                     f"{row['cross_suffix_path_fraction_of_routed']:.1%} | "
                     f"{busy_range} |")
    stress = result["stress_route_parity"]["rows"]
    lines.extend(["", "实际路径数远少于理论合法路径数；非规范路径在这六个窗口中"
                  "主要体现为跨后缀拼接。它说明 M3 利用了布局提供的灵活性，"
                  "不单独证明拼接带来性能增益。逐 GPU 忙碌率及路径经过次数见"
                  " `path_analysis.json`。", "",
                  "## 在线语义回归", "",
                  "除固定 12 请求轨迹外，还在正式 offered load 下以开发种子 100／101 "
                  "各运行 300 秒短窗口。原 M3 与图接口 M3 的逐请求完整路由、"
                  "请求样本和窗口指标精确一致；这是行为回归检查，正式结果仍使用"
                  "种子 0／1／2。", "",
                  "| 拓扑 | 开发种子 | 到达请求 | 已分配路径 | 逐请求路由及指标一致 |",
                  "| --- | ---: | ---: | ---: | --- |"])
    for row in stress:
        label = "单集群" if row["scenario"] == "single" else "三集群"
        lines.append(f"| {label} | {row['seed']} | {row['arrivals']} | "
                     f"{row['route_assignments']} | {'是' if row['passed'] else '否'} |")
    lines.extend(["", "短窗口原始回归摘要和轨迹 SHA256 见 `stress_route_parity.json`。", "",
                  "## 种子 0／1／2 迁移回归结果", "",
                  "本节只检查方法改造后系统行为与原实现是否处于相近范围。"
                  "冻结 V2 是历史实现参考，不是论文中证明 M1、M2 或 M3 有效性的性能基线；"
                  "两者的 M2 评价方式及单集群后缀数也不同。以下保留全部数值差异，"
                  "不据此宣称统计等效或相对 V2 的优势。", "",
                  "单集群负载 700、三集群负载 320 offered token/s；每次 1800 秒，"
                  "零预热，末端不排空。逐种子 P95 再取均值。布局哈希、执行语义、轨迹"
                  "与请求身份审计通过，因此六个候选窗口和六个 V2 窗口均复用既有原始"
                  "记录，没有重新运行正式窗口。", "",
                  "| 拓扑 | 方法 | 吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s/token ↓ | 完成率 ↑ | 末端积压 ↓ |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for name, label in (("single", "单集群"), ("multi", "三集群")):
        for system in SYSTEMS:
            values = result["aggregate"][name][system]
            lines.append(f"| {label} | {LABELS[system]} | "
                         f"{fmt(values['output_throughput_tokens_per_s']['mean'])} | "
                         f"{fmt(values['ttft_p95_s']['mean'])} | "
                         f"{fmt(values['tpot_p95_s']['mean'])} | "
                         f"{fmt(values['completion_fraction']['mean'])} | "
                         f"{fmt(values['backlog_at_window_end']['mean'], 1)} |")
    lines.extend(["", "逐种子原始配对值如下，每格依次为纯图候选／冻结 V2。", "",
                  "| 拓扑 | 种子 | 吞吐 token/s | P95 TTFT s | P95 TPOT s/token | 完成率 | 末端积压 | 共同完成数 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in result["rows"]:
        left, right = (row["metrics"][system] for system in SYSTEMS)
        label = "单集群" if row["scenario"] == "single" else "三集群"
        pair = lambda key, digits=3: (f"{fmt(left[key], digits)} / "
                                      f"{fmt(right[key], digits)}")
        lines.append(f"| {label} | {row['seed']} | "
                     f"{pair('output_throughput_tokens_per_s')} | "
                     f"{pair('ttft_p95_s')} | {pair('tpot_p95_s')} | "
                     f"{pair('completion_fraction')} | "
                     f"{pair('backlog_at_window_end', 0)} | "
                     f"{row['common_completed']['count']} |")
    lines.extend(["", "共同完成请求的 P95、未完成请求驻留时长分布、每份原始 JSON 的"
                  "路径与 SHA256 均在 `summary.json`。", "",
                  "## 判定", "",
                  "M1 的验收依据是资源与层兼容图合法、M2 和 M3 读取同一合法边集、"
                  "重构后静态评分与选路行为保持一致。以上检查均通过。"
                  "相对冻结 V2，候选的吞吐处于相近范围，平均 P95 尾延迟略高；"
                  "三个种子只描述波动，不构成统计等效性证明。", "",
                  "论文中的在线性能主张应分别由 M2 的受控放置对照、M3 的同布局调度对照，"
                  "以及完整系统对 Helix 等外部方法的同轨迹比较建立。"
                  "当前图合法性和路径使用记录不替代这些性能实验。", "",
                  "复现命令见 [README_CN.md](README_CN.md)。"])
    return "\n".join(lines) + "\n"


def main() -> None:
    result = collect()
    (HERE / "summary.json").write_text(json.dumps(result, indent=2) + "\n",
                                       encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text(markdown(result), encoding="utf-8")
    print(HERE / "RESULTS_CN.md")


if __name__ == "__main__":
    main()

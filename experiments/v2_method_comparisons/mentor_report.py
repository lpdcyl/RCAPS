"""Render the advisor-facing tables from audited whole-method results."""

from __future__ import annotations

import json
from html import escape

from benchmarks.compare import MATCH_FIELDS, common_cohort

from .report import (GROUPS, KEYS, OLD, ROOT, SEEDS, aggregate, audited_record,
                     fmt, paired)


DESTINATION = ROOT / "experiments" / "v2_method_ablation" / "ADVISOR_MAIN_TABLE_CN.md"
LOW_SUMMARY = ROOT / "experiments" / "helix_additional_baselines" / "common_low_summary.json"
SCENARIOS = (("single", "单集群", 700), ("multi", "三集群", 320))
SHORT_LABELS = ("吞吐 ↑", "P95 TTFT ↓", "P95 TPOT ↓", "完成率 % ↑", "积压 ↓")


def checked(method: str, scenario: str) -> list[dict]:
    rows = []
    for seed in SEEDS:
        row, audit = audited_record(method, scenario, seed)
        if row is None:
            raise RuntimeError(f"Incomplete {scenario} seed{seed} {method}: {audit}")
        rows.append(row)
    return rows


def helix_rows(scenario: str, v2_rows: list[dict]) -> list[dict]:
    rows = []
    for seed, v2 in zip(SEEDS, v2_rows):
        path = OLD / scenario / f"seed{seed}" / "helix.json"
        helix = json.loads(path.read_text(encoding="utf-8"))
        for field in MATCH_FIELDS:
            if helix.get(field) != v2.get(field):
                raise ValueError(f"Helix mismatch: {scenario}/seed{seed}/{field}")
        common_cohort(v2, helix)
        rows.append(helix)
    return rows


def dual_table(methods: list[tuple[str, dict[str, list[dict]]]]) -> list[str]:
    def border(index: int) -> str:
        return ' style="border-left: 1px solid;"' if index == 0 else ""

    lines = ['<table style="border-collapse: collapse; border-top: 2px solid; border-bottom: 2px solid; white-space: nowrap;">',
             "<thead>",
             '<tr><th rowspan="2" style="text-align: left;">方法</th><th colspan="5">单集群 700 token/s</th><th colspan="5" style="border-left: 1px solid;">三集群 320 token/s</th></tr>',
             "<tr>" + "".join(f"<th>{escape(label)}</th>" for label in SHORT_LABELS) +
             "".join(f'<th{border(index)}>{escape(label)}</th>'
                     for index, label in enumerate(SHORT_LABELS)) + "</tr>",
             "</thead>", "<tbody>"]
    for label, scenario_rows in methods:
        cells = []
        for scenario, _, _ in SCENARIOS:
            summary = aggregate(scenario_rows[scenario])
            cells.extend(fmt(summary[key], key) for key in KEYS)
        body = "".join(f'<td{border(index - 5)}>{escape(value)}</td>'
                       for index, value in enumerate(cells))
        lines.append(f"<tr><td>{escape(label)}</td>{body}</tr>")
    lines.extend(["</tbody>", "</table>"])
    return lines


def paired_table(methods: list[tuple[str, dict[str, list[dict]]]],
                 v2: dict[str, list[dict]], heading: str =
                 "完整 V2 相对各替代方案的同种子配对改善") -> list[str]:
    lines = [heading + "；正值表示吞吐提高或延迟降低。",
             "", "| 对照 | 单集群吞吐 ↑ | 单集群 TTFT ↓ | 单集群 TPOT ↓ | 三集群吞吐 ↑ | 三集群 TTFT ↓ | 三集群 TPOT ↓ |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, scenario_rows in methods:
        values = []
        for scenario, _, _ in SCENARIOS:
            effect = paired(v2[scenario], scenario_rows[scenario])
            for key in KEYS[:3]:
                stat = effect[key]
                values.append(f"{stat['mean']:+.2f} ± {stat['sample_sd']:.2f}%")
        lines.append("| " + label + " | " + " | ".join(values) + " |")
    return lines


def low_table() -> list[str]:
    summary = json.loads(LOW_SUMMARY.read_text(encoding="utf-8"))
    lines = ["## 外部系统补充：四方法共同较低负载", "",
             "单集群 350、三集群 160 token/s；此档与上面的高负载分开解读。",
             "四方法均使用相同请求轨迹和种子 0/1/2 的完整窗口。", "",
             "| 拓扑 | 方法 | 吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 % ↑ | 积压 ↓ |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    labels = (("helix", "Helix"), ("swarm", "Swarm"),
              ("separate", "SP"), ("rcaps_v2", "RCAPS V2"))
    for scenario, scenario_label, _ in SCENARIOS:
        for method, label in labels:
            stats = summary["scenarios"][scenario]["methods"][method]
            cells = [fmt(stats[key], key) for key in KEYS]
            lines.append("| " + scenario_label + " | " + label + " | " +
                         " | ".join(cells) + " |")
    return lines


def main() -> None:
    v2 = {scenario: checked("rcaps_v2", scenario) for scenario, _, _ in SCENARIOS}
    groups = []
    for name, options in GROUPS.items():
        entries = []
        for label, method in options:
            entries.append((label, {scenario: checked(method, scenario)
                                    for scenario, _, _ in SCENARIOS}))
        groups.append((name, entries))
    helix = {scenario: helix_rows(scenario, v2[scenario])
             for scenario, _, _ in SCENARIOS}
    lines = ["# RCAPS V2 导师汇报：三项完整方法替换对照", "",
             "**核心问题：在异构 GPU 环境下，提高 LLM 推理吞吐量，降低请求尾延迟。**", "",
             "| 挑战 | 本文完整方法 | 两种同功能替代 |",
             "| --- | --- | --- |",
             "| M1：异构资源与执行竞争如何评价？ | 多请求资源竞争事件 DAG 模型 | 容量与连通性模型；静态异构资源模型 |",
             "| M2：如何选择共享复制结构？ | V2 自适应共享复制搜索 | 固定共享复制结构；有界 beam search |",
             "| M3：动态请求如何调度？ | 在线 DAG 选路与传输协调 | 固定路径轮转；负载感知完整流水线 |", "",
             "每组固定另外两项 V2 方法，只整体替换当前方法；各组差额不能相加。",
             "70B、两种 24-GPU 拓扑、种子 0/1/2、1800 秒零预热；单集群 700、三集群 320 提供 token/s。",
             "每格为三种子均值 ± 样本标准差，吞吐单位为完成请求输出 token/s，P95 单位为秒。",
             "三种新增较强替代完成 18/18 个正式窗口；简单替代、V2 与 Helix 使用已存窗口，经布局、轨迹、请求身份和协议审计后复用。", "",
             "## 外部系统主对比：V2 与 Helix", ""]
    lines.extend(dual_table([("Helix", helix), ("RCAPS V2", v2)]))
    lines.extend(["", *paired_table([("Helix", helix)], v2,
                                    "完整 V2 相对 Helix 的同种子配对改善"), ""])
    for name, entries in groups:
        lines.extend(["## " + name + "（完整方法替换）", ""])
        lines.extend(dual_table(entries))
        lines.extend(["", *paired_table(entries[:-1], v2), ""])
    lines.extend(["## 结果解读", "",
                  "- **M1：** 相对只看容量与连通性的放置，完整模型在两种拓扑均降低尾延迟。相对静态异构资源模型，单集群有小幅改善；三集群吞吐与完成率略低、TPOT 较低，六个开发候选的排序也与静态模型相同。事件 DAG 的单候选评价中位耗时约 31 ms，静态模型约 0.2 ms。因此，不能宣称事件 DAG 在所有拓扑上具有全面独立增益。",
                  "- **M2：** 自适应共享复制明显优于固定结构。相同评价上限下，beam search 与 V2 搜索均选出 4 张共享 GPU、48 层前缀和 3 条后缀，性能接近；具体 V2 搜索策略未显示稳定的全面优势。",
                  "- **M3：** 完整在线 DAG 调度在两种拓扑均优于固定轮转与负载感知完整流水线。完整流水线方法会将较多请求集中在单一路径；详细路径占比与资源等待见审计报告。这是整调度方法的差额，不能拆给单个代价项或传输步骤。", ""])
    lines.extend(low_table())
    lines.extend(["", "## 证据与解释边界", "",
                  "M1 三种完整离线评价方案均检查显存、层连续覆盖和物理连通性；静态模型评估 GPU 服务及链路代价，但不构建多请求事件依赖。",
                  "M2 三种放置方法共用 V2 事件 DAG 评价器和在线调度器；beam 宽度为 4、至多 16 轮，候选评价上限等于原 V2 对应拓扑的正式搜索预算。",
                  "M3 三种在线方法使用字节相同的 V2 布局；完整流水线方法可感知实时负担，但只在三条规范路径中选路，Decode 固定路径并逐请求传输。",
                  "共同可观测请求 P95、搜索预算和路径/等待画像见[完整审计报告](../v2_method_comparisons/RESULTS_CN.md)；逐种子原值、布局哈希及复用来源见[机器可读审计汇总](../v2_method_comparisons/summary.json)。",
                  "四方法共同低负载的原始协议与审计见[独立报告](../helix_additional_baselines/COMMON_LOW_SUMMARY_CN.md)。",
                  "已有 A+B+C 递进、逐项去除及细组件实验保留为补充材料，不作为这三组主消融。",
                  "若某替代方案与 V2 表现接近或胜出，应按实测收窄对应贡献；三个种子仅描述配对波动，不支持统计显著性或真实集群性能声明。", ""])
    DESTINATION.write_text("\n".join(lines), encoding="utf-8")
    print(DESTINATION)


if __name__ == "__main__":
    main()

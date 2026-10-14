"""Audit and summarize the V2 base -> A -> A+B -> A+B+C ladder."""

from __future__ import annotations

import json
import math
from statistics import mean, stdev

from benchmarks.registry import METHODS
from benchmarks.run import ROOT, output_file
from experiments.v2_method_ablation.report import (
    HERE, METRICS, RUNS, SCENARIOS, SEEDS, digest, load, validate_layout,
    validate_pair,
)


STAGES = (
    ("基础方案", "rcaps_v2_base_safe_static"),
    ("A：异构资源感知放置", "rcaps_v2_fixed_safe_static"),
    ("A+B：自适应共享复制", "rcaps_v2_adaptive_safe_static"),
    ("A+B+C：动态调度", "rcaps_v2"),
)
FIELDS = tuple(item[0] for item in METRICS)


def stats(values: list[float]) -> dict:
    if len(values) != len(SEEDS) or any(not math.isfinite(value) for value in values):
        raise ValueError("Missing or nonfinite formal-window metric")
    return {"mean": mean(values), "sample_sd": stdev(values),
            "by_seed": dict(zip(SEEDS, values))}


def signed_improvement(new: float, old: float, higher: bool) -> float:
    if old <= 0:
        raise ValueError("Cannot compute paired relative improvement from zero baseline")
    return 100 * ((new / old - 1) if higher else (1 - new / old))


def format_stat(item: dict, field: str) -> str:
    factor = 100 if field == "completion_fraction" else 1
    digits = 1 if field == "backlog_at_window_end" else 3
    return f"{item['mean'] * factor:.{digits}f} ± {item['sample_sd'] * factor:.{digits}f}"


def format_gain(item: dict) -> str:
    return f"{item['mean']:+.2f} ± {item['sample_sd']:.2f}%"


def verify_stage_layouts(scenario: str) -> dict:
    static = METHODS[STAGES[0][1]].evaluate
    if any(METHODS[method].evaluate is not static for _, method in STAGES[:-1]):
        raise ValueError("The base, A and A+B stages do not use the same static scheduler")
    if METHODS[STAGES[-1][1]].evaluate is static:
        raise ValueError("The final V2 stage does not use its dynamic scheduler")
    layouts = {method: validate_layout(scenario, method) for _, method in STAGES}
    if any(item["gpu_count"] != 24 for item in layouts.values()):
        raise ValueError(f"{scenario}: ladder stage does not use the 24-GPU pool")
    base, a, ab, abc = (layouts[method] for _, method in STAGES)
    for name, item in (("base", base), ("A", a)):
        if item["prefix_layers"] != 12 or len(item["stem"]) != 1 or item["suffix_count"] != 2:
            raise ValueError(f"{scenario} {name} is not the specified fixed structure")
    for field in ("solution_sha256", "sim_cluster_sha256"):
        if ab[field] != abc[field]:
            raise ValueError(f"{scenario}: A+B and A+B+C differ in layout")
    source = METHODS["rcaps_v2_fixed_structure"].layout(scenario, ROOT)
    fixed = METHODS["rcaps_v2_fixed_safe_static"].layout(scenario, ROOT)
    if tuple(map(digest, source)) != tuple(map(digest, fixed)):
        raise ValueError(f"{scenario}: A-only does not reuse original fixed V2 layout")
    physical = {item["physical_cluster_sha256"] for item in layouts.values()}
    if len(physical) != 1:
        raise ValueError(f"{scenario}: physical topology mismatch")
    return layouts


def render() -> None:
    summary = {
        "protocol": "70B, single/multi original 24-GPU topologies, offered 700/320 token/s, "
                    "1800 s, zero warmup, no tail drain, seeds 0/1/2",
        "stage_order": [{"label": label, "method": method} for label, method in STAGES],
        "method_code_sha256": {
            **{str(HERE / name): digest(HERE / name) for name in
               ("capacity_only.py", "adapters.py", "run_incremental.py",
                "incremental_report.py")},
            **{str(ROOT / name): digest(ROOT / name) for name in
               ("benchmarks/registry.py", "rcaps/placement/adaptive.py",
                "rcaps/scheduling/routing_dag.py", "rcaps/scheduling/scheduler_final.py")},
        },
        "scenarios": {},
    }
    lines = [
        "# RCAPS V2 递进式方法消融", "",
        "顺序为基础方案 → A（资源感知放置）→ A+B（自适应共享复制）→ A+B+C（动态调度）。"
        "基础方案和 A 使用相同的一张共享 A100、12 层前缀、双后缀约束与固定合法路径轮转；"
        "A+B 和完整 V2 使用字节相同的自适应布局。前三阶段共用 KV 容量安全准入，"
        "以仿真轨迹给定的目标输出长度作为预留上界，不以实时 GPU/链路负担改变轮转路径。"
        "真实服务需要请求声明的最大长度或其他预留上界。", "",
        "70B、两种原始 24-GPU 拓扑，single/multi 负载分别为 700/320 offered token/s；"
        "正式种子 0/1/2，1800 秒零预热且不排空尾部。", "",
        "绝对值为三个正式窗口指标的均值 ± 样本标准差；P95 是三个种子各自 P95 的均值，"
        "并非合并请求重算。增益先在每个种子内配对计算，再取均值 ± 样本标准差。"
        "吞吐、完成率越高越好；TTFT、TPOT、积压越低越好；负增益如实表示退化。", "",
    ]
    for scenario in SCENARIOS:
        layouts = verify_stage_layouts(scenario)
        placements = {
            method: load(METHODS[method].layout(scenario, ROOT)[0].parent / "placement.json")
            for _, method in STAGES
        }
        records = {}
        hashes = {}
        for label, method in STAGES:
            records[method] = []
            hashes[method] = {}
            for seed in SEEDS:
                path = output_file(RUNS, scenario, seed, method)
                record = load(path)
                if record.get("system") != method or record.get("scenario") != scenario or record.get("seed") != seed:
                    raise ValueError(f"Result identity mismatch: {path}")
                if record.get("solution_sha256") != layouts[method]["solution_sha256"] or \
                        record.get("sim_cluster_sha256") != layouts[method]["sim_cluster_sha256"]:
                    raise ValueError(f"Result layout hash mismatch: {path}")
                if record.get("duration_s") != 1800 or record.get("warmup_s") != 0 or \
                        record.get("evaluation_protocol") != "fixed_window_no_tail_drain" or \
                        record.get("offered_tokens_per_s") != (700.0 if scenario == "single" else 320.0):
                    raise ValueError(f"Formal protocol mismatch: {path}")
                if record.get("query_samples_schema") != 1:
                    raise ValueError(f"Request identity schema missing: {path}")
                records[method].append(record)
                hashes[method][seed] = digest(path)
        for seed_index, seed in enumerate(SEEDS):
            reference = records[STAGES[0][1]][seed_index]
            for _, method in STAGES[1:]:
                validate_pair(records[method][seed_index], reference,
                              f"{scenario}/seed{seed}/{method}")
        identical_old_static = {}
        ab_method = STAGES[2][1]
        for seed, ab_record in zip(SEEDS, records[ab_method]):
            old_static = load(output_file(RUNS, scenario, seed, "rcaps_v2_static_routes"))
            validate_pair(ab_record, old_static, f"{scenario}/seed{seed}/safe-old-static")
            checked = ("query_samples", "route_counts", "gpu_queue_request_s",
                       "outbound_wait_request_s", *FIELDS)
            identical_old_static[seed] = (ab_record["capacity_guard_block_events"] == 0 and
                                          all(ab_record[field] == old_static[field]
                                              for field in checked))
        if not all(identical_old_static.values()):
            raise ValueError(f"{scenario}: A+B safety guard changed a formal run")
        absolute = {method: {field: stats([record[field] for record in records[method]])
                             for field in FIELDS} for _, method in STAGES}
        guard = {method: stats([record["capacity_guard_block_events"]
                                for record in records[method]])
                 for _, method in STAGES[:-1]}
        steps = []
        for (from_label, old), (to_label, new) in zip(STAGES[:-1], STAGES[1:]):
            cohorts = [validate_pair(n, o, f"{scenario}/seed{seed}/{new}/{old}")
                       for seed, n, o in zip(SEEDS, records[new], records[old])]
            changes = {field: stats([
                signed_improvement(n[field], o[field], higher)
                for n, o in zip(records[new], records[old])])
                for field, _, higher in METRICS}
            step = {"from": old, "to": new, "label": f"{from_label} → {to_label}",
                    "paired_improvement_percent": changes,
                    "common_cohort_by_seed": cohorts}
            steps.append(step)
        summary["scenarios"][scenario] = {
            "layouts": layouts,
            "placement_search": {
                method: {field: placements[method].get(field) for field in
                         ("algorithm", "stem", "prefix_layers", "branches",
                          "candidate_evaluations", "planning_s")}
                for _, method in STAGES},
            "result_sha256_by_method": hashes,
            "run_log_sha256_by_new_method": {
                method: {seed: digest(output_file(RUNS, scenario, seed, method).with_suffix(".log"))
                         for seed in SEEDS}
                for _, method in STAGES[:-1]},
            "absolute": absolute,
            "capacity_guard_block_events": guard,
            "adaptive_static_identical_to_old_static_by_seed": identical_old_static,
            "adjacent_steps": steps,
            "measurement_population_by_method": {
                method: [{"seed": seed, "arrivals": record["arrivals"],
                          "first_tokens_in_window": record["first_tokens_in_window"],
                          "queries_with_tpot_samples": record["queries_with_tpot_samples"],
                          "completion_fraction": record["completion_fraction"],
                          "backlog_at_window_end": record["backlog_at_window_end"],
                          "capacity_guard_block_events": record.get("capacity_guard_block_events")}
                         for seed, record in zip(SEEDS, records[method])]
                for _, method in STAGES},
        }
        lines += [f"## {scenario}", "", "### 放置结构与选型开销", "",
                  "| 阶段 | 共享 GPU | 前缀层数 | 后缀数 | 候选评价数 | 规划 s |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        for label, method in STAGES:
            item = placements[method]
            lines.append(f"| {label} | {','.join(map(str, item['stem']))} | "
                         f"{item['prefix_layers']} | {len(item['branches'])} | "
                         f"{item.get('candidate_evaluations', '—')} | "
                         f"{item.get('planning_s', float('nan')):.3f} |")
        lines += ["", "A+B 和 A+B+C 复用同一布局；规划时间为布局生成记录值，"
                  "不计入在线 1800 秒窗口。", "",
                  "前三阶段 KV 安全准入阻塞事件数（均值 ± 样本标准差）：" +
                  "；".join(f"{label} {guard[method]['mean']:.1f} ± {guard[method]['sample_sd']:.1f}"
                          for label, method in STAGES[:-1]) + "。", "",
                  "A+B 的三个种子保护均未触发，请求样本、执行路径、资源等待和五项核心指标"
                  "与原无保护静态对照逐项相同。", "", "### 绝对指标", "",
                  "| 阶段 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 % | 末端积压 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for label, method in STAGES:
            lines.append("| " + label + " | " + " | ".join(
                format_stat(absolute[method][field], field) for field in FIELDS) + " |")
        lines += ["", "### 每加入一项方法的配对改善", "",
                  "| 递进步骤 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 末端积压 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for step in steps:
            lines.append("| " + step["label"] + " | " + " | ".join(
                format_gain(step["paired_improvement_percent"][field])
                for field in FIELDS) + " |")
        lines += ["", "### 相邻阶段共同可观测请求", "",
                  "| 步骤 | TTFT 共同数 | 新/旧 TTFT P95 s | TPOT 共同数 | 新/旧 TPOT P95 s |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for step in steps:
            cohorts = step["common_cohort_by_seed"]
            for field, title in (("ttft_s", "TTFT"), ("tpot_s", "TPOT")):
                if any(cohort[field]["both_observed"] == 0 for cohort in cohorts):
                    raise ValueError(f"No common {title} observations: {scenario}/{step['label']}")
            ttft = [cohort["ttft_s"] for cohort in cohorts]
            tpot = [cohort["tpot_s"] for cohort in cohorts]
            count = lambda items: (f"{mean(item['both_observed'] for item in items):.1f} ± "
                                   f"{stdev(item['both_observed'] for item in items):.1f}")
            paired = lambda items: (
                f"{mean(item['main_p95_s'] for item in items):.3f} ± "
                f"{stdev(item['main_p95_s'] for item in items):.3f} / "
                f"{mean(item['baseline_p95_s'] for item in items):.3f} ± "
                f"{stdev(item['baseline_p95_s'] for item in items):.3f}")
            lines.append(f"| {step['label']} | {count(ttft)} | {paired(ttft)} | "
                         f"{count(tpot)} | {paired(tpot)} |")
        lines += ["", "共同请求表按每种子共同可观测请求重算 P95，再对三个 P95 取均值 ± 样本标准差。"
                  "共同请求数同样按种子汇总；原始请求身份和逐种子值见 JSON。", ""]
    lines += [
        "## 归因边界", "",
        "A 检验同一固定结构与静态调度下，容量规则和完整 V2 资源感知放置流程的差别；"
        "它包含候选构造、设备排序、层分配与事件图评分，不单独归因于某个分数项。",
        "B 检验同一 V2 放置评价与静态调度下，自适应共享范围、设备分组、层边界与复制结构的联合作用。",
        "C 检验同一最终布局下，V2 在线 DAG 选路与传输合并的整体作用。"
        "A+B 的保守 KV 准入规则在六个正式窗口均未触发，实际执行记录与原静态对照一致；"
        "仍不能将差额单独归因于选路或传输合并。",
        "未加 KV 容量保护的固定结构静态对照在正式种子 1 触发模拟器容量断言；"
        "失败日志保留在 attempts_pre_kv_guard/，未计算完整窗口指标。",
        "各步差额是不同条件下的增量，不能直接相加。种子 1 曾参与早期开发；"
        "三个种子只描述配对波动，不作显著性或真实集群性能声明。", "",
    ]
    (HERE / "incremental_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "INCREMENTAL_REPORT_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'INCREMENTAL_REPORT_CN.md'}")


if __name__ == "__main__":
    render()

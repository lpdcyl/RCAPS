"""Audit paired formal evidence for the static M1 candidate."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from .evidence import (HERE, LOADS, ROOT, SEEDS, SYSTEMS, choose, digest,
                       layout, paired)


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
NAMES = {"m1_static_candidate": "简化 M1", "v2_reference": "冻结 V2"}


def p95(values: list[float]) -> float | None:
    return float(np.percentile(values, 95)) if values else None


def describe(values: list[float]) -> dict:
    return {"count": len(values), "mean": mean(values) if values else None,
            "sample_sd": stdev(values) if len(values) > 1 else None,
            "by_seed": values}


def common_completed(candidate: dict, reference: dict) -> dict:
    left, right = candidate["query_samples"], reference["query_samples"]
    uids = [uid for uid in left if left[uid]["completed"] and right[uid]["completed"]]
    result = {"count": len(uids)}
    for field in ("ttft_s", "tpot_s"):
        matched = [uid for uid in uids if left[uid][field] is not None and
                   right[uid][field] is not None]
        result[field] = {"count": len(matched),
                         "candidate_p95_s": p95([left[uid][field] for uid in matched]),
                         "v2_p95_s": p95([right[uid][field] for uid in matched])}
    return result


def pending(record: dict) -> dict:
    ages = [max(0.0, record["duration_s"] - sample["arrival_s"])
            for sample in record["query_samples"].values()
            if not sample["completed"]]
    if len(ages) != record["backlog_at_window_end"]:
        raise ValueError("Pending samples do not match backlog")
    return {"count": len(ages), "residence_p50_s":
            float(np.percentile(ages, 50)) if ages else None,
            "residence_p95_s": p95(ages),
            "residence_max_s": max(ages) if ages else None}


def structure(path: Path) -> dict:
    row = json.loads(path.read_text(encoding="utf-8"))
    return {"shared_gpus": len(row["stem"]), "shared_layers": row["prefix_layers"],
            "suffixes": len(row["branches"]),
            "model_layer_copies": sum(end - start for start, end in
                                      row["intervals"].values()),
            "candidate_evaluations": row["candidate_evaluations"],
            "planning_s_saved": row["planning_s"]}


def collect() -> dict:
    layout_audit = json.loads((HERE / "layout_audit.json").read_text(encoding="utf-8"))
    rows = []
    for scenario in LOADS:
        for seed in SEEDS:
            chosen = {system: choose(scenario, seed, system) for system in SYSTEMS}
            row = {"scenario": scenario, "seed": seed,
                   "sources": {system: chosen[system][1] for system in SYSTEMS},
                   "metrics": {}, "pending": {}}
            for system, (record, source) in chosen.items():
                if record is None:
                    row["metrics"][system] = None
                    row["pending"][system] = None
                    continue
                row["metrics"][system] = {field: record[field] for field in METRICS}
                row["pending"][system] = pending(record)
            left, right = chosen["m1_static_candidate"][0], chosen["v2_reference"][0]
            if left is not None and right is not None:
                row["paired_trace"] = paired(left, right)
                row["common_completed"] = common_completed(left, right)
                row["candidate_minus_v2"] = {
                    field: left[field] - right[field] for field in METRICS}
            else:
                row["paired_trace"] = None
                row["common_completed"] = None
                row["candidate_minus_v2"] = None
            rows.append(row)
    aggregate = {}
    for scenario in LOADS:
        selected = [row for row in rows if row["scenario"] == scenario]
        aggregate[scenario] = {
            system: {field: describe([row["metrics"][system][field]
                                      for row in selected if row["metrics"][system]
                                      is not None]) for field in METRICS}
            for system in SYSTEMS}
        aggregate[scenario]["candidate_minus_v2"] = {
            field: describe([row["candidate_minus_v2"][field] for row in selected
                             if row["candidate_minus_v2"] is not None])
            for field in METRICS}
    layouts = {}
    for scenario in LOADS:
        layouts[scenario] = {
            system: structure(layout(scenario, system)[0].parent / "placement.json")
            for system in SYSTEMS}
        layouts[scenario]["new_search_timing"] = {
            "static_planning_s": layout_audit[scenario]["search"]["planning_s"],
            "v2_planning_s": layout_audit[scenario]["frozen_v2_search"]["planning_s"]}
        layouts[scenario]["audit"] = layout_audit[scenario]
    return {"protocol": {"model": "LLaMA-70B", "loads": LOADS,
                         "seeds": SEEDS, "duration_s": 1800, "warmup_s": 0,
                         "tail_drain": False, "scheduler": "QueueAwareDagScheduler"},
            "rows": rows, "aggregate": aggregate, "layouts": layouts,
            "source_code_sha256": {
                "static_resource": digest(ROOT / "rcaps/placement/static_resource.py"),
                "adaptive_search": digest(ROOT / "rcaps/placement/adaptive.py"),
                "online_scheduler": digest(ROOT / "rcaps/scheduling/scheduler_final.py")}}


def fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def markdown(result: dict) -> str:
    lines = ["# M1 简化：静态异构资源代价的第一阶段验证", "",
             "新候选仅将放置评价替换为确定性的画像与资源代价；不模拟请求到达、"
             "不构建多请求事件 DAG，也不预测真实 P95 TTFT／TPOT。"
             "M2 搜索空间、初始化、邻域与轮数，以及 M3 在线调度保持原语义。"
             "冻结 V2 与旧实验文件未被覆盖。", "",
             "## 证据来源", "",
             "LLaMA-70B、原 24 GPU；单集群 700、三集群 320 offered token/s；"
             "种子 0/1/2、1800 秒、零预热、窗口末不排空。"
             "新布局与此前强静态模型对照的 `solution.ini`、`simulator_cluster.ini` "
             "在两个拓扑均逐字节一致；新旧布局均由同一个在线调度器执行。"
             "六个静态模型正式窗口及六个冻结 V2 窗口通过文件哈希、协议、"
             "轨迹和请求身份审计后复用，没有重复仿真。"
             "逐种子原始路径与 SHA256 见 [summary.json](summary.json)。", "",
             "## 布局与离线搜索", "",
             "| 拓扑 | 方法 | 共享 GPU | 共享层 | 后缀 | 模型层副本 | 候选评价数 | 本次规划秒数 | 合法在线路径数 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for scenario, title in (("single", "单集群"), ("multi", "三集群")):
        for system in SYSTEMS:
            placement = result["layouts"][scenario][system]
            timing = result["layouts"][scenario]["new_search_timing"]
            duration = (timing["static_planning_s"] if system == "m1_static_candidate"
                        else timing["v2_planning_s"])
            paths = (result["layouts"][scenario]["audit"]["structure"]
                     ["online_compatible_path_count"] if system == "m1_static_candidate"
                     else None)
            lines.append("| " + " | ".join((title, NAMES[system],
                str(placement["shared_gpus"]), str(placement["shared_layers"]),
                str(placement["suffixes"]), str(placement["model_layer_copies"]),
                str(placement["candidate_evaluations"]), fmt(duration, 2),
                str(paths) if paths is not None else "—")) + " |")
    lines.extend(["", "合法在线路径数是层连续且沿导出链路可达的路径计数，"
                  "不代表调度器实际使用数量。规划耗时为本次同一进程的搜索墙钟时间，"
                  "包括候选生成和评价；不将其称为单候选评分耗时。", "",
                  "## 在线性能", "",
                  "逐种子窗口 P95 再跨种子求均值。所有指标均为仿真测量值，"
                  "不是静态评价器的预测。", "",
                  "| 拓扑 | 方法 | 完整种子 | 吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s/token ↓ | 完成率 ↑ | 末端积压 ↓ |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for scenario, title in (("single", "单集群"), ("multi", "三集群")):
        for system in SYSTEMS:
            group = result["aggregate"][scenario][system]
            lines.append("| " + " | ".join((title, NAMES[system],
                str(group["output_throughput_tokens_per_s"]["count"]),
                *(fmt(group[field]["mean"], 1 if field == "backlog_at_window_end"
                       else 3) for field in METRICS))) + " |")
    lines.extend(["", "同种子配对的简化 M1 − 冻结 V2；正吞吐差值为提升，"
                  "正延迟差值为退化。", "",
                  "| 拓扑 | 吞吐差 token/s | P95 TTFT 差 s | P95 TPOT 差 s/token | 完成率差 | 积压差 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for scenario, title in (("single", "单集群"), ("multi", "三集群")):
        group = result["aggregate"][scenario]["candidate_minus_v2"]
        lines.append("| " + " | ".join((title, *(fmt(group[field]["mean"],
            1 if field == "backlog_at_window_end" else 3) for field in METRICS))) + " |")
    lines.extend(["", "逐种子原始配对值如下，每格均按“简化 M1 / 冻结 V2”排列。", "",
                  "| 拓扑 | 种子 | 吞吐 token/s | P95 TTFT s | P95 TPOT s/token | 完成率 | 末端积压 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in result["rows"]:
        label = "单集群" if row["scenario"] == "single" else "三集群"
        cells = []
        for field in METRICS:
            left = row["metrics"]["m1_static_candidate"]
            right = row["metrics"]["v2_reference"]
            cells.append(" / ".join(fmt(value[field], 1 if field ==
                                        "backlog_at_window_end" else 3)
                                    if value is not None else "—"
                                    for value in (left, right)))
        lines.append("| " + " | ".join((label, str(row["seed"]), *cells)) + " |")
    lines.extend(["", "## 共同完成请求与截尾", "",
                  "下表的 P95 只在两方法同一种子内都完成的请求上计算，再跨种子平均。"
                  "未完成请求驻留时长是窗口末减到达时间，包含可能已接受服务的时间。", "",
                  "| 拓扑 | 共同完成数／种子 | 共同 P95 TTFT：简化／V2 s | 共同 P95 TPOT：简化／V2 s/token | 未完成驻留 P95：简化／V2 s |",
                  "| --- | --- | ---: | ---: | ---: |"])
    for scenario, title in (("single", "单集群"), ("multi", "三集群")):
        rows = [row for row in result["rows"] if row["scenario"] == scenario and
                row["common_completed"] is not None]
        counts = "/".join(str(row["common_completed"]["count"]) for row in rows)
        values = []
        for field in ("ttft_s", "tpot_s"):
            values.append(" / ".join(fmt(mean(row["common_completed"][field][key]
                                               for row in rows)) if rows else "—"
                                     for key in ("candidate_p95_s", "v2_p95_s")))
        ages = " / ".join(fmt(mean(row["pending"][system]["residence_p95_s"]
                                    for row in rows)) if rows else "—"
                          for system in SYSTEMS)
        lines.append("| " + " | ".join((title, counts or "—", *values, ages)) + " |")
    lines.extend(["", "## 判定边界", "",
                  "这项受控对照说明静态代价评价如何改变布局与在线指标，"
                  "不能证明两种评价器在统计意义上等效。三个种子只描述波动。"
                  "本阶段没有预设数值通过门槛，也不自动将该候选替换为论文主版本。"
                  "现有物理资源模型与导出的层兼容图仍是两种表示；"
                  "统一图接口及论文主表重写留待下一阶段。", "",
                  "复现步骤见 [README_CN.md](README_CN.md)。", ""])
    return "\n".join(lines)


def main() -> None:
    result = collect()
    (HERE / "summary.json").write_text(json.dumps(result, indent=2) + "\n",
                                       encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text(markdown(result), encoding="utf-8")
    print(HERE / "RESULTS_CN.md")


if __name__ == "__main__":
    main()

"""Summarize only completed, legal planning trials; retain failures separately."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from .worker import audit_export, write_json


HERE = Path(__file__).resolve().parent


def metric(values: list[float]) -> str:
    if not values:
        return "—"
    return f"{statistics.median(values):.3f} [{min(values):.3f}, {max(values):.3f}]"


def main() -> None:
    index = json.loads((HERE / "index.json").read_text(encoding="utf-8"))
    env = index["environment"]
    grouped = defaultdict(list)
    for item in index["trials"]:
        grouped[(item["case"], item["method"])].append(item)
    methods = ["v3", "helix_ilp", *sorted({row["method"] for row in
               index["trials"] if row["method"].startswith("helix_ilp_budget")})]
    lines = ["# V3 与 Helix ILP：离线规划效率", "",
             "两者使用相同的 C1 物理 GPU 配置；每次在新的 Python 进程中串行运行。",
             "总时间从规划器准备输入和建立模型开始，到导出部署文件结束；不含 Python 启动、",
             "预先生成的启发式初始布局，也不含在线仿真。V3 使用冻结 `multi_any` 规则；",
             "Helix 调用原 artifact 的 70B ILP 入口；`helix_ilp` 保持原停机策略，",
             "`helix_ilp_budget*` 额外设置明示的 Gurobi 求解时间上限。", "",
             f"运行主机：{env['processor']}；物理/逻辑 CPU "
             f"{env['physical_cpus']}/{env['logical_cpus']}；内存 "
             f"{env['ram_gib']:.1f} GiB；Gurobi {'.'.join(map(str, env['gurobi_version']))}。",
             "Helix 使用 Gurobi 原生线程设置（日志显示最多 32 线程）；V3 使用单进程确定性搜索。", "",
             "| 拓扑 | 方法 | 有效部署/运行数 | 总规划时间中位数 [范围] s | 核心搜索/求解中位数 [范围] s | 布局检查 |",
             "| --- | --- | ---: | ---: | ---: | --- |"]
    structured = {}
    for case in ("C1_single", "C1_multi"):
        structured[case] = {}
        for method in methods:
            items = grouped[(case, method)]
            if not items:
                continue
            passed = [row for row in items if row["status"] == "passed" and
                      row.get("deployment", {}).get("valid")]
            total = [row["total_wall_s"] for row in passed]
            core = [(row["search_wall_s"] if method == "v3" else
                     row["stage_wall_s"]["search_layout"]) for row in passed]
            lines.append(f"| {case} | {method} | {len(passed)}/{len(items)} | "
                         f"{metric(total)} | {metric(core)} | "
                         f"{'全部通过' if len(passed) == len(items) and items else '有失败或未测'} |")
            structured[case][method] = {
                "completed": len(passed), "attempted": len(items),
                "total_wall_s": total, "core_wall_s": core}
        for method in methods:
            if method == "v3":
                continue
            left = structured[case]["v3"]
            right = structured[case].get(method)
            if not right:
                continue
            if left["completed"] and right["completed"] and \
                    left["completed"] == left["attempted"] and \
                    right["completed"] == right["attempted"]:
                ratio = statistics.median(right["total_wall_s"]) / statistics.median(
                    left["total_wall_s"])
                structured[case][f"{method}_over_v3_median_total_ratio"] = ratio
    lines.extend(["", "## 逐次记录", "",
                  "| 拓扑 | 方法 | 重复 | 状态 | 总时间 s | 搜索/求解 s | 内部诊断 |",
                  "| --- | --- | ---: | --- | ---: | ---: | --- |"])
    for item in sorted(index["trials"], key=lambda row: (
            row["case"], row["method"], row["repetition"])):
        case, method = item["case"], item["method"]
        if item["status"] == "passed":
            core = (item["search_wall_s"] if method == "v3" else
                    item["stage_wall_s"]["search_layout"])
            diag = (f"{item['candidate_evaluations']} 次静态评分" if method == "v3"
                    else f"Gurobi status={item['model']['solver_status']}, "
                         f"gap={100 * item['model'].get('mip_gap', float('nan')):.1f}%")
            lines.append(f"| {case} | {method} | {item['repetition']} | 成功 | "
                         f"{item['total_wall_s']:.3f} | {core:.3f} | {diag} |")
        else:
            output = HERE / "runs" / case / method / f"rep{item['repetition']}"
            solution = output / "ilp_sol.ini"
            simulator = output / "simulator_cluster.ini"
            diagnosis = "原始日志保留"
            if solution.exists() and simulator.exists():
                try:
                    checked = audit_export(case, solution, simulator)
                    diagnosis = (f"{checked['complete_paths']} 条完整路径；"
                                 f"有效={checked['valid']}")
                except Exception as error:
                    diagnosis = f"部署检查异常：{type(error).__name__}"
            lines.append(f"| {case} | {method} | {item['repetition']} | "
                         f"{item['status']} | — | — | {diagnosis} |")
    lines.extend(["", "## 解释边界", "",
                  "- 这项实验衡量的是本仓库中两种规划实现的实际耗时，不是相同数学目标下的算法复杂度竞赛。",
                  "- Helix ILP 的变量/约束数、Gurobi 求解状态和 gap，与 V3 的实际候选评分数不是同一量纲；分别列出供复现与诊断。",
                  "- 原始 Helix 使用 Petals（单集群）或 Swarm（三集群）的既有初始布局。初始布局的生成成本不计入这两种方法的总时间。",
                  "- `helix_ilp_budget*` 仅为 Gurobi 设置明确的求解时间上限，导出该时刻的 incumbent；它不是原 36000 秒停机策略的完整结果，也不能据此说 Helix 在该时刻没有可部署解。",
                  "- 单集群原策略的超时记录显示 Gurobi 已加载非零启发式 MIP 初始解；超时只表示完整求解过程仍在运行。",
                  "- V3 使用已冻结的初始状态与评分参考；两种部署均逐次检查层段、显存层容量、物理连通和完整执行路径。",
                  "- 如有超时或失败，不对不完整运行填入规划时间，也不以超时下界计算加速比。", ""])
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(HERE / "analysis.json", structured)


if __name__ == "__main__":
    main()

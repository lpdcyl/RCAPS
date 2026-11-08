"""Write a concise, source-linked results table after the five-seed audit."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def main() -> None:
    audit = json.loads((HERE / "FINAL_AUDIT.json").read_text(encoding="utf-8"))
    if audit["complete_five_seed_groups"] != 4 or audit["failure_count"] or audit["pending_count"]:
        raise RuntimeError("Formal result matrix is not complete")
    lines = [
        "# HexGen 外部基线：24 节点五种子端到端模拟结果",
        "",
        "方法来自 HexGen（ICML 2024）论文的多流水线分组、流水线内层划分与服务质量搜索框架。",
        "当前 70B/24 节点只有 152 层可放置容量，故完整模型的副本数上限为 1；",
        "该拓扑上的 GA 分组退化为单条流水线，不能据此检验 HexGen 的多副本收益。",
        "层划分由 DP 搜索，在线请求沿该流水线执行；所有结果来自原模拟器的 CPU 离散事件执行，非真实 GPU 测量。",
        "",
        "正式协议：单集群 350/700、三集群 160/320 offered token/s；每条件 seed0–4，",
        "1800 s、零预热、窗口末不排空。同键请求轨迹 SHA 与既有 V4/Helix 证据逐一一致。",
        "布局由开发种子 100/101 的 180 s 窗口选择，正式种子未参与选型。",
        "",
        "| 拓扑/负载 | 完成种子 | 输出吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 末端积压 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    metric_names = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                    "completion_fraction", "backlog_at_window_end")
    for key in ("single_load350", "single_load700", "multi_load160", "multi_load320"):
        group = audit["groups"][key]
        values = [group["hexgen"][metric]["mean"] for metric in metric_names]
        lines.append(f"| {key} | 5/5 | {fmt(values[0])} | {fmt(values[1])} | "
                     f"{fmt(values[2])} | {fmt(values[3] * 100, 2)}% | {fmt(values[4], 1)} |")
    lines += ["", "## 与现有正式结果的同种子配对差（HexGen − 对照）", "",
              "正值表示 HexGen 数值更大；吞吐/完成率希望为正，TTFT/TPOT/积压希望为负。",
              "括号为 df=4 的双侧 95% 配对 t 区间；仅在五种子和原证据 SHA 均通过时列出。",
              "", "| 拓扑/负载 | 对照 | 吞吐差 token/s | TTFT 差 s | TPOT 差 s |",
              "|---|---|---:|---:|---:|"]
    for key in ("single_load350", "single_load700", "multi_load160", "multi_load320"):
        group = audit["groups"][key]
        for cell in ("V4", "HH", "HHplus"):
            paired = group["paired"].get(cell)
            if not paired:
                continue
            cells = []
            for metric in metric_names[:3]:
                stats = paired.get(metric)
                cells.append((f"{fmt(stats['mean'])} [{fmt(stats['ci95_lower'])}, "
                              f"{fmt(stats['ci95_upper'])}]" if stats else "—"))
            lines.append(f"| {key} | {cell} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines += ["", "## 可追溯性与解释边界", "",
              f"- 正式协议：[manifest.json]({(HERE / 'manifest.json').as_posix()})；逐键结果与日志在 `runs/`；审计：[FINAL_AUDIT.json]({(HERE / 'FINAL_AUDIT.json').as_posix()})。",
              "- 正式五种子结果与原失败、独立重放分别记账；本次没有把开发窗口或重放写入正式表。",
              "- 本实现用当前离散事件模拟器评价候选 SLO，代替论文使用的 AlpaServe 估计器；",
              "  节点排序采用链路感知贪心，层数分配采用 DP。该结果应称为 HexGen 论文方法的模拟器适配，",
              "  不应称为原作者 artifact 的逐位复现。",
              ""]
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

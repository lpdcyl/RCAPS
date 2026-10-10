"""Audit the official-load three-way placement/scheduler comparison."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from statistics import mean, stdev

from experiments.multiseed.run import GUROBI_VERSION, HERE, LAYOUTS, PAPER_LOAD, ROOT
from simulator.event_simulator.utils import AVG_OUTPUT_LEN


SEEDS = (0, 1, 2)
SCENARIOS = ("single", "multi")
NAMES = ("paper_helix", "paper_scheduler_helix", "paper_integrated")
LABELS = {
    "paper_helix": "Helix 放置＋Helix 调度",
    "paper_scheduler_helix": "新放置＋Helix 调度",
    "paper_integrated": "新放置＋新调度",
}
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end")


def load(scenario: str, seed: int, name: str) -> dict | None:
    path = HERE / "runs" / f"seed{seed}" / scenario / f"{name}.json"
    if not path.is_file():
        if name != "paper_scheduler_helix":
            raise FileNotFoundError(path)
        log = path.with_suffix(".log")
        if not log.is_file():
            raise FileNotFoundError(f"Missing both result and failure log: {path}")
        content = log.read_text(encoding="utf-8", errors="replace")
        if "Traceback" not in content or "AssertionError:" not in content:
            raise ValueError(f"Incomplete run without recorded exception: {log}")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["scenario"] == scenario and data["seed"] == seed, path
    assert data["offered_tokens_per_s"] == PAPER_LOAD[scenario], path
    assert data["duration_s"] == 1800 and data["warmup_s"] == 0, path
    assert data["evaluation_protocol"] == "fixed_window_no_tail_drain", path
    assert data["gurobi_version"] == GUROBI_VERSION, path
    expected_method = "queue_dag" if name == "paper_integrated" else "helix"
    assert data["method"] == expected_method, path
    if name == "paper_integrated":
        assert data["routing_policy"] == "final", path
    layout_key = "paper_helix" if name == "paper_helix" else "final"
    layout_dir = ROOT / LAYOUTS[scenario][layout_key]
    expected_solution = layout_dir / ("ilp_sol.ini" if layout_key == "paper_helix"
                                      else "solution.ini")
    assert Path(data["solution"]).resolve() == expected_solution.resolve(), path
    assert Path(data["sim_cluster"]).resolve() == (
        layout_dir / "simulator_cluster.ini").resolve(), path
    assert all(data[field] is not None for field in FIELDS), path
    return data


def gain(before: float, after: float, higher_is_better: bool) -> float:
    assert before > 0
    return 100 * (after / before - 1 if higher_is_better
                  else 1 - after / before)


def main() -> None:
    records = {}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            three = {name: load(scenario, seed, name) for name in NAMES}
            for field in ("scenario", "seed", "offered_tokens_per_s", "duration_s",
                          "warmup_s", "evaluation_protocol", "trace_sha256",
                          "arrivals", "python_version", "numpy_version",
                          "gurobi_version"):
                assert len({three[name][field] for name in NAMES
                            if three[name] is not None}) == 1, (
                    scenario, seed, field)
            records[scenario, seed] = three

    lines = [
        "# 官方高负载三方案成对实验",
        "",
        "LLaMA-70B、24 GPU，种子 0/1/2，单集群 700 token/s、三集群 320 token/s，",
        "每次测量 1800 s，无预热，Gurobi 13。有完整结果的三方案在同场景同种子下，",
        "`trace_sha256` 与到达请求数严格相同。",
        "",
        "三方案依次为：Helix 放置＋Helix 调度；新放置＋Helix 调度；新放置＋新调度。",
        "中间方案只更换放置，用于直接归因官方高负载下的放置效果。",
        "如果原 Helix 在线调度在新放置下触发不可路由断言，该运行标为失败，",
        "不使用截断窗口指标，也不把失败种子算作改善。",
        "",
        "## 逐种子结果",
        "",
        "| 场景 | 种子 | 方案 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 窗口末积压 |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scenario in SCENARIOS:
        for seed in SEEDS:
            for name in NAMES:
                r = records[scenario, seed][name]
                if r is None:
                    lines.append(f"| {scenario} | {seed} | {LABELS[name]} | 运行失败 | — | — | — | — |")
                    continue
                lines.append(
                    f"| {scenario} | {seed} | {LABELS[name]} | "
                    f"{r['output_throughput_tokens_per_s']:.3f} | "
                    f"{r['ttft_p95_s']:.3f} | {r['tpot_p95_s']:.3f} | "
                    f"{r['completion_fraction']:.3f} | {r['backlog_at_window_end']} |")

    failures = [(scenario, seed) for scenario in SCENARIOS for seed in SEEDS
                if records[scenario, seed]["paper_scheduler_helix"] is None]
    if failures:
        lines += ["", "## 未完成运行", "",
                  "| 场景 | 种子 | 最后进度 | 原始异常 |",
                  "| --- | ---: | --- | --- |"]
        for scenario, seed in failures:
            log = (HERE / "runs" / f"seed{seed}" / scenario /
                   "paper_scheduler_helix.log")
            entries = log.read_text(encoding="utf-8", errors="replace").splitlines()
            progress = next((entry for entry in reversed(entries)
                             if entry.startswith("progress:")), "无进度记录")
            error = next((entry for entry in reversed(entries)
                          if entry.startswith("AssertionError:")), "未知异常")
            lines.append(f"| {scenario} | {seed} | {progress} | {error} |")
        diagnostic = (HERE / "runs/seed1/single/"
                      "paper_scheduler_helix_diagnostic.json")
        if diagnostic.is_file():
            detail = json.loads(diagnostic.read_text(encoding="utf-8"))
            if detail["scenario"] == "single" and detail["seed"] == 1:
                candidate = detail["candidates"][0]
                uid = candidate["node_uid"]
                solution = (ROOT / LAYOUTS["single"]["final"] / "solution.ini")
                match = re.search(rf"^compute_node_{uid}\s*=\s*(\[.*\])$",
                                  solution.read_text(encoding="utf-8"), re.MULTILINE)
                if match is None:
                    raise ValueError(f"Cannot find compute_node_{uid} in {solution}")
                layer_count = len(ast.literal_eval(match.group(1)))
                expected_tokens = int(detail["prompt_tokens"] + AVG_OUTPUT_LEN * 0.6)
                kv_cost = expected_tokens * layer_count
                remaining = candidate["kv_expected_available"] - kv_cost
                reserve = 0.1 * candidate["kv_total_capacity"]
                assert detail["reason"] == ["Fail-KV"] and remaining < reserve
                lines += [
                    "", "### 同参数重跑诊断", "",
                    f"重跑在仿真时间 {detail['sim_time_s']:.3f} s 再次触发同一断言。"
                    f"节点 {detail['current_node_uid']} 的唯一下一跳是节点 {uid}，"
                    f"流量份额 {candidate['flow_share']:.0%}、prompt 上限 "
                    f"{candidate['prompt_max_tokens']} token；本次 prompt 仅 "
                    f"{detail['prompt_tokens']} token，所以流量与长度过滤均通过。",
                    f"唯一失败项为 `Fail-KV`。Helix 预计本次请求需 "
                    f"({detail['prompt_tokens']} + {AVG_OUTPUT_LEN}×0.6)×{layer_count} "
                    f"= {kv_cost} 个 KV 单位；节点 {uid} 当前预计空余 "
                    f"{candidate['kv_expected_available']}，加入后为 {remaining}，"
                    f"低于其总容量 {candidate['kv_total_capacity']} 的 10% "
                    f"保留量（{reserve:.1f}）。在线模式遇到无可行下一跳便断言终止。",
                ]

    comparisons = {
        "placement_only": ("paper_helix", "paper_scheduler_helix",
                           "仅更换放置（Helix 调度固定）"),
        "scheduler_only": ("paper_scheduler_helix", "paper_integrated",
                           "仅更换调度（新放置固定）"),
        "end_to_end": ("paper_helix", "paper_integrated", "完整系统"),
    }
    summary = {}
    lines += [
        "", "## 成对变化", "",
        "正数表示改善。均值±样本标准差基于已完成的逐种子百分比，不是置信区间。",
        "单集群中间方案仅完成 2/3 种子，其均值不能代表三种子的完整归因结论。",
        "", "| 场景 | 对照 | 吞吐变化 | TTFT 降低 | TPOT 降低 | 三项同向改善种子 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for scenario in SCENARIOS:
        summary[scenario] = {}
        for key, (before_name, after_name, label) in comparisons.items():
            changes = {field: [] for field in FIELDS}
            for seed in SEEDS:
                before = records[scenario, seed][before_name]
                after = records[scenario, seed][after_name]
                if before is None or after is None:
                    continue
                for field in FIELDS:
                    changes[field].append(gain(before[field], after[field],
                                               field in ("output_throughput_tokens_per_s",
                                                         "completion_fraction")))
            sample_count = len(changes[FIELDS[0]])
            three = sum(all(changes[field][index] > 0 for field in FIELDS[:3])
                        for index in range(sample_count))
            summary[scenario][key] = {
                field: {"per_seed_percent": values,
                        "mean_percent": mean(values) if values else None,
                        "sample_sd_percent": stdev(values) if len(values) > 1 else None,
                        "improved_seeds": sum(value > 0 for value in values)}
                for field, values in changes.items()
            }
            summary[scenario][key]["three_metrics_improved_seeds"] = three
            summary[scenario][key]["completed_pairs"] = sample_count
            def fmt(field: str) -> str:
                values = changes[field]
                if not values:
                    return "无完整配对"
                sd = f" ± {stdev(values):.2f}%" if len(values) > 1 else ""
                return (f"{mean(values):+.2f}%{sd} "
                        f"({sum(value > 0 for value in values)}/{sample_count} 完成)")
            lines.append(
                f"| {scenario} | {label} | "
                f"{fmt('output_throughput_tokens_per_s')} | "
                f"{fmt('ttft_p95_s')} | {fmt('tpot_p95_s')} | {three}/{sample_count} 完成 |")
    multi_placement = summary["multi"]["placement_only"]["output_throughput_tokens_per_s"]
    multi_scheduler = summary["multi"]["scheduler_only"]["output_throughput_tokens_per_s"]
    lines += [
        "", "## 解读", "",
        f"三集群中，固定 Helix 调度仅更换放置使吞吐平均增加 "
        f"{multi_placement['mean_percent']:.2f}%（3/3 种子完成）；"
        f"固定新放置再更换调度增加 {multi_scheduler['mean_percent']:.2f}%。",
        "新调度进一步降低 TPOT，但相对于中间方案的 TTFT 仅 1/3 种子改善。",
        "单集群中间方案有 1/3 种子触发 Helix 在线路由断言；"
        "因此不能声称其在官方高负载下稳定可行，也不能把 2/3 完成种子的均值写成完整三种子归因。",
        "", "原始记录及日志位于 `runs/seed*/{single,multi}/paper_*.{json,log}`。",
        "本表使用固定窗口、未排空尾部请求的在线协议；具体绝对延迟",
        "和完成率应连同窗口末积压一起解释。",
        "",
    ]
    (HERE / "PAPER_PLACEMENT.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "paper_placement_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Validated official-load three-way records and wrote PAPER_PLACEMENT.md")


if __name__ == "__main__":
    main()

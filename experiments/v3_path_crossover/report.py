"""Validate and summarize the registered fixed-topology crossover matrix."""

from __future__ import annotations

import json
import math
import statistics
from itertools import combinations
from pathlib import Path

from experiments.v3_path_crossover.run import (
    CELLS, FORMAL_SEEDS, HERE, LOADS, NETWORKS, PROTOCOL, check_frozen, digest,
    read, write,
)

METRICS = (
    ("output_throughput_tokens_per_s", "throughput_tokens_s", "higher"),
    ("ttft_p95_s", "p95_ttft_s", "lower"),
    ("tpot_p95_s", "p95_tpot_s", "lower"),
    ("completion_fraction", "completion_fraction", "higher"),
    ("backlog_at_window_end", "end_backlog", "lower"),
)


def result_path(load: str, network: str, cell: str, seed: int) -> Path:
    return HERE / "runs/formal_isolated" / load / network / f"{cell}_seed{seed}.json"


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    low = int(position)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)


def mean_sd(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def collect() -> tuple[dict, dict]:
    frozen = check_frozen()
    rows = {}
    inputs = {"audit.json": digest(HERE / "audit.json")}
    for load in LOADS:
        for network in NETWORKS:
            for cell in CELLS:
                for seed in FORMAL_SEEDS:
                    path = result_path(load, network, cell, seed)
                    if not path.is_file():
                        raise FileNotFoundError(f"Formal matrix incomplete: {path}")
                    row = read(path)
                    expected = {
                        "load_label": load, "network_profile": network,
                        "path_space": cell, "seed": seed, "duration_s": 1800,
                        "warmup_s": 0, "protocol_sha256": frozen["protocol_sha256"],
                        "pythonhashseed": "0",
                    }
                    if any(row.get(key) != value for key, value in expected.items()):
                        raise ValueError(f"Formal identity mismatch in {path}")
                    if len(row.get("query_samples", {})) != row.get("arrivals"):
                        raise ValueError(f"Incomplete query samples in {path}")
                    key = (load, network, cell, seed)
                    rows[key] = row
                    inputs[path.relative_to(HERE).as_posix()] = digest(path)
        for seed in FORMAL_SEEDS:
            hashes = {rows[(load, network, cell, seed)]["trace_sha256"]
                      for network in NETWORKS for cell in CELLS}
            if len(hashes) != 1:
                raise ValueError(f"Trace mismatch for {load}/seed{seed}")
    return rows, inputs


def summarize(rows: dict) -> dict:
    conditions = {}
    for load in LOADS:
        for network in NETWORKS:
            key = f"{load}/{network}"
            conditions[key] = {}
            for cell in CELLS:
                per_seed = [rows[(load, network, cell, seed)] for seed in FORMAL_SEEDS]
                stats = {}
                for source, label, _direction in METRICS:
                    values = [float(row[source]) for row in per_seed]
                    avg, sd = mean_sd(values)
                    stats[label] = {"per_seed": values, "mean": avg, "sample_sd": sd}
                stats["paths_used_per_seed"] = [len(row["route_counts"]) for row in per_seed]
                stats["partial_hops_per_seed"] = [
                    sum(entry["partial_hops"] for entry in row["path_records"].values())
                    for row in per_seed]
                stats["decode_batch_mean_per_seed"] = [
                    row["decode_batches"]["mean_batch"] for row in per_seed]
                stats["decode_single_share_per_seed"] = [
                    row["decode_batches"]["single_share"] for row in per_seed]
                stats["kv_peak_fraction_per_seed"] = [row["kv_peak_fraction"]
                                                       for row in per_seed]
                stats["arrivals_per_seed"] = [row["arrivals"] for row in per_seed]
                stats["tpot_sample_count_per_seed"] = [row["queries_with_tpot_samples"]
                                                       for row in per_seed]
                stats["recorded_prompt_routes_per_seed"] = [len(row["path_records"])
                                                             for row in per_seed]
                stats["kv_deferred_checks_per_seed"] = [row["kv_admission"]["deferred_checks"]
                                                         for row in per_seed]
                conditions[key][cell] = stats

            mean_tpot = {cell: conditions[key][cell]["p95_tpot_s"]["mean"]
                         for cell in CELLS}
            mean_throughput = {cell: conditions[key][cell]["throughput_tokens_s"]["mean"]
                               for cell in CELLS}
            mean_completion = {cell: conditions[key][cell]["completion_fraction"]["mean"]
                               for cell in CELLS}
            best_throughput = max(mean_throughput.values())
            best_completion = max(mean_completion.values())
            eligible = [cell for cell in CELLS
                        if mean_throughput[cell] >= 0.99 * best_throughput and
                        mean_completion[cell] >= best_completion - 0.01]
            eligible = sorted(eligible, key=lambda cell: mean_tpot[cell])
            winner = None
            # The registered rule requires the overall lowest mean TPOT,
            # not merely the best TPOT after filtering by the guardrails.
            if eligible and mean_tpot[eligible[0]] == min(mean_tpot.values()):
                if len(eligible) == 1:
                    winner = eligible[0]
                else:
                    best, second = eligible[:2]
                    if mean_tpot[best] <= 0.99 * mean_tpot[second]:
                        winner = best
            conditions[key]["selection"] = {
                "eligible_by_guardrails": eligible,
                "mean_p95_tpot_s": mean_tpot,
                "winner": winner,
                "status": "unique_winner" if winner else "tradeoff_or_tie",
            }

    winners = {key: value["selection"]["winner"]
               for key, value in conditions.items()}
    comparisons = []
    for load in LOADS:
        left, right = f"{load}/nominal", f"{load}/crosslink_4x"
        if winners[left] and winners[right] and winners[left] != winners[right]:
            a, b = winners[left], winners[right]
            directional = sum(
                rows[(load, "nominal", a, seed)]["tpot_p95_s"] <
                rows[(load, "nominal", b, seed)]["tpot_p95_s"] and
                rows[(load, "crosslink_4x", b, seed)]["tpot_p95_s"] <
                rows[(load, "crosslink_4x", a, seed)]["tpot_p95_s"]
                for seed in FORMAL_SEEDS)
            comparisons.append({"axis": "network", "load": load,
                                "from": left, "to": right,
                                "winner_from": a, "winner_to": b,
                                "paired_seed_directions": directional,
                                "confirmed_by_rule": directional >= 2})
    ordered_loads = list(LOADS)
    for network in NETWORKS:
        for left_load, right_load in combinations(ordered_loads, 2):
            left, right = f"{left_load}/{network}", f"{right_load}/{network}"
            if winners[left] and winners[right] and winners[left] != winners[right]:
                a, b = winners[left], winners[right]
                directional = sum(
                    rows[(left_load, network, a, seed)]["tpot_p95_s"] <
                    rows[(left_load, network, b, seed)]["tpot_p95_s"] and
                    rows[(right_load, network, b, seed)]["tpot_p95_s"] <
                    rows[(right_load, network, a, seed)]["tpot_p95_s"]
                    for seed in FORMAL_SEEDS)
                comparisons.append({"axis": "load", "network": network,
                                    "from": left, "to": right,
                                    "winner_from": a, "winner_to": b,
                                    "paired_seed_directions": directional,
                                    "confirmed_by_rule": directional >= 2})
    confirmed = [item for item in comparisons if item["confirmed_by_rule"]]
    return {"conditions": conditions, "winner_map": winners,
            "crossover_comparisons": comparisons,
            "crossover_confirmed": bool(confirmed),
            "confirmed_comparisons": confirmed}


def common_completed(rows: dict) -> dict:
    result = {}
    for load in LOADS:
        for seed in FORMAL_SEEDS:
            cell_rows = [rows[(load, network, cell, seed)]
                         for network in NETWORKS for cell in CELLS]
            common = set.intersection(*[
                {uid for uid, sample in row["query_samples"].items()
                 if sample["completed"]}
                for row in cell_rows])
            bundle = {"common_completed_count": len(common), "cells": {}}
            for network in NETWORKS:
                for cell in CELLS:
                    key = f"{network}/{cell}"
                    samples = rows[(load, network, cell, seed)]["query_samples"]
                    bundle["cells"][key] = {
                        "p95_ttft_s": p95([samples[uid]["ttft_s"] for uid in common]),
                        "p95_tpot_s": p95([samples[uid]["tpot_s"] for uid in common]),
                    }
            result[f"{load}/seed{seed}"] = bundle
    return result


def workload_summary(rows: dict) -> dict:
    result = {}
    for load in LOADS:
        for seed in FORMAL_SEEDS:
            samples = rows[(load, "nominal", "canonical", seed)]["query_samples"].values()
            prompt = sum(s["input_tokens"] for s in samples)
            output = sum(s["output_tokens"] for s in samples)
            result[f"{load}/seed{seed}"] = {
                "target_total_offered_tokens_per_s": LOADS[load],
                "observed_total_offered_tokens_per_s": (prompt + output) / 1800,
                "observed_prompt_tokens": prompt, "requested_output_tokens": output,
                "arrivals": len(rows[(load, "nominal", "canonical", seed)]["query_samples"]),
            }
    return result


def common_completed_sensitivity(analysis: dict) -> dict:
    """Check the primary winner pairs on a fixed completed-request cohort.

    This diagnostic never changes the registered primary winner/decision.
    """
    comparisons = []
    for primary in analysis["confirmed_comparisons"]:
        left_load, left_network = primary["from"].split("/")
        right_load, right_network = primary["to"].split("/")
        a, b = primary["winner_from"], primary["winner_to"]
        per_seed = []
        for seed in FORMAL_SEEDS:
            left = analysis["common_completed"][f"{left_load}/seed{seed}"]["cells"]
            right = analysis["common_completed"][f"{right_load}/seed{seed}"]["cells"]
            values = [left[f"{left_network}/{a}"]["p95_tpot_s"],
                      left[f"{left_network}/{b}"]["p95_tpot_s"],
                      right[f"{right_network}/{a}"]["p95_tpot_s"],
                      right[f"{right_network}/{b}"]["p95_tpot_s"]]
            direction = (values[0] < values[1] and values[3] < values[2]
                         if all(v is not None for v in values) else None)
            per_seed.append({"seed": seed, "p95_tpot_s_left_a_b_right_a_b": values,
                             "same_crossover_direction": direction})
        count = sum(item["same_crossover_direction"] is True for item in per_seed)
        comparisons.append({"axis": primary["axis"], "from": primary["from"],
                            "to": primary["to"], "winner_from": a, "winner_to": b,
                            "primary_paired_seed_directions": primary["paired_seed_directions"],
                            "common_completed_paired_seed_directions": count,
                            "preserves_two_of_three_direction_rule": count >= 2,
                            "per_seed": per_seed})
    return {"role": "sensitivity diagnostic; does not replace the preregistered primary decision",
            "comparisons": comparisons,
            "any_primary_crossover_preserves_direction_rule": any(
                item["preserves_two_of_three_direction_rule"] for item in comparisons)}


def markdown(analysis: dict) -> str:
    out = ["# 固定拓扑下的路径策略交叉实验结果", "",
           "实验类型：离散事件仿真（simulation_only），不是实体 GPU 集群部署实测。"
           "正式种子为 0、1、2，每格 1800 仿真秒、零预热、窗口末不排空；共 54 格。", "",
           "同一 C1_multi 24 GPU 部署；三策略均使用相同 M3 排序和 KV 生命周期预约。"
           "跨集群计算链路在 crosslink_4x 条件下带宽乘 4，其他物理量固定。", "",
           "负载是生成器的输入加输出 token 到达速率目标；吞吐只计窗口内完成的输出 token。"
           "两者口径不同，不能直接相除解释为利用率。不同种子的实际到达速率略有变化，但同一负载/种子的六个条件严格共用同一轨迹。", "",
           "## 各负载和网络条件的三种子均值 ± 样本标准差", "",
           "| 负载 | 网络 | 路径空间 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 末端积压 | Decode 均批 | KV 峰值比例 |", "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for load in LOADS:
        for network in NETWORKS:
            key = f"{load}/{network}"
            row = analysis["conditions"][key]
            for cell in CELLS:
                values = row[cell]
                def fmt(name, digits=3):
                    stat = values[name]
                    return f"{stat['mean']:.{digits}f} ± {stat['sample_sd']:.{digits}f}"
                out.append(
                    f"| {load} ({LOADS[load]:g}) | {network} | {cell} | "
                    f"{fmt('throughput_tokens_s')} | {fmt('p95_ttft_s')} | "
                    f"{fmt('p95_tpot_s')} | {fmt('completion_fraction', 4)} | "
                    f"{fmt('end_backlog', 1)} | "
                    f"{statistics.mean(values['decode_batch_mean_per_seed']):.2f} | "
                    f"{statistics.mean(values['kv_peak_fraction_per_seed']):.3f} |")
            selection = row["selection"]
            out.append(f"| {load} ({LOADS[load]:g}) | {network} | **winner: "
                       f"{selection['winner'] or '无唯一胜者'}** | | | | | | | |")
    out += ["", "## 交叉判定", ""]
    if analysis["confirmed_comparisons"]:
        out.append("符合预注册规则的方向性交叉：")
        for item in analysis["confirmed_comparisons"]:
            out.append(f"- {item['axis']} 轴：{item['from']} 的 {item['winner_from']} → "
                       f"{item['to']} 的 {item['winner_to']}；三种子中 "
                       f"{item['paired_seed_directions']}/3 同向。")
    elif analysis["crossover_comparisons"]:
        out.append("观察到候选胜者变化，但未达到至少 2/3 配对种子同向的确认规则：")
        for item in analysis["crossover_comparisons"]:
            out.append(f"- {item['axis']} 轴：{item['from']} 的 {item['winner_from']} → "
                       f"{item['to']} 的 {item['winner_to']}；同向 "
                       f"{item['paired_seed_directions']}/3。")
    else:
        out.append("本矩阵未发现具有唯一胜者变化的负载或网络条件对。")
    out += ["", "三种子仅作描述性证据，不代表统计显著性。吞吐和完成率用于尾延迟胜者的护栏；"
            "不同条件间的绝对吞吐不直接互比。", "",
            "## 机制观测", "",
            "下表为种子 0/1/2 的原始观测。部分层跳转表示实际执行层数小于该 GPU 驻留层数的跳转；"
            "Decode 均批按 GPU 执行事件计数，不能当作输出 token 数。"
            "这些观测解释性能差异的候选原因，不单独构成动态控制器有效性或因果证明。", "",
            "| 负载/网络 | 路径空间 | 实际路径数 0/1/2 | 部分层跳转/准入请求 0/1/2 | Decode 均批 0/1/2 | 单 token 批占比 0/1/2 | KV 延后检查数 0/1/2 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for condition, values in analysis["conditions"].items():
        for cell in CELLS:
            stats = values[cell]
            per_route = [hops / count if count else 0 for hops, count in zip(
                stats["partial_hops_per_seed"], stats["recorded_prompt_routes_per_seed"])]
            join = lambda items, digits=None: "/".join(
                str(v) if digits is None else f"{v:.{digits}f}" for v in items)
            out.append(f"| {condition} | {cell} | {join(stats['paths_used_per_seed'])} | "
                       f"{join(per_route, 3)} | {join(stats['decode_batch_mean_per_seed'], 2)} | "
                       f"{join(stats['decode_single_share_per_seed'], 3)} | "
                       f"{join(stats['kv_deferred_checks_per_seed'])} |")
    total_deferred = sum(sum(values[cell]["kv_deferred_checks_per_seed"])
                         for values in analysis["conditions"].values() for cell in CELLS)
    max_kv = max(max(values[cell]["kv_peak_fraction_per_seed"])
                 for values in analysis["conditions"].values() for cell in CELLS)
    out += ["", f"全部窗口的请求级 KV 延后检查合计 {total_deferred} 次，"
            f"单 GPU KV 预约峰值最高为容量的 {max_kv:.2%}。"]
    if total_deferred == 0:
        out.append("本矩阵未出现请求因 KV 容量不足而延后的事件；它不提供容量受限条件下准入机制收益的验证。")
    out += ["", "## 共同完成请求敏感性检查", "",
            "每个负载/种子在六个条件中取共同完成请求的交集，固定请求集合后重算 P95 TPOT（秒）。"
            "这是对窗口截断和请求难度差异的诊断；不替代预注册主指标和护栏。TTFT 同口径数值见 analysis.json。", "",
            "| 负载/种子 | 共同完成数 | nominal canonical | nominal partial | nominal full | 4x canonical | 4x partial | 4x full |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for key, bundle in analysis["common_completed"].items():
        values = [bundle["cells"][f"{network}/{cell}"]["p95_tpot_s"]
                  for network in NETWORKS for cell in CELLS]
        cells = [f"{value:.6f}" if value is not None else "无样本" for value in values]
        out.append(f"| {key} | {bundle['common_completed_count']} | " + " | ".join(cells) + " |")
    sensitivity = analysis.get("common_completed_sensitivity", {})
    for item in sensitivity.get("comparisons", []):
        out.append(f"- {item['from']} → {item['to']}：主口径有 "
                   f"{item['primary_paired_seed_directions']}/3 种子同向，"
                   f"共同完成请求口径有 {item['common_completed_paired_seed_directions']}/3 同向。")
    if sensitivity.get("comparisons") and not sensitivity["any_primary_crossover_preserves_direction_rule"]:
        out += ["", "**证据限制：主口径符合预注册交叉规则，但两处交叉在共同完成请求口径下都未保持至少 2/3 同向。"
                "当前结果对观测请求集合敏感，不能据此宣称已稳健证明动态路径空间切换的必要性。"
                "这也不能单独确定差异由窗口截断造成，仍需受控的后续验证。**"]
    out += ["", "## 到达负载核对", "",
            "| 负载/种子 | 目标输入+输出 token/s | 实际输入+输出 token/s | 到达请求数 |",
            "| --- | ---: | ---: | ---: |"]
    for key, value in analysis.get("workloads", {}).items():
        out.append(f"| {key} | {value['target_total_offered_tokens_per_s']:.0f} | "
                   f"{value['observed_total_offered_tokens_per_s']:.3f} | {value['arrivals']} |")
    out += ["", "## 证据范围", "",
            "该矩阵只检验固定路径空间偏好是否随负载或链路容量改变。"
            "它不能替代动态自适应控制器、42 GPU 泛化，以及少 GPU 相比 Helix 全 GPU 的对比实验。"
            "主指标按仿真事件时间统计，未把调度器在 CPU 上的真实计算时间加入请求延迟。"
            "校验细节见 validation.json 与 INTEGRITY_NOTES_CN.md。", ""]
    return "\n".join(out)


def main() -> None:
    from experiments.v3_path_crossover.validate import validate_matrix
    validation = validate_matrix()
    write(HERE / "validation.json", validation)
    if not validation["complete"]:
        raise ValueError("Formal matrix is incomplete or invalid; see validation.json")
    rows, inputs = collect()
    analysis = summarize(rows)
    analysis["common_completed"] = common_completed(rows)
    analysis["common_completed_sensitivity"] = common_completed_sensitivity(analysis)
    analysis["workloads"] = workload_summary(rows)
    analysis["inputs_sha256"] = inputs
    analysis["protocol_sha256"] = digest(HERE / "protocol.json")
    analysis["analysis_sources_sha256"] = {
        path: digest(HERE / path) for path in ("report.py", "validate.py")}
    analysis["validation_sha256"] = digest(HERE / "validation.json")
    write(HERE / "analysis.json", analysis)
    (HERE / "RESULTS_CN.md").write_text(markdown(analysis), encoding="utf-8")
    print(markdown(analysis))


if __name__ == "__main__":
    main()

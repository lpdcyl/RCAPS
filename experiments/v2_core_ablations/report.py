"""Audit and summarize the three V2 method-level ablation tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.registry import METHODS
from .audit_layouts import audit as audit_layout


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REFERENCE = ROOT / "experiments" / "v2_method_ablation" / "runs"
RUNS = HERE / "runs"
SEEDS = (0, 1, 2)
OFFERED = {"single": 700.0, "multi": 320.0}
METRICS = (
    ("output_throughput_tokens_per_s", "吞吐 token/s ↑", "higher"),
    ("ttft_p95_s", "P95 TTFT s ↓", "lower"),
    ("tpot_p95_s", "P95 TPOT s ↓", "lower"),
    ("completion_fraction", "完成率 % ↑", "higher"),
    ("backlog_at_window_end", "末端积压 ↓", "lower"),
)
TABLES = {
    "modeling": (
        ("Compute-only", "rcaps_v2_model_compute"),
        ("Compute + Communication", "rcaps_v2_model_static"),
        ("Event DAG", "rcaps_v2_model_event")),
    "placement": (
        ("Fixed Structure", "rcaps_v2_fixed_structure"),
        ("Fixed Branches", "rcaps_v2_fixed_branches"),
        ("Full Adaptive", "rcaps_v2")),
    "scheduling": (
        ("Static DAG", "rcaps_v2_static_dag"),
        ("Queue-Aware DAG", "rcaps_v2_queue_dag"),
        ("Full V2", "rcaps_v2")),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layout(method: str, scenario: str) -> tuple[Path, Path]:
    return METHODS[method].layout(scenario, ROOT)


def source(method: str, scenario: str, seed: int) -> tuple[Path, str]:
    if method == "rcaps_v2_model_event":
        actual = "rcaps_v2"
    elif method == "rcaps_v2_model_static" and scenario == "single":
        actual = "rcaps_v2_model_compute"
    else:
        actual = method
    directory = REFERENCE if actual in ("rcaps_v2", "rcaps_v2_fixed_structure") else RUNS
    return directory / scenario / f"seed{seed}" / f"{actual}.json", actual


def record(method: str, scenario: str, seed: int) -> tuple[dict, dict]:
    path, actual = source(method, scenario, seed)
    if not path.is_file():
        raise FileNotFoundError(f"Formal window missing: {path}")
    expected_solution, expected_cluster = layout(method, scenario)
    source_solution, source_cluster = layout(actual, scenario)
    if (digest(expected_solution), digest(expected_cluster)) != (
            digest(source_solution), digest(source_cluster)):
        raise ValueError(f"Reuse layout differs: {scenario}/{method} <- {actual}")
    if METHODS[method].evaluate is not METHODS[actual].evaluate:
        if not (method == "rcaps_v2_model_event" and actual == "rcaps_v2"):
            raise ValueError(f"Reuse scheduler differs: {scenario}/{method} <- {actual}")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {"system": actual, "scenario": scenario, "seed": seed,
                "offered_tokens_per_s": OFFERED[scenario], "duration_s": 1800,
                "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
                "query_samples_schema": 1,
                "solution_sha256": digest(source_solution),
                "sim_cluster_sha256": digest(source_cluster)}
    for key, target in expected.items():
        if value.get(key) != target:
            raise ValueError(f"{path}: {key} differs: {value.get(key)!r} != {target!r}")
    if len(value.get("query_samples", {})) != value["arrivals"]:
        raise ValueError(f"{path}: incomplete request identities")
    return value, {"path": str(path.relative_to(ROOT)), "sha256": digest(path),
                   "source_method": actual, "reused": actual != method}


def same_trace(left: dict, right: dict) -> dict:
    for field in MATCH_FIELDS:
        if left.get(field) != right.get(field):
            raise ValueError(f"Mismatched paired field {field}")
    return common_cohort(left, right)


def mean_sd(values: list[float]) -> dict:
    return {"mean": mean(values), "sample_sd": stdev(values),
            "by_seed": dict(zip(SEEDS, values))}


def absolute(records: list[dict]) -> dict:
    return {key: mean_sd([row[key] * (100 if key == "completion_fraction" else 1)
                          for row in records]) for key, _, _ in METRICS}


def paired(full: list[dict], control: list[dict]) -> dict:
    result = {}
    for key, _, direction in METRICS:
        gains = []
        for a, b in zip(full, control):
            if b[key] <= 0:
                raise ValueError(f"Nonpositive control metric: {key}")
            gains.append(100 * (a[key] / b[key] - 1 if direction == "higher"
                                else 1 - a[key] / b[key]))
        result[key] = mean_sd(gains)
    result["common_cohort_by_seed"] = [same_trace(a, b)
                                       for a, b in zip(full, control)]
    return result


def placement_structure(method: str, scenario: str) -> dict:
    solution, _ = layout(method, scenario)
    path = solution.parent / "placement.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    spans = data["intervals"].values()
    copies = sum(end - start for start, end in spans)
    return {"stem": data["stem"], "prefix_layers": data["prefix_layers"],
            "branches": len(data["branches"]), "model_layer_copies": copies,
            "placement_sha256": digest(path)}


def mean_wait(records: list[dict], nodes: list[int] | None = None,
              key: str = "gpu_queue_request_s") -> dict:
    values = []
    for row in records:
        selection = (f"Compute-{node + 2}" for node in nodes) if nodes else row[key]
        values.append(sum(row[key].get(uid, 0.0) for uid in selection) / row["arrivals"])
    return mean_sd(values)


def rank(values: list[float]) -> list[float]:
    result = []
    for value in values:
        below = sum(other < value for other in values)
        equal = sum(other == value for other in values)
        result.append(below + (equal + 1) / 2)
    return result


def spearman_agreement(scores: list[float], outcomes: list[float],
                       direction: str) -> float | None:
    x = rank(scores)
    y = rank(outcomes if direction == "lower" else [-value for value in outcomes])
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def diagnostic_ranking(scenario: str) -> dict:
    manifest_path = HERE / "modeling_candidates" / f"{scenario}.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {row["id"]: row for row in data["entries"]}
    ids = data["diagnostic_ids"]
    rows = []
    missing = []
    traces = {}
    for candidate_id in ids:
        outcome = {}
        for seed in (100, 101):
            path = HERE / "diagnostic_runs" / scenario / candidate_id / f"seed{seed}.json"
            if not path.is_file():
                missing.append(str(path.relative_to(ROOT)))
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            solution = HERE / "layouts" / "diagnostic" / scenario / candidate_id / "solution.ini"
            cluster = solution.parent / "simulator_cluster.ini"
            expected = {"scenario": scenario, "candidate_id": candidate_id,
                        "seed": seed, "offered_tokens_per_s": OFFERED[scenario],
                        "duration_s": 600, "warmup_s": 0,
                        "evaluation_protocol": "fixed_window_no_tail_drain",
                        "solution_sha256": digest(solution),
                        "sim_cluster_sha256": digest(cluster)}
            for key, target in expected.items():
                if value.get(key) != target:
                    raise ValueError(f"Diagnostic {path}: {key} differs")
            if len(value.get("query_samples", {})) != value["arrivals"]:
                raise ValueError(f"Diagnostic {path}: request identities incomplete")
            prior = traces.setdefault(seed, value["trace_sha256"])
            if value["trace_sha256"] != prior:
                raise ValueError(f"Diagnostic {scenario}/seed{seed}: trace differs")
            outcome[str(seed)] = {key: value[key] for key, _, _ in METRICS}
        if len(outcome) != 2:
            continue
        rows.append({"candidate_id": candidate_id,
                     "scores": entries[candidate_id]["scores"],
                     "online_by_seed": outcome,
                     "online_mean": {key: mean(outcome[str(seed)][key]
                                          for seed in (100, 101))
                                     for key, _, _ in METRICS}})
    accuracy = {}
    for evaluator in ("compute_only", "compute_comm", "event_dag"):
        accuracy[evaluator] = {}
        scores = [row["scores"][evaluator] for row in rows]
        for key, _, direction in METRICS[:3]:
            agreement = (spearman_agreement(
                scores, [row["online_mean"][key] for row in rows], direction)
                if len(rows) == len(ids) else None)
            accuracy[evaluator][key] = agreement
    return {"candidate_ids": ids, "rows": rows, "missing_windows": missing,
            "rank_agreement": accuracy}


def formatted(item: dict, digits: int = 3) -> str:
    return f"{item['mean']:.{digits}f} ± {item['sample_sd']:.{digits}f}"


def main() -> None:
    report = {"protocol": "70B, official 700/320 offered, seeds 0/1/2, 1800 s zero warmup",
              "scenarios": {}}
    lines = ["# RCAPS V2 三项方法级消融", "",
             "三张表分别隔离给定候选池的评价方式、结构搜索空间、固定布局上的路由状态信息。"
             "三表差额不能相加；所有百分比均为相同轨迹种子的配对变化。"
             "每格为三个完整窗口的均值 ± 样本标准差，P95 是逐种子 P95 的均值。", ""]
    for scenario in ("single", "multi"):
        section = {"tables": {}, "diagnostic": diagnostic_ranking(scenario)}
        section["layout_audit"] = {
            method: audit_layout(*layout(method, scenario), scenario)
            for method in sorted({method for rows in TABLES.values()
                                  for _, method in rows})}
        lines.extend([f"## {'单集群' if scenario == 'single' else '三集群'}", ""])
        for table, rows in TABLES.items():
            title = {"modeling": "Table A：建模评价", "placement": "Table B：共享复制放置",
                     "scheduling": "Table C：在线路由"}[table]
            values = {}
            for label, method in rows:
                records, sources = zip(*(record(method, scenario, seed) for seed in SEEDS))
                values[method] = {"label": label, "absolute": absolute(records),
                                  "source": sources}
                if table == "placement":
                    structure = placement_structure(method, scenario)
                    values[method]["structure"] = structure
                    values[method]["shared_gpu_queue_request_s_per_arrival"] = mean_wait(
                        list(records), structure["stem"])
                elif table == "scheduling":
                    values[method]["gpu_queue_request_s_per_arrival"] = mean_wait(list(records))
                    values[method]["outbound_wait_request_s_per_arrival"] = mean_wait(
                        list(records), key="outbound_wait_request_s")
                if method != rows[-1][1]:
                    # The final row is the complete model/placement/scheduler.
                    full = [record(rows[-1][1], scenario, seed)[0] for seed in SEEDS]
                    values[method]["full_vs_control"] = paired(full, list(records))
            full_records = [record(rows[-1][1], scenario, seed)[0] for seed in SEEDS]
            for _, method in rows:
                for seed, (item, _) in zip(SEEDS, (record(method, scenario, s) for s in SEEDS)):
                    same_trace(full_records[seed], item)
            section["tables"][table] = values
            lines.extend([f"### {title}", "",
                          "| 配置 | 吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 % ↑ | 末端积压 ↓ |",
                          "| --- | ---: | ---: | ---: | ---: | ---: |"])
            for label, method in rows:
                result = values[method]["absolute"]
                lines.append("| " + " | ".join(
                    [label] + [formatted(result[key]) for key, _, _ in METRICS]) + " |")
            lines.append("")
            if table == "placement":
                lines.extend(["| 配置 | 共享层数 | 后缀数 | 模型层副本数 | 共享 GPU 排队请求秒／到达请求 |",
                              "| --- | ---: | ---: | ---: | ---: |"])
                for label, method in rows:
                    result = values[method]
                    structure = result["structure"]
                    lines.append(f"| {label} | {structure['prefix_layers']} | "
                                 f"{structure['branches']} | {structure['model_layer_copies']} | "
                                 f"{formatted(result['shared_gpu_queue_request_s_per_arrival'])} |")
                lines.append("")
            elif table == "scheduling":
                lines.extend(["| 配置 | GPU 排队请求秒／到达请求 | 出站等待请求秒／到达请求 |",
                              "| --- | ---: | ---: |"])
                for label, method in rows:
                    result = values[method]
                    lines.append(f"| {label} | "
                                 f"{formatted(result['gpu_queue_request_s_per_arrival'])} | "
                                 f"{formatted(result['outbound_wait_request_s_per_arrival'])} |")
                lines.extend(["", "出站等待包含发送端和下游资源限制，不解释为纯链路队列。", ""])
        rank_data = section["diagnostic"]["rank_agreement"]
        diagnostic = section["diagnostic"]
        lines.extend([f"建模候选排序诊断：{len(diagnostic['rows'])}/{len(diagnostic['candidate_ids'])} "
                      "个预定结构样本有完整开发窗口，种子 100/101，600 秒；"
                      "Spearman 一致性范围 −1 到 +1，正值代表代理分数排序与在线指标的好坏方向一致。", "",
                      "| 评价器 | 吞吐排序 | TTFT 排序 | TPOT 排序 |",
                      "| --- | ---: | ---: | ---: |"])
        for evaluator, label in (("compute_only", "Compute-only"),
                                 ("compute_comm", "Compute + Communication"),
                                 ("event_dag", "Event DAG")):
            rank_values = rank_data[evaluator]
            cells = ["未定义" if rank_values[key] is None else f"{rank_values[key]:+.3f}"
                     for key, _, _ in METRICS[:3]]
            lines.append("| " + " | ".join([label, *cells]) + " |")
        lines.append("")
        report["scenarios"][scenario] = section
    lines.extend(["建模表的候选生成仍使用 V2 启发式，因此仅检验同池评价。"
                  "调度表三种配置都保留就绪 Decode 传输合并，因此只检验路径代价中的动态信息。"
                  "三个正式种子不用于显著性推断；这些是 Helix 离散事件仿真结果。", ""])
    (HERE / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'RESULTS_CN.md'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()

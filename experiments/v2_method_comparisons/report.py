"""Audit and report V2 whole-method replacement comparisons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.registry import METHODS
from experiments.v2_core_ablations.audit_layouts import audit as audit_layout
from experiments.v2_core_ablations.report import diagnostic_ranking, spearman_agreement
from rcaps.placement import adaptive
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel

from .placement import static_measure


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "experiments" / "v2_method_ablation" / "runs"
RUNS = HERE / "runs"
SEEDS = (0, 1, 2)
LOADS = {"single": 700.0, "multi": 320.0}
GROUPS = {
    "M1：建模与评价": (("容量与连通性模型", "rcaps_v2_capacity_only"),
                      ("静态异构资源模型", "rcaps_v2_static_resource_model"),
                      ("V2 多请求事件 DAG 模型", "rcaps_v2")),
    "M2：自适应放置": (("固定共享复制结构", "rcaps_v2_fixed_structure"),
                    ("有界 beam search", "rcaps_v2_beam_placement"),
                    ("V2 自适应放置搜索", "rcaps_v2")),
    "M3：在线调度": (("固定合法路径轮转", "rcaps_v2_static_routes"),
                  ("负载感知完整流水线", "rcaps_v2_live_pipeline"),
                  ("V2 在线 DAG 调度", "rcaps_v2")),
}
KEYS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
        "completion_fraction", "backlog_at_window_end")
LABELS = ("吞吐 token/s ↑", "P95 TTFT s ↓", "P95 TPOT s ↓", "完成率 % ↑", "积压 ↓")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean_sd(values: list[float]) -> dict:
    return {"mean": mean(values), "sample_sd": stdev(values),
            "by_seed": dict(zip(SEEDS, values))}


def source(method: str, scenario: str, seed: int) -> Path:
    base = (RUNS if method in ("rcaps_v2_static_resource_model",
                               "rcaps_v2_beam_placement",
                               "rcaps_v2_live_pipeline") else OLD)
    return base / scenario / f"seed{seed}" / f"{method}.json"


def audited_record(method: str, scenario: str, seed: int) -> tuple[dict | None, dict]:
    path = source(method, scenario, seed)
    if not path.is_file():
        log = path.with_suffix(".log")
        return None, {"status": "failed" if log.exists() else "not_run",
                      "source": str(path.relative_to(ROOT)),
                      "log": str(log.relative_to(ROOT)) if log.exists() else None}
    solution, cluster = METHODS[method].layout(scenario, ROOT)
    row = json.loads(path.read_text(encoding="utf-8"))
    expected = {"system": method, "scenario": scenario, "seed": seed,
                "offered_tokens_per_s": LOADS[scenario], "duration_s": 1800,
                "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
                "query_samples_schema": 1,
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster)}
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"{path}: {key} differs: {row.get(key)!r} != {value!r}")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"{path}: incomplete request identities")
    for key in KEYS:
        if row.get(key) is None:
            raise ValueError(f"{path}: missing full-window metric {key}")
    return row, {"status": "complete", "source": str(path.relative_to(ROOT)),
                 "sha256": digest(path), "layout": audit_layout(solution, cluster, scenario)}


def aggregate(rows: list[dict]) -> dict:
    return {key: mean_sd([row[key] * (100 if key == "completion_fraction" else 1)
                          for row in rows]) for key in KEYS}


def paired(full: list[dict], alternative: list[dict]) -> dict:
    output = {}
    for a, b in zip(full, alternative):
        for field in MATCH_FIELDS:
            if a.get(field) != b.get(field):
                raise ValueError(f"Mismatched {field}: {a['scenario']}/seed{a['seed']}")
    for key in KEYS:
        values = []
        for a, b in zip(full, alternative):
            if b[key] <= 0:
                raise ValueError(f"Nonpositive {key} control metric")
            values.append(100 * (a[key] / b[key] - 1 if key in
                                 ("output_throughput_tokens_per_s", "completion_fraction")
                                 else 1 - a[key] / b[key]))
        output[key] = mean_sd(values)
    output["common_cohort_by_seed"] = [common_cohort(a, b)
                                       for a, b in zip(full, alternative)]
    return output


def fmt(metric: dict, key: str) -> str:
    digits = 1 if key == "backlog_at_window_end" else 3
    return f"{metric['mean']:.{digits}f} ± {metric['sample_sd']:.{digits}f}"


def wait_metric(rows: list[dict], key: str) -> dict:
    return mean_sd([sum(row.get(key, {}).values()) / row["arrivals"] for row in rows])


def structure(method: str, scenario: str) -> dict:
    solution, _ = METHODS[method].layout(scenario, ROOT)
    path = solution.parent / "placement.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    semantics = {key: row[key] for key in ("stem", "prefix_layers", "branches", "intervals")}
    return {"shared_gpu_count": len(row["stem"]),
            "shared_layers": row["prefix_layers"],
            "suffixes": len(row["branches"]),
            "model_layer_copies": sum(end - start for start, end in row["intervals"].values()),
            "planning_s": row.get("planning_s"),
            "candidate_evaluations": row.get("candidate_evaluations"),
            "placement_sha256": digest(path),
            "semantic_sha256": hashlib.sha256(json.dumps(
                semantics, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def modeling_diagnostic(scenario: str) -> dict:
    """Audit the existing development candidates and score the new static model."""
    existing = diagnostic_ranking(scenario)
    manifest_path = (ROOT / "experiments" / "v2_core_ablations" /
                     "modeling_candidates" / f"{scenario}.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in manifest["entries"]}
    physical, _ = scenario_files(scenario)
    model = TopologyModel(physical)
    reference = static_measure(model, adaptive.reference_state(model, scenario))
    scores = []
    online = {key: [] for key in KEYS[:3]}
    for row in existing["rows"]:
        state = entries[row["candidate_id"]]["state"]
        state["lengths"] = {int(node): value for node, value in state["lengths"].items()}
        scores.append(adaptive.objective(static_measure(model, state), reference))
        for key in online:
            online[key].append(row["online_mean"][key])
    return {"candidate_count": len(scores), "development_seeds": [100, 101],
            "static_resource_rank_agreement": {
                key: spearman_agreement(scores, values,
                                        "higher" if key == "output_throughput_tokens_per_s"
                                        else "lower")
                for key, values in online.items()},
            "event_dag_rank_agreement": existing["rank_agreement"]["event_dag"]}


def main() -> None:
    summary = {"protocol": {"model": "LLaMa70B", "seeds": SEEDS,
                            "loads": LOADS, "duration_s": 1800, "warmup_s": 0},
               "groups": {}}
    lines = ["# RCAPS V2：三项完整方法的替换对照", "",
             "三组各保持另外两项 V2 方法不变，比较简单替代、较强替代和完整 V2。",
             "70B、24 GPU、种子 0/1/2、1800 秒零预热；单集群 700、三集群 320 提供 token/s。",
             "每格是完整窗口的三种子均值 ± 样本标准差；P95 是逐种子 P95 的均值。",
             "失败或未运行窗口不补数值。", ""]
    for scenario in ("single", "multi"):
        lines.extend([f"## {'单集群' if scenario == 'single' else '三集群'}", ""])
        summary["groups"][scenario] = {}
        diagnostic = modeling_diagnostic(scenario)
        summary.setdefault("modeling_diagnostic", {})[scenario] = diagnostic
        for name, options in GROUPS.items():
            records = {}
            provenance = {}
            for label, method in options:
                checked = [audited_record(method, scenario, seed) for seed in SEEDS]
                provenance[method] = [entry for _, entry in checked]
                records[method] = [row for row, _ in checked]
            full = records["rcaps_v2"]
            group = {"methods": {}, "paired": {}}
            lines.extend([f"### {name}", "",
                          "| 方法 | " + " | ".join(LABELS) + " | 完整窗口 |",
                          "| --- | " + " | ".join("---:" for _ in LABELS) + " | ---: |"])
            for label, method in options:
                rows = records[method]
                completed = [row for row in rows if row is not None]
                data = {"provenance": provenance[method],
                        "structure": structure(method, scenario) if name.startswith("M1") or
                        name.startswith("M2") else None}
                if len(completed) == 3:
                    data["absolute"] = aggregate(completed)
                    data["gpu_queue_per_arrival"] = wait_metric(completed, "gpu_queue_request_s")
                    data["outbound_wait_per_arrival"] = wait_metric(
                        completed, "outbound_wait_request_s")
                    data["route_counts_by_seed"] = [row.get("route_counts", {}) for row in completed]
                    cells = [fmt(data["absolute"][key], key) for key in KEYS]
                else:
                    cells = ["不完整"] * len(KEYS)
                group["methods"][method] = data
                lines.append(f"| {label} | " + " | ".join(cells) +
                             f" | {len(completed)}/3 |")
            lines.append("")
            if all(row is not None for row in full):
                lines.extend(["| 完整 V2 相对替代方法：逐种子配对变化 | 吞吐 ↑ | TTFT ↓ | TPOT ↓ | 完成率 ↑ | 积压 ↓ |",
                              "| --- | ---: | ---: | ---: | ---: | ---: |"])
                for label, method in options[:-1]:
                    if any(row is None for row in records[method]):
                        continue
                    effect = paired(full, records[method])
                    group["paired"][method] = effect
                    cells = [fmt(effect[key], key) + "%" for key in KEYS]
                    lines.append(f"| {label} | " + " | ".join(cells) + " |")
                lines.append("")
                lines.extend(["| 配对共同请求 | TTFT 共同数 | 共同 P95 TTFT：V2 / 替代 s | TPOT 共同数 | 共同 P95 TPOT：V2 / 替代 s |",
                              "| --- | ---: | ---: | ---: | ---: |"])
                for label, method in options[:-1]:
                    if method not in group["paired"]:
                        continue
                    cohorts = group["paired"][method]["common_cohort_by_seed"]
                    first = [row["ttft_s"] for row in cohorts]
                    decode = [row["tpot_s"] for row in cohorts]
                    count_first = sum(row["both_observed"] for row in first)
                    count_decode = sum(row["both_observed"] for row in decode)
                    first_v2 = mean_sd([row["main_p95_s"] for row in first])
                    first_alt = mean_sd([row["baseline_p95_s"] for row in first])
                    decode_v2 = mean_sd([row["main_p95_s"] for row in decode])
                    decode_alt = mean_sd([row["baseline_p95_s"] for row in decode])
                    lines.append(f"| {label} | {count_first} | {fmt(first_v2, '')} / "
                                 f"{fmt(first_alt, '')} | {count_decode} | "
                                 f"{fmt(decode_v2, '')} / {fmt(decode_alt, '')} |")
                lines.append("")
            for label, method in options:
                statuses = provenance[method]
                if any(row["status"] != "complete" for row in statuses):
                    failed = ", ".join(f"seed{seed}: {row['status']} ({row['log'] or row['source']})"
                                       for seed, row in zip(SEEDS, statuses)
                                       if row["status"] != "complete")
                    lines.append(f"- {label}：{failed}")
            if any(any(row["status"] != "complete" for row in provenance[method])
                   for _, method in options):
                lines.append("")
            if name.startswith("M1") or name.startswith("M2"):
                official_hash = group["methods"]["rcaps_v2"]["structure"]["semantic_sha256"]
                for label, method in options[:-1]:
                    if group["methods"][method]["structure"]["semantic_sha256"] == official_hash:
                        lines.append(f"{label} 与 V2 选择了执行语义相同的布局；记录为相同决策，不将微小计时差写成放置收益。")
                        lines.append("")
            if name.startswith("M2"):
                lines.extend(["| 放置方法 | 共享 GPU | 共享层 | 后缀 | 模型层副本 | 候选评价 | 规划秒数 |",
                              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
                for label, method in options:
                    item = group["methods"][method]["structure"]
                    lines.append(f"| {label} | {item['shared_gpu_count']} | {item['shared_layers']} | "
                                 f"{item['suffixes']} | {item['model_layer_copies']} | "
                                 f"{item['candidate_evaluations']} | {item['planning_s']:.2f} |")
                lines.append("")
            if name.startswith("M1"):
                lines.extend(["| 完整建模方案 | 候选评价数 | 规划秒数 | 静态评分累计秒数 |",
                              "| --- | ---: | ---: | ---: |"])
                for label, method in options:
                    placement_path = METHODS[method].layout(scenario, ROOT)[0].parent / "placement.json"
                    placement = json.loads(placement_path.read_text(encoding="utf-8"))
                    static_time = placement.get("scoring_s")
                    lines.append(f"| {label} | {placement.get('candidate_evaluations', '—')} | "
                                 f"{placement.get('planning_s', 0.0):.2f} | "
                                 f"{'—' if static_time is None else f'{static_time:.3f}'} |")
                lines.extend(["", "规划耗时包含候选构造与搜索；静态评分累计秒数仅由新增静态模型单独计时，不把规划耗时误写为纯评分时间。", ""])
                lines.extend(["同一组已审计的 600 秒开发候选上，静态模型与事件 DAG 的排序一致性如下；这不是正式三种子性能指标。", "",
                              "| 评价模型 | 吞吐排序 | TTFT 排序 | TPOT 排序 |",
                              "| --- | ---: | ---: | ---: |"])
                labels = (("静态异构资源模型", diagnostic["static_resource_rank_agreement"]),
                          ("V2 事件 DAG", diagnostic["event_dag_rank_agreement"]))
                for label, values in labels:
                    cells = [values[key] for key in KEYS[:3]]
                    lines.append(f"| {label} | " + " | ".join(
                        "—" if value is None else f"{value:+.3f}" for value in cells) + " |")
                lines.append("")
            if name.startswith("M3"):
                lines.extend(["| 调度方法 | GPU 排队 request-s/到达 | 出站等待 request-s/到达 | 路径种类/种子 |",
                              "| --- | ---: | ---: | --- |"])
                for label, method in options:
                    item = group["methods"][method]
                    if "absolute" not in item:
                        continue
                    routes = "/".join(str(len(row)) for row in item["route_counts_by_seed"])
                    lines.append(f"| {label} | {fmt(item['gpu_queue_per_arrival'], '')} | "
                                 f"{fmt(item['outbound_wait_per_arrival'], '')} | {routes} |")
                lines.append("")
            summary["groups"][scenario][name] = group
    lines.extend(["## 解释边界", "",
                  "M1 的容量替代使用独立的容量规则；静态模型和 V2 使用相同结构搜索流程，但分别完成整轮搜索，非固定候选池内换一次分数。基本合法性检查在三者之间共用。",
                  "M2 三者使用 V2 事件 DAG 评价及在线调度；beam search 的评价上限等于该拓扑 V2 正式搜索的评价数。",
                  "M3 三者使用字节相同的 V2 布局；负载感知完整流水线只能选三条规范完整路径，V2 可使用完整层兼容 DAG。出站等待包含发送端和下游限制。",
                  "外部系统的同负载 V2–Helix，以及共同较低负载的 V2／Helix／Swarm／SP，分别见既有导师主表和四方法共同负载报告，不与本表跨负载相减。",
                  "三个种子只描述配对波动，不作统计显著性或真实集群性能声明。", ""])
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                       encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {HERE / 'RESULTS_CN.md'}")


if __name__ == "__main__":
    main()

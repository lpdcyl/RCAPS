"""Audit and summarize the paired V3/Helix/Swarm/SP common-load windows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

import numpy as np

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.layout import scenario as physical_scenario
from benchmarks.registry import METHODS
from experiments.helix_additional_baselines.summarize_common_low import audit_sp_physical

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "experiments" / "helix_additional_baselines"
LOADS = {"single": 350.0, "multi": 160.0}
SEEDS = (0, 1, 2)
METHODS_IN_TABLE = ("rcaps_v3", "helix", "swarm", "separate")
NAMES = {"rcaps_v3": "RCAPS V3", "helix": "Helix ILP",
         "swarm": "Swarm", "separate": "Separate Pipelines (SP)"}
METRICS = {
    "output_throughput_tokens_per_s": ("输出吞吐 token/s ↑", 1, "higher"),
    "ttft_p95_s": ("P95 TTFT s ↓", 1, "lower"),
    "tpot_p95_s": ("P95 TPOT s ↓", 1, "lower"),
    "completion_fraction": ("完成率 % ↑", 100, "higher"),
    "backlog_at_window_end": ("末端积压 ↓", 1, "lower"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_path(scenario: str, seed: int, method: str) -> Path:
    if method == "rcaps_v3":
        base = HERE / "runs"
    elif scenario == "single":
        base = OLD / "common_low_formal"
    else:
        base = OLD / "common_low_formal_multi"
    return base / scenario / f"seed{seed}" / f"{method}.json"


def checked_record(scenario: str, seed: int, method: str) -> tuple[dict, Path]:
    path = source_path(scenario, seed, method)
    record = json.loads(path.read_text(encoding="utf-8"))
    solution, cluster = METHODS[method].layout(scenario, ROOT)
    expected = {
        "system": method, "scenario": scenario, "seed": seed,
        "offered_tokens_per_s": LOADS[scenario], "duration_s": 1800,
        "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
        "query_samples_schema": 1, "solution_sha256": sha256(solution),
        "sim_cluster_sha256": sha256(cluster),
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f"{path}: unexpected {key}: {record.get(key)!r}")
    if len(record.get("query_samples", {})) != record["arrivals"]:
        raise ValueError(f"{path}: missing query samples")
    if record["backlog_at_window_end"] != record["arrivals"] - sum(
        sample["completed"] for sample in record["query_samples"].values()
    ):
        raise ValueError(f"{path}: backlog and completion disagree")
    return record, path


def summarize(values: list[float]) -> dict:
    return {"mean": mean(values), "sample_sd": stdev(values),
            "by_seed": dict(zip(SEEDS, values))}


def formatted(summary: dict, digits: int = 3) -> str:
    return f"{summary['mean']:.{digits}f} ± {summary['sample_sd']:.{digits}f}"


def unfinished_age(record: dict) -> dict:
    ages = [1800 - sample["arrival_s"] for sample in record["query_samples"].values()
            if not sample["completed"]]
    return {"count": len(ages), "p50_s": float(np.percentile(ages, 50)) if ages else None,
            "p95_s": float(np.percentile(ages, 95)) if ages else None,
            "max_s": max(ages) if ages else None}


def write_ieee_table(report: dict) -> None:
    """Produce the compact two-topology table for an IEEE two-column paper."""
    keys = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")
    lines = [
        r"\begin{table*}[t]", r"\centering", r"\caption{Paired four-method comparison at the common offered loads. Values are mean $\pm$ sample SD over seeds 0/1/2; output throughput is in token/s and P95 latencies are in seconds.}",
        r"\label{tab:v3-four-methods}", r"\scriptsize",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccccc@{}}",
        r"\toprule",
        r" & \multicolumn{3}{c}{Single cluster (350 token/s)} & \multicolumn{3}{c}{Three clusters (160 token/s)} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"Method & Output throughput$\uparrow$ & P95 TTFT$\downarrow$ & P95 TPOT$\downarrow$ & Output throughput$\uparrow$ & P95 TTFT$\downarrow$ & P95 TPOT$\downarrow$ \\",
        r"\midrule",
    ]
    for method in METHODS_IN_TABLE:
        cells = []
        for scenario in LOADS:
            metrics = report["scenarios"][scenario]["methods"][method]["metrics"]
            cells.extend(f"{metrics[key]['mean']:.3f} $\\pm$ {metrics[key]['sample_sd']:.3f}"
                         for key in keys)
        name = r"\textbf{RCAPS V3}" if method == "rcaps_v3" else NAMES[method]
        lines.append(name + " & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular*}",
              r"\end{table*}", ""]
    (HERE / "IEEE_TABLE.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    result = {
        "protocol": {"model": "LLaMa 70B", "gpu_pool": "4 A100 + 8 L4 + 12 T4",
                     "offered_tokens_per_s": LOADS, "seeds": SEEDS,
                     "duration_s": 1800, "warmup_s": 0,
                     "tail_drain": False, "loads_origin": "Helix artifact Swarm setting"},
        "raw_sha256": {}, "sp_gpu_mapping": {}, "scenarios": {},
        "implementation_sha256": {
            path: sha256(ROOT / path) for path in (
                "benchmarks/fixed_window.py", "baselines/helix.py",
                "baselines/swarm.py", "baselines/separate.py",
                "rcaps/v3_method.py", "rcaps/v3/scheduler.py")},
        "physical_config_sha256": {
            scenario: sha256(physical_scenario(scenario)[0]) for scenario in LOADS},
    }
    lines = ["# V3、Helix ILP、Swarm、Separate Pipelines：四方法完整对比", "",
             "70B；同一套 4 A100、8 L4、12 T4 GPU。单集群 350、三集群 160 offered token/s；"
             "种子 0/1/2；1800 秒、零预热、窗口末不排空。"
             "四方法逐种子使用同一请求轨迹。数值为均值 ± 样本标准差。", "",
             "负载在旧 V2 四方法实验前按 Helix artifact 的 Swarm 配置确定。"
             "这组结果与 700/320 token/s 的 V3–Helix 主表属于不同负载，不能直接相减。", ""]
    for scenario in LOADS:
        result["sp_gpu_mapping"][scenario] = audit_sp_physical(scenario)
        rows: dict[str, list[dict]] = {method: [] for method in METHODS_IN_TABLE}
        raw_index: dict[str, dict] = {}
        for seed in SEEDS:
            for method in METHODS_IN_TABLE:
                record, path = checked_record(scenario, seed, method)
                rows[method].append(record)
                relative = path.relative_to(ROOT).as_posix()
                result["raw_sha256"][relative] = sha256(path)
                raw_index[f"seed{seed}/{method}"] = {
                    "path": relative, "sha256": sha256(path),
                    "layout_sha256": record["solution_sha256"],
                    "sim_cluster_sha256": record["sim_cluster_sha256"],
                    "trace_sha256": record["trace_sha256"],
                }
            reference = rows["rcaps_v3"][-1]
            for method in METHODS_IN_TABLE[1:]:
                record = rows[method][-1]
                if any(record.get(field) != reference.get(field) for field in MATCH_FIELDS):
                    raise ValueError(f"{scenario}/seed{seed}/{method}: protocol/trace mismatch")
                common_cohort(record, reference)
        scene = {"raw_index": raw_index, "methods": {}, "v3_vs_baseline": {},
                 "trace_sha256_by_seed": {seed: rows["rcaps_v3"][seed]["trace_sha256"]
                                          for seed in SEEDS}}
        for method, records in rows.items():
            scene["methods"][method] = {
                "metrics": {key: summarize([record[key] * factor for record in records])
                            for key, (_, factor, _) in METRICS.items()},
                "by_seed": {seed: {
                    **{key: record[key] for key in METRICS},
                    "arrivals": record["arrivals"],
                    "unfinished_age_s": unfinished_age(record),
                } for seed, record in zip(SEEDS, records)},
            }
        for method in METHODS_IN_TABLE[1:]:
            gains = {}
            for key, (_, _, direction) in METRICS.items():
                values = []
                for v3, other in zip(rows["rcaps_v3"], rows[method]):
                    if other[key] <= 0:
                        raise ValueError(f"{scenario}/{method}: zero denominator for {key}")
                    values.append(100 * (v3[key] / other[key] - 1 if direction == "higher"
                                         else 1 - v3[key] / other[key]))
                gains[key] = summarize(values)
            scene["v3_vs_baseline"][method] = {
                "paired_improvement_percent": gains,
                "common_cohort_by_seed": [common_cohort(v3, other)
                                          for v3, other in zip(rows["rcaps_v3"], rows[method])],
            }
        result["scenarios"][scenario] = scene
        title = "单集群" if scenario == "single" else "三集群"
        lines += [f"## {title}", "",
                  "| 方法 | " + " | ".join(label for label, _, _ in METRICS.values()) + " |",
                  "| --- |" + " ---: |" * len(METRICS)]
        for method in METHODS_IN_TABLE:
            metrics = scene["methods"][method]["metrics"]
            lines.append("| " + NAMES[method] + " | " + " | ".join(
                formatted(metrics[key], 1 if key == "backlog_at_window_end" else 3)
                for key in METRICS) + " |")
        lines += ["", "V3 相对各方法的逐种子配对改善（%）：", "",
                  "| 对照 | 输出吞吐 ↑ | P95 TTFT ↓ | P95 TPOT ↓ | 完成率 ↑ | 末端积压 ↓ |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for method in METHODS_IN_TABLE[1:]:
            gains = scene["v3_vs_baseline"][method]["paired_improvement_percent"]
            lines.append("| " + NAMES[method] + " | " + " | ".join(
                formatted(gains[key], 2) for key in METRICS) + " |")
        lines += ["", "共同观测请求的配对尾延迟（每种子分别取共同样本 P95，表内为三种子均值）：", "",
                  "| 对照 | 共同完成请求数 | TTFT V3 / 对照 s | TPOT V3 / 对照 s |",
                  "| --- | ---: | ---: | ---: |"]
        for method in METHODS_IN_TABLE[1:]:
            cohorts = scene["v3_vs_baseline"][method]["common_cohort_by_seed"]
            lines.append(f"| {NAMES[method]} | "
                         f"{mean(row['both_completed'] for row in cohorts):.1f} | "
                         f"{mean(row['ttft_s']['main_p95_s'] for row in cohorts):.3f} / "
                         f"{mean(row['ttft_s']['baseline_p95_s'] for row in cohorts):.3f} | "
                         f"{mean(row['tpot_s']['main_p95_s'] for row in cohorts):.3f} / "
                         f"{mean(row['tpot_s']['baseline_p95_s'] for row in cohorts):.3f} |")
        lines += ["", "### 逐种子原始指标", "",
                  "| 种子 | 方法 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 % | 积压 | 未完成请求年龄 P95 s |",
                  "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for seed in SEEDS:
            for method in METHODS_IN_TABLE:
                row = scene["methods"][method]["by_seed"][seed]
                age = row["unfinished_age_s"]["p95_s"]
                lines.append(f"| {seed} | {NAMES[method]} | "
                             f"{row['output_throughput_tokens_per_s']:.3f} | "
                             f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                             f"{row['completion_fraction'] * 100:.2f} | "
                             f"{row['backlog_at_window_end']} | "
                             f"{age:.1f} |" if age is not None else
                             f"| {seed} | {NAMES[method]} | "
                             f"{row['output_throughput_tokens_per_s']:.3f} | "
                             f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                             f"{row['completion_fraction'] * 100:.2f} | "
                             f"{row['backlog_at_window_end']} | — |")
        lines.append("")
    single = result["scenarios"]["single"]["methods"]
    multi = result["scenarios"]["multi"]["methods"]
    s_v3 = single["rcaps_v3"]["metrics"]
    s_sp = single["separate"]["metrics"]
    m_v3 = multi["rcaps_v3"]["metrics"]
    lines += ["## 简要结论", "",
              "- 在这三个配对种子的共同负载下，V3 在两个拓扑的输出吞吐均高于 Helix ILP 和 Swarm，"
              "P95 TTFT、P95 TPOT 也均较低。三集群 V3 的吞吐还高于 SP。",
              f"- 单集群 V3 与 SP 的平均吞吐分别为 "
              f"{s_v3['output_throughput_tokens_per_s']['mean']:.3f} 和 "
              f"{s_sp['output_throughput_tokens_per_s']['mean']:.3f} token/s；"
              "不能声称 V3 在此负载下对 SP 有吞吐优势。"
              f"V3 的 P95 TTFT/TPOT 为 {s_v3['ttft_p95_s']['mean']:.3f}/"
              f"{s_v3['tpot_p95_s']['mean']:.3f} s，低于 SP。",
              f"- 三集群 V3 的平均输出吞吐为 "
              f"{m_v3['output_throughput_tokens_per_s']['mean']:.3f} token/s，"
              "且完成率最高、末端积压最少；这组数据支持完整 V3 系统在该资源池和负载下的竞争力，"
              "不单独归因于 M1 图建模或额外分叉。", "",
              "## 核查与解释边界", "",
              "- V3 使用冻结的 `multi_any` 搜索输出：单集群实际布局为 1→4→3，"
              "三集群退回 1→3；两拓扑均运行相同的在线 M3。Helix 为 ILP 布局，"
              "Swarm 与 SP 保留原 artifact 布局及调度。",
              "- 每个正式窗口核查 1800 秒、零预热、不排空、种子、负载、布局 SHA256 与完整请求样本。"
              "同种子逐请求核对 UID、到达时间及输入/目标输出长度。",
              "- SP 使用原 artifact A100/L4/T4 三个独立流水线布局和 Naive 调度；"
              "请求按原 artifact 的子集群负载比例、仅依据已分配请求数分流。"
              "三个子集群的物理 GPU 合起来恰好覆盖同一 24 GPU 池。",
              "- P95 根据各方法在窗口内观测到的请求计算；完成率、积压和未完成请求年龄"
              "共同提示固定窗口截尾影响。逐种子共同请求的尾延迟在 `summary.json` 中。",
              "- 旧 Helix/Swarm/SP 低负载窗口经协议审计复用；V3 在相同负载新运行。"
              "原始路径及 SHA256 见 `summary.json`。三个种子仅描述波动，不宣称统计显著。", ""]
    (HERE / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    write_ieee_table(result)


if __name__ == "__main__":
    main()

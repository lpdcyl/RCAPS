"""Build an auditable paper ablation of V3 M2 from completed paired windows.

No simulator job is launched. The script verifies raw-window hashes and common
protocol before combining the placement-only crossover with the single-boundary
M2 control. Run: python -m experiments.v3_m2_paper_ablation.make_table
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, stdev

from experiments.m2_multistage_candidate.analysis import common_completed


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CROSS = ROOT / "experiments/v3_method_validation/formal_analysis.json"
CORE = ROOT / "experiments/v3_core_ablations/formal_analysis.json"
CROSS_AUDIT = ROOT / "experiments/v3_method_validation/crossover_audit.json"
CASES = (("single", "C1_single", 700), ("multi", "C1_multi", 320))
METHODS = ("Helix ILP + M3", "Single-boundary M2 + M3", "Full M2 + M3")
METRICS = (
    ("output_throughput_tokens_per_s", "Output token/s", True),
    ("ttft_p95_s", "P95 TTFT (s)", False),
    ("tpot_p95_s", "P95 TPOT (s)", False),
    ("completion_fraction", "Completion", True),
    ("backlog_at_window_end", "Backlog", False),
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_raw(source: dict) -> dict:
    path = ROOT / source["source"]
    if digest(path) != source["sha256"]:
        raise ValueError(f"Raw window hash changed: {path}")
    row = read(path)
    if row["trace_sha256"] != source["trace_sha256"]:
        raise ValueError(f"Trace hash changed: {path}")
    if len(row["query_samples"]) != row["arrivals"]:
        raise ValueError(f"Incomplete request records: {path}")
    return row


def validate_protocol(cross: dict, core: dict, audit: dict, case: str,
                      scenario: str, offered: int, rows: dict) -> None:
    if (cross["protocol"]["duration_s"] != 1800 or
            core["protocol"]["duration_s"] != 1800 or
            cross["protocol"]["warmup_s"] != 0 or
            core["protocol"]["warmup_s"] != 0 or
            cross["protocol"]["tail_drain"] or
            core["protocol"]["tail_drain"] or
            cross["protocol"]["loads"][scenario] != offered or
            core["protocol"]["offered_token_s"][case] != offered):
        raise ValueError("Mismatched formal-window protocol")
    physical = audit["scenarios"][scenario]["v3"]["physical_sha256"]
    expected_solutions = {
        METHODS[0]: audit["scenarios"][scenario]["helix"]["solution_sha256"],
        METHODS[1]: core["audit"]["cases"][case]["layouts"]["single_any"]["solution_sha256"],
        METHODS[2]: audit["scenarios"][scenario]["v3"]["solution_sha256"],
    }
    expected_clusters = {
        METHODS[0]: audit["scenarios"][scenario]["helix"]["sim_cluster_sha256"],
        METHODS[1]: core["audit"]["cases"][case]["layouts"]["single_any"]["sim_cluster_sha256"],
        METHODS[2]: audit["scenarios"][scenario]["v3"]["sim_cluster_sha256"],
    }
    for seed in (0, 1, 2):
        paired = [rows[method][seed] for method in METHODS]
        if len({row["trace_sha256"] for row in paired}) != 1:
            raise ValueError(f"Different request traces: {scenario}/{seed}")
        if len({frozenset(row["query_samples"]) for row in paired}) != 1:
            raise ValueError(f"Different request identities: {scenario}/{seed}")
        for method, row in zip(METHODS, paired):
            if (row["seed"] != seed or row["scenario"] != scenario or
                    row["offered_tokens_per_s"] != offered or
                    row["duration_s"] != 1800 or row["warmup_s"] != 0 or
                    row["evaluation_protocol"] != "fixed_window_no_tail_drain" or
                    row["method"] != "queue_dag" or
                    row["physical_cluster_sha256"] != physical or
                    row["solution_sha256"] != expected_solutions[method] or
                    row["sim_cluster_sha256"] != expected_clusters[method]):
                raise ValueError(f"Window identity differs: {scenario}/{seed}/{method}")
        if (rows[METHODS[0]][seed].get("scheduler") != "m3" or
                rows[METHODS[1]][seed].get("execution_sha256") !=
                rows[METHODS[2]][seed].get("source_execution_sha256")):
            raise ValueError(f"M3 execution identity differs: {scenario}/{seed}")


def aggregate(rows: dict) -> dict:
    return {method: {key: {"mean": mean(row[key] for row in rows[method]),
                           "sd": stdev(row[key] for row in rows[method]),
                           "values": [row[key] for row in rows[method]]}
                     for key, _, _ in METRICS}
            for method in METHODS}


def effects(rows: dict, left: str, right: str) -> dict:
    a, b = rows[left], rows[right]
    return {
        "left": left, "right": right,
        "mean_paired_delta": {key: mean(b[i][key] - a[i][key] for i in range(3))
                              for key, _, _ in METRICS},
        "throughput_relative_percent":
            100 * (mean(row["output_throughput_tokens_per_s"] for row in b) /
                   mean(row["output_throughput_tokens_per_s"] for row in a) - 1),
        "common_completed": [common_completed(a[i], b[i]) for i in range(3)],
    }


def make_summary() -> dict:
    cross, core, audit = read(CROSS), read(CORE), read(CROSS_AUDIT)
    if cross["audit_sha256"] != digest(CROSS_AUDIT) or core["failures"]:
        raise ValueError("Crossover audit changed or core ablation has failures")
    summary = {"sources": {str(CROSS.relative_to(ROOT)): digest(CROSS),
                            str(CORE.relative_to(ROOT)): digest(CORE),
                            str(CROSS_AUDIT.relative_to(ROOT)): digest(CROSS_AUDIT)},
               "protocol": "paired seeds 0/1/2; 1800 s; zero warmup; no tail drain",
               "cases": {}}
    for scenario, case, offered in CASES:
        rows = {method: [] for method in METHODS}
        paths = {method: [] for method in METHODS}
        for seed in (0, 1, 2):
            s = str(seed)
            source = cross["scenarios"][scenario]["seeds"][s]["sources"]
            core_source = core["raw_result_index"][case][s]
            selected = {METHODS[0]: source["HR"],
                        METHODS[1]: core_source["C"],
                        METHODS[2]: source["RR"]}
            if (core_source["D"]["sha256"] != source["RR"]["sha256"] or
                    core_source["D"]["source"] != source["RR"]["source"]):
                raise ValueError(f"V3 reference differs between experiments: {case}/{seed}")
            for method, entry in selected.items():
                row = checked_raw(entry)
                rows[method].append(row)
                paths[method].append({"source": entry["source"], "sha256": entry["sha256"]})
                reference = (cross["scenarios"][scenario]["seeds"][s]["metrics"]["HR"]
                             if method == METHODS[0] else
                             core["paired"][case][s]["metrics"]["C"]
                             if method == METHODS[1] else
                             cross["scenarios"][scenario]["seeds"][s]["metrics"]["RR"])
                for key, _, _ in METRICS:
                    if abs(row[key] - reference[key]) > 1e-10:
                        raise ValueError(f"Analysis and raw metric differ: {case}/{seed}/{method}/{key}")
        validate_protocol(cross, core, audit, case, scenario, offered, rows)
        summary["cases"][case] = {
            "offered_tokens_per_s": offered,
            "aggregate": aggregate(rows),
            "effects": {"M2_vs_Helix": effects(rows, METHODS[0], METHODS[2]),
                        "multistage_vs_single": effects(rows, METHODS[1], METHODS[2])},
            "raw_sources": paths,
            "structure": {
                "single_boundary": core["audit"]["cases"][case]["layouts"]["single_any"]["structure"],
                "full_m2": core["audit"]["cases"][case]["layouts"]["multi_any"]["structure"],
            },
        }
    return summary


def value(stats: dict, key: str) -> str:
    mu, sd = stats[key]["mean"], stats[key]["sd"]
    return f"{mu:.3f} ± {sd:.3f}"


def markdown(summary: dict) -> str:
    lines = [
        "# 可用于论文的 V3 M2 消融（已完成正式窗口）", "",
        "## 设计", "",
        "主对照固定 V3 的层兼容 DAG 执行接口和同一实时 M3，仅替换放置来源：Helix ILP、V3 M2 单边界搜索、完整 V3 M2（最多双边界）。“无 M2”在此具体定义为 Helix ILP 放置，并非空部署。三行使用相同资源池、种子、请求身份和 1800 秒零预热不排空窗口。", "",
        "| 拓扑与负载 | 放置 + 固定 M3 | 输出 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s ↓ | 完成率 ↑ | 末端积压 ↓ |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    labels = {METHODS[0]: "Helix ILP + M3（无 M2）",
              METHODS[1]: "单边界 M2 + M3",
              METHODS[2]: "完整 M2 + M3（V3）"}
    for _, case, offered in CASES:
        name = "单集群" if case == "C1_single" else "三集群"
        for method in METHODS:
            data = summary["cases"][case]["aggregate"][method]
            cells = [value(data, key) for key, _, _ in METRICS]
            lines.append(f"| {name}，{offered} token/s | {labels[method]} | " + " | ".join(cells) + " |")
    lines.extend(["", "均值 ± 样本标准差；种子 0/1/2。", "", "## 配对差值（右侧 − 左侧）", "",
                  "| 拓扑 | 对照 | 吞吐差 token/s | 吞吐相对变化 | P95 TTFT 差 s | P95 TPOT 差 s | 完成率差 | 积压差 |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for _, case, _ in CASES:
        for key, label in (("M2_vs_Helix", "完整 M2 − Helix ILP"),
                           ("multistage_vs_single", "完整 M2 − 单边界 M2")):
            effect = summary["cases"][case]["effects"][key]
            delta = effect["mean_paired_delta"]
            cells = [f"{delta['output_throughput_tokens_per_s']:+.3f}",
                     f"{effect['throughput_relative_percent']:+.2f}%",
                     f"{delta['ttft_p95_s']:+.3f}", f"{delta['tpot_p95_s']:+.3f}",
                     f"{delta['completion_fraction']:+.3f}",
                     f"{delta['backlog_at_window_end']:+.1f}"]
            lines.append(f"| {case} | {label} | " + " | ".join(cells) + " |")
    lines.extend(["", "## 解释", "",
                  "- **M2 作为放置方法有用。** 固定 M3 后，完整 M2 相对 Helix ILP 在两拓扑的三个配对种子中均提高吞吐、完成率，并降低 TTFT、TPOT 与积压。主表只支持所测资源池和负载下的条件收益。",
                  "- **多级结构的增量收益限于单集群。** 单集群完整 M2 相对单边界 M2 的平均吞吐增加 0.604 token/s，TTFT/TPOT 下降 0.283/0.041 s。三集群完整 M2 实际仍选 `1→3` 单边界；两行只反映微观 GPU 放置差异，不能称为多级结构收益。",
                  "- **请求完成集合不同。** 主对照的共同完成请求 P95 仍同向；逐种子共同完成数和 P95 见下表。固定窗口 P95 应连同完成率与积压解释。三个种子描述方向与波动，不作显著性声明。", "",
                  "| 拓扑 | 种子 | 共同完成数 | 共同 P95 TTFT：Helix→M2 s | 共同 P95 TPOT：Helix→M2 s |",
                  "| --- | ---: | ---: | ---: | ---: |"])
    for _, case, _ in CASES:
        cohorts = summary["cases"][case]["effects"]["M2_vs_Helix"]["common_completed"]
        for seed, item in enumerate(cohorts):
            t, p = item["ttft_s"], item["tpot_s"]
            lines.append(f"| {case} | {seed} | {item['count']} | {t['left_p95_s']:.3f}→{t['right_p95_s']:.3f} | {p['left_p95_s']:.3f}→{p['right_p95_s']:.3f} |")
    lines.extend(["", "## 论文可采用的表述", "",
                  "在固定层兼容 DAG 构建规则和同一实时 M3 调度器后，将 Helix ILP 放置替换为完整 M2 放置，在 C1 单集群和三集群的相同到达轨迹上，平均输出吞吐分别提高 4.76% 和 9.32%，P95 TTFT 分别降低 2.222 s 和 5.090 s。单集群的第二边界带来较小的额外收益；三集群搜索回退为单边界，不支持多级结构在该拓扑上有效的主张。", "",
                  "**English draft.** Holding the layer-compatible DAG construction rule and the online M3 scheduler fixed, replacing the Helix ILP placement with M2 increases mean output throughput by 4.76% and 9.32% in the single- and three-cluster settings, respectively. The corresponding P95 TTFT decreases by 2.222 s and 5.090 s. The additional boundary yields a smaller gain in the single-cluster setting; in the three-cluster setting, the full search selects a single-boundary layout, so its marginal difference cannot be attributed to multistage replication. These are paired three-seed simulator results, not a statistical significance claim.", "",
                  "## 复现与来源", "",
                  "运行 `python -m experiments.v3_m2_paper_ablation.make_table`。生成器逐个核验原始 JSON 的 SHA256、物理配置、布局、窗口协议、请求身份及汇总数值。原始路径和哈希保存在 `summary.json`。此文件只汇总已完成的正式仿真，没有新跑窗口。", ""])
    return "\n".join(lines)


def latex(summary: dict) -> str:
    lines = [r"\begin{table*}[t]",
             r"\caption{M2 placement ablation with the same layer-compatible DAG construction rule and live M3 scheduler.}",
             r"\label{tab:v3-m2-ablation}", r"\centering", r"\scriptsize",
             r"\setlength{\tabcolsep}{3pt}",
             r"\begin{tabular}{@{}llccccc@{}}", r"\toprule",
             r"Pool & Placement + M3 & Output token/s $\uparrow$ & P95 TTFT (s) $\downarrow$ & P95 TPOT (s) $\downarrow$ & Completion $\uparrow$ & Backlog $\downarrow$ \\",
             r"\midrule"]
    labels = {METHODS[0]: "Helix ILP (no M2)",
              METHODS[1]: "Single-boundary M2",
              METHODS[2]: "Full M2 (V3)"}
    for index, (_, case, offered) in enumerate(CASES):
        pool = f"{'Single cluster' if case == 'C1_single' else 'Three clusters'} ({offered})"
        if index:
            lines.append(r"\midrule")
        for method in METHODS:
            data = summary["cases"][case]["aggregate"][method]
            cells = []
            for key, _, _ in METRICS:
                mu, sd = data[key]["mean"], data[key]["sd"]
                cells.append(f"{mu:.3f} $\\pm$ {sd:.3f}")
            lines.append(" & ".join([pool if method == METHODS[0] else "",
                                     labels[method], *cells]) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\vspace{2pt}",
                  r"\parbox{\textwidth}{\scriptsize Mean $\pm$ sample standard deviation over paired seeds 0--2. "
                  r"All windows last 1800 s with zero warmup and no tail drain. Single/three-cluster offered loads "
                  r"are 700/320 token/s. The three-cluster full M2 deployment retains one boundary, so its "
                  r"difference from single-boundary M2 is micro-placement, not an added stage.}",
                  r"\end{table*}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    summary = make_summary()
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text(markdown(summary), encoding="utf-8")
    block = latex(summary)
    (HERE / "m2_ablation_table.tex").write_text(block, encoding="utf-8")
    preview = (r"\documentclass[twocolumn]{article}" + "\n" +
               r"\usepackage{booktabs}" + "\n" +
               r"\setlength{\textwidth}{7.16in}" + "\n" +
               r"\setlength{\columnsep}{0.24in}" + "\n" +
               r"\begin{document}" + "\n" + block + r"\end{document}" + "\n")
    (HERE / "m2_ablation_preview.tex").write_text(preview, encoding="utf-8")
    print(HERE / "RESULTS_CN.md")
    print(HERE / "m2_ablation_table.tex")


if __name__ == "__main__":
    main()

"""Summarize offline and paired online V3 M2 search sensitivity results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, stdev

from experiments.v3_release.verify import digest

from .plan import CASES, HERE, ROOT, SETTINGS, label, write_json
from .run import LOADS, SEEDS, audit


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")
SHORT = ("吞吐 token/s", "P95 TTFT s", "P95 TPOT s", "完成率", "积压")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(values: list[float], digits: int = 3) -> str:
    if len(values) != len(SEEDS):
        return f"不完整 {len(values)}/{len(SEEDS)}"
    return f"{mean(values):.{digits}f} ± {stdev(values):.{digits}f}"


def rows_for(index: dict, case: str, canonical: str, load: int) -> dict[int, dict]:
    records = {}
    for seed in SEEDS:
        key = f"{case}/{canonical}/{load}/seed{seed}"
        item = index["jobs"].get(key)
        if not item or item["status"] not in ("passed", "reused"):
            continue
        source = ROOT / item["source"]
        if digest(source) != item["sha256"]:
            raise ValueError(f"Raw result changed: {source}")
        row = read_json(source)
        if row["trace_sha256"] != item["trace_sha256"] or \
                len(row["query_samples"]) != row["arrivals"]:
            raise ValueError(f"Trace or request samples invalid: {source}")
        records[seed] = row
    return records


def render() -> None:
    protocol = audit()
    saved_audit = HERE / "audit.json"
    if read_json(saved_audit) != json.loads(json.dumps(protocol)):
        raise ValueError("Audit changed since online execution")
    planning = read_json(HERE / "planning_index.json")
    index = read_json(HERE / "formal_index.json")
    if index["audit_sha256"] != digest(saved_audit):
        raise ValueError("Formal run index refers to another audit")
    by_group = {}
    for case in CASES:
        by_group[case] = {name: group["canonical"]
                          for group in protocol["groups"][case]
                          for name in group["aliases"]}
    offline = []
    online = []
    paired = []
    lines = ["# V3 M2 搜索参数敏感性", "",
             "本实验比较固定 `multi_any` 搜索中 Beam 宽度与每阶段评分预算。",
             "预算为上限；表中评分数是实际调用静态评价器的不同候选数。",
             "目标分数越低越好。‘已测最优差距’只相对于本次六组设置中的最低分。", ""]
    for case in CASES:
        variants = planning["cases"][case]
        best = min(variants[label(*setting)]["score"] for setting in SETTINGS)
        baseline = variants[label(64, 500)]
        lines.extend([f"## {case}", "",
                      "| Beam | 每阶段预算 | 结构宽度 | 边界 | 已测最优差距 | 共享评分 | 多级扩展评分 | 总评分 | 规划秒 | 布局 |",
                      "| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"])
        for beam, budget in SETTINGS:
            setting = label(beam, budget)
            item = variants[setting]
            gap = (item["score"] - best) / best * 100
            same = (item["solution_sha256"] == baseline["solution_sha256"] and
                    item["sim_cluster_sha256"] == baseline["sim_cluster_sha256"])
            offline.append({"case": case, "setting": setting, "beam": beam,
                            "budget": budget, "score": item["score"],
                            "best_observed_score": best, "observed_gap_percent": gap,
                            "same_as_default": same, "widths": item["widths"],
                            "boundaries": item["boundaries"],
                            "layer_copies": item["layer_copies"],
                            "active_gpus": item["active_gpus"],
                            "common_evaluations": item["common_evaluations"],
                            "additional_evaluations": item["additional_evaluations"],
                            "candidate_evaluations": item["candidate_evaluations"],
                            "search_wall_s": item["search_wall_s"],
                            "metrics": item["metrics"],
                            "canonical": by_group[case][setting],
                            "solution_sha256": item["solution_sha256"],
                            "sim_cluster_sha256": item["sim_cluster_sha256"]})
            lines.append(f"| {beam} | {budget} | {item['widths']} | {item['boundaries']} | "
                         f"{gap:.3f}% | {item['common_evaluations']} | "
                         f"{item['additional_evaluations']} | "
                         f"{item['candidate_evaluations']} | {item['search_wall_s']:.2f} | "
                         f"{'同默认' if same else by_group[case][setting]} |")
        unique = len(protocol["groups"][case])
        lines.extend(["", f"本池六组参数产生 **{unique}** 个不同部署文件组合。", "",
                      "| offered token/s | 参数 | 吞吐 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 末端积压 |",
                      "| ---: | --- | ---: | ---: | ---: | ---: | ---: |"])
        for load in LOADS[case]:
            baseline_records = rows_for(index, case, by_group[case][label(64, 500)], load)
            for beam, budget in SETTINGS:
                setting = label(beam, budget)
                canonical = by_group[case][setting]
                records = rows_for(index, case, canonical, load)
                values = {metric: [records[s][metric] for s in SEEDS if s in records]
                          for metric in METRICS}
                online.append({"case": case, "load": load, "setting": setting,
                               "canonical": canonical, "n_seeds": len(records),
                               "per_seed": {str(s): {"source": index["jobs"][f"{case}/{canonical}/{load}/seed{s}"]["source"],
                                                     "sha256": index["jobs"][f"{case}/{canonical}/{load}/seed{s}"]["sha256"],
                                                     "trace_sha256": records[s]["trace_sha256"],
                                                     **{m: records[s][m] for m in METRICS}}
                                            for s in records},
                               "mean": {m: mean(v) if v else None for m, v in values.items()},
                               "sd": {m: stdev(v) if len(v) > 1 else None for m, v in values.items()}})
                lines.append(f"| {load} | {setting} | " + " | ".join(
                    fmt(values[metric]) for metric in METRICS) + " |")
                for seed in SEEDS:
                    if seed not in records or seed not in baseline_records:
                        continue
                    if records[seed]["trace_sha256"] != baseline_records[seed]["trace_sha256"]:
                        raise ValueError(f"Paired trace mismatch: {case}/{load}/seed{seed}/{setting}")
                    paired.append({"case": case, "load": load, "setting": setting,
                                   "seed": seed,
                                   **{m: records[seed][m] - baseline_records[seed][m]
                                      for m in METRICS}})
        lines.append("")
    lines.extend(["## 与默认 64／500 的逐种子配对差值", "",
                  "正值表示该指标高于默认设置；吞吐为正有利，延迟为正不利。", "",
                  "| 拓扑 | 负载 | 设置 | Δ吞吐 token/s | ΔP95 TTFT s | ΔP95 TPOT s |",
                  "| --- | ---: | --- | ---: | ---: | ---: |"])
    for case in CASES:
        for load in LOADS[case]:
            for beam, budget in SETTINGS:
                setting = label(beam, budget)
                subset = [item for item in paired if item["case"] == case and
                          item["load"] == load and item["setting"] == setting]
                values = ([item[metric] for item in subset] for metric in METRICS[:3])
                lines.append(f"| {case} | {load} | {setting} | " +
                             " | ".join(fmt(value) for value in values) + " |")
    failed = [(key, item) for key, item in index["jobs"].items()
              if item["status"] not in ("passed", "reused")]
    lines.extend(["## 解释边界", "",
                  "相同部署哈希表示布局完全相同；不同布局需看同负载、同种子的在线差值。",
                  "更大的评分预算可能改善静态代理分数，也可能使在线指标退化。",
                  "本实验不遍历全部可行布局，不能提供全局最优性保证。",
                  "三个种子只描述波动，不用于统计显著性推断。", "",
                  f"正式失败／缺失窗口：{len(failed)}。失败详情保留于 `formal_index.json`。", ""])
    write_json(HERE / "analysis.json", {"offline": offline, "online": online,
                                         "paired_delta_vs_default": paired,
                                         "failed": failed})
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    csv_path = HERE / "paired_seed_deltas.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case", "load", "setting", "seed", *METRICS))
        writer.writeheader()
        writer.writerows(paired)
    plots(offline, online)
    print(HERE / "RESULTS_CN.md")


def plots(offline: list[dict], online: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [label(*setting) for setting in SETTINGS]
    ticks = [f"{beam}/{budget}" for beam, budget in SETTINGS]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex="col")
    for col, case in enumerate(CASES):
        points = {row["setting"]: row for row in offline if row["case"] == case}
        axes[0, col].plot(range(len(names)),
                          [points[name]["score"] for name in names], "o")
        axes[0, col].set_title(case)
        axes[0, col].set_ylabel("Static objective (lower is better)")
        axes[1, col].plot(range(len(names)),
                          [points[name]["candidate_evaluations"] for name in names],
                          "s", color="tab:orange", label="Evaluations")
        axes[1, col].set_ylabel("Actual candidate evaluations")
        axes[1, col].set_xticks(range(len(names)), ticks, rotation=40, ha="right")
        axes[1, col].set_xlabel("Beam / per-stage budget")
        for row in axes[:, col]:
            row.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(HERE / "offline_sensitivity.png", dpi=180)
    plt.close(fig)

    lookup = {(row["case"], row["load"], row["setting"]): row for row in online}
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex="col")
    selected = (("output_throughput_tokens_per_s", "Throughput", "tab:blue"),
                ("ttft_p95_s", "P95 TTFT", "tab:orange"),
                ("tpot_p95_s", "P95 TPOT", "tab:green"))
    for row_index, case in enumerate(CASES):
        for col, load in enumerate(LOADS[case]):
            ax = axes[row_index, col]
            baseline = lookup[case, load, label(64, 500)]["mean"]
            for metric, title, color in selected:
                denominator = baseline[metric]
                ratios = []
                for name in names:
                    item = lookup[case, load, name]
                    value = item["mean"][metric] if item["n_seeds"] == len(SEEDS) else None
                    ratios.append(value / denominator if value is not None and denominator else float("nan"))
                ax.plot(range(len(names)), ratios, "o", label=title, color=color)
            ax.axhline(1, color="gray", lw=1, ls="--")
            ax.set_title(f"{case}, offered {load} token/s")
            ax.set_ylabel("Ratio to default 64/500")
            ax.set_xticks(range(len(names)), ticks, rotation=40, ha="right")
            ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "online_sensitivity.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    render()

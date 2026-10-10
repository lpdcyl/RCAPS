"""Validate paired multi-seed runs and write a per-seed paper result report."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev

from scipy.stats import spearmanr

from experiments.critical_graph.model_audit import state_from_placement
from experiments.critical_graph.partition import scenario as graph_scenario
from experiments.critical_graph.path_ensemble import measure as ensemble_measure
from experiments.critical_graph.topology import TopologyModel
from experiments.multiseed.run import GUROBI_VERSION, HERE, ROOT, RUNS, jobs, layout_files


SEEDS = (0, 1, 2)
SCENARIOS = ("single", "multi")
SCENARIO_LABELS = {"single": "单集群", "multi": "三集群"}
METRICS = {
    "output_throughput_tokens_per_s": ("输出吞吐 token/s", True),
    "ttft_p95_s": ("P95 TTFT s", False),
    "tpot_p95_s": ("P95 TPOT s", False),
    "completion_fraction": ("完成率", True),
    "backlog_at_window_end": ("窗口末积压", False),
    "paper_prompt_request_p95_s": ("官方口径 P95 prompt s", False),
    "paper_decode_request_p95_s": ("官方口径 P95 decode s", False),
}
PAIRS = {
    "paper": ("paper_helix", "paper_integrated", "官方负载：完整系统"),
    "dev": ("dev_helix", "dev_integrated", "开发负载：完整系统"),
    "placement": ("dev_placement_helix_layout", "dev_placement_final_layout",
                  "固定早期 DAG 调度：放置归因"),
    "scheduler": ("dev_scheduler_helix", "dev_integrated",
                  "固定最终放置：调度归因"),
    "ablation": ("dev_ablation_before", "dev_placement_final_layout",
                 "放置内部消融"),
    "model_move": ("model_before", "model_after", "建模代理方向检查"),
    "scheduler_serial": ("dev_scheduler_serial", "dev_integrated",
                         "调度内部消融：串行传输与最终版本"),
    "scheduler_coalesced": ("dev_scheduler_coalesced", "dev_integrated",
                            "三集群调度内部消融：合并传输与最终版本"),
}
PAIR_SCENARIOS = {"scheduler_coalesced": ("multi",)}


def load(seed: int, scenario: str, name: str) -> dict:
    path = RUNS / f"seed{seed}" / scenario / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def improvement(old: float, new: float, higher: bool) -> float:
    if old == 0:
        raise ValueError("Cannot compute relative change from zero baseline")
    return (new / old - 1 if higher else 1 - new / old) * 100


def summarize(values: list[float]) -> dict:
    return {"mean": mean(values), "sample_sd": stdev(values),
            "min": min(values), "max": max(values),
            "positive_seeds": sum(value > 0 for value in values)}


def validate_all() -> None:
    expected = jobs(list(SEEDS), list(SCENARIOS),
                    ["paper", "dev", "model", "model_refined",
                     "scheduler_ablation"])
    missing = [str(job.output.relative_to(HERE)) for job in expected
               if not job.output.is_file()]
    if missing:
        raise FileNotFoundError(f"Incomplete: {len(missing)}/{len(expected)} runs missing; "
                                + ", ".join(missing[:8]))
    runtime_versions: set[tuple[str, str, str]] = set()
    for job in expected:
        data = load(job.seed, job.scenario, job.name)
        runtime_versions.add((data["python_version"], data["numpy_version"],
                              data["gurobi_version"]))
        for field, value in (("seed", job.seed), ("scenario", job.scenario),
                             ("method", job.method),
                             ("offered_tokens_per_s", job.offered),
                             ("duration_s", job.duration),
                             ("warmup_s", job.warmup)):
            if data[field] != value:
                raise ValueError(f"{job.output}: unexpected {field}: {data[field]}")
        if data.get("gurobi_version") != GUROBI_VERSION:
            raise ValueError(f"{job.output}: expected Gurobi {GUROBI_VERSION}")
        solution, cluster = layout_files(job)
        if Path(data["solution"]).resolve() != solution.resolve():
            raise ValueError(f"{job.output}: wrong placement file")
        if Path(data["sim_cluster"]).resolve() != cluster.resolve():
            raise ValueError(f"{job.output}: wrong simulation cluster file")
        if data["evaluation_protocol"] != "fixed_window_no_tail_drain":
            raise ValueError(f"{job.output}: wrong evaluation protocol")
        if job.method == "queue_dag" and data.get("routing_policy") != job.policy:
            raise ValueError(f"{job.output}: wrong scheduler variant")
    if len(runtime_versions) != 1:
        raise ValueError(f"Mixed Python/NumPy/Gurobi environments: {runtime_versions}")


def pair_data(pair_name: str, scenario: str, seed: int) -> dict:
    old_name, new_name, _ = PAIRS[pair_name]
    old = load(seed, scenario, old_name)
    new = load(seed, scenario, new_name)
    fields = ("scenario", "seed", "offered_tokens_per_s", "duration_s",
              "warmup_s", "evaluation_protocol", "python_version",
              "numpy_version", "gurobi_version", "trace_sha256", "arrivals")
    for field in fields:
        if old[field] != new[field]:
            raise ValueError(f"{pair_name}/{scenario}/seed{seed}: mismatched {field}")
    metrics = {}
    for key, (label, higher) in METRICS.items():
        before, after = old[key], new[key]
        if before is None or after is None:
            raise ValueError(f"{pair_name}/{scenario}/seed{seed}: missing {key}")
        metrics[key] = {"label": label, "before": before, "after": after,
                        "improvement_percent": improvement(before, after, higher)}
    return {"seed": seed, "scenario": scenario, "pair": pair_name,
            "arrivals": old["arrivals"], "trace_sha256": old["trace_sha256"],
            "python_version": old["python_version"],
            "numpy_version": old["numpy_version"],
            "gurobi_version": old["gurobi_version"],
            "ttft_samples": [old["first_tokens_in_window"],
                             new["first_tokens_in_window"]],
            "tpot_samples": [old["queries_with_tpot_samples"],
                             new["queries_with_tpot_samples"]],
            "metrics": metrics,
            "raw": {"before": str((RUNS / f"seed{seed}" / scenario /
                                     f"{old_name}.json").relative_to(HERE)),
                    "after": str((RUNS / f"seed{seed}" / scenario /
                                    f"{new_name}.json").relative_to(HERE))}}


def model_data(scenario: str, seed: int) -> dict:
    from experiments.critical_graph.resource_audit import top_keys

    model = TopologyModel(graph_scenario(scenario)[0])
    canonical_dir = ROOT / "experiments/critical_graph/runs" / (
        "single" if scenario == "single" else "multi")
    state = state_from_placement(canonical_dir / "placement.json")
    profile = load(seed, scenario, "model_profile" if scenario == "single"
                   else "model_profile_refined")
    actual = {int(label.split("-")[1]) - 2: value
              for label, value in profile["gpu_busy_fraction"].items()}
    canonical = {node: 0.0 for node in model.types}
    for path in state["paths"]:
        for stage in model._stages(state, path):
            if stage["device"] != "sink":
                canonical[int(stage["device"])] += 0.5 * max(
                    stage["prefill_s"] / model.prompt_tokens,
                    stage["decode_s"] / model.decode_batch)
    ensemble = ensemble_measure(model, state).gpu_demand_s
    keys = sorted(canonical)
    def rank(values: dict[int, float]) -> float:
        return float(spearmanr([values[k] for k in keys],
                               [actual[k] for k in keys]).statistic)
    result = {"seed": seed, "scenario": scenario,
              "canonical_spearman": rank(canonical),
              "ensemble_spearman": rank(ensemble),
              "canonical_top5_overlap": len(set(top_keys(canonical)) & set(top_keys(actual))),
              "ensemble_top5_overlap": len(set(top_keys(ensemble)) & set(top_keys(actual)))}
    dirs = (("single", "single_sharedpush") if scenario == "single" else
            ("multi_coarse", "multi"))
    before = model.measure(state_from_placement(
        ROOT / "experiments/critical_graph/runs" / dirs[0] / "placement.json"),
        demand_mode="canonical")
    after = model.measure(state_from_placement(
        ROOT / "experiments/critical_graph/runs" / dirs[1] / "placement.json"),
        demand_mode="canonical")
    observed = pair_data("model_move", scenario, seed)["metrics"]
    result["model_move"] = {
        "ttft_proxy_change_percent": (after.ttft_s / before.ttft_s - 1) * 100,
        "tpot_proxy_change_percent": (after.tpot_s / before.tpot_s - 1) * 100,
        "bottleneck_proxy_change_percent":
            (after.bottleneck_s / before.bottleneck_s - 1) * 100,
        "observed_ttft_change_percent": -observed["ttft_p95_s"]["improvement_percent"],
        "observed_tpot_change_percent": -observed["tpot_p95_s"]["improvement_percent"],
        "observed_throughput_change_percent":
            observed["output_throughput_tokens_per_s"]["improvement_percent"],
    }
    return result


def fmt(value: float) -> str:
    return f"{value:.3f}"


def make_markdown(report: dict) -> str:
    paper_single = report["summary"]["paper"]["single"]
    paper_multi = report["summary"]["paper"]["multi"]
    scheduler_multi = report["summary"]["scheduler"]["multi"]
    def effect(summary: dict, key: str) -> str:
        value = summary[key]
        return f"{value['mean']:.2f}±{value['sample_sd']:.2f}%"
    lines = ["# 三种子实验结果", "",
             f"独立运行种子 0、1、2，统一使用 Gurobi {GUROBI_VERSION}；"
             "每个场景和种子的成对方法使用相同请求轨迹。",
             "共完成 78 次仿真。主实验测量窗口为 1800 秒；官方负载为 700/320 token/s、无预热，"
             "开发负载为 400/160 token/s、预热 180 秒。", "",
             "表中 Δ：吞吐为增加百分比，延迟与积压为降低百分比；正数表示改善。"
             "均值±样本标准差基于三个逐种子相对变化，不能当作置信区间。", "",
             "## 主要发现", "",
             f"- 官方负载完整系统对照：单集群吞吐增加 {effect(paper_single, 'output_throughput_tokens_per_s')}，"
             f"TTFT 降低 {effect(paper_single, 'ttft_p95_s')}，"
             f"TPOT 降低 {effect(paper_single, 'tpot_p95_s')}；"
             f"三集群分别为 {effect(paper_multi, 'output_throughput_tokens_per_s')}、"
             f"{effect(paper_multi, 'ttft_p95_s')}、{effect(paper_multi, 'tpot_p95_s')}。"
             "六组场景与指标均在 3/3 种子改善。",
             "- 固定早期 DAG 调度后的放置归因：两场景的吞吐、TTFT、TPOT 均在 3/3 种子改善。",
             f"- 固定最终放置后的调度归因：三集群吞吐增加 "
             f"{effect(scheduler_multi, 'output_throughput_tokens_per_s')}、"
             f"TPOT 降低 {effect(scheduler_multi, 'tpot_p95_s')}，但 TTFT 的降低幅度为"
             f" {effect(scheduler_multi, 'ttft_p95_s')}（平均变慢），仅 1/3 种子改善。"
             "因此不能声称三集群调度本身同时改善三项指标。", ""]
    for pair_name, (_, _, title) in PAIRS.items():
        if pair_name == "model_move":
            continue
        lines += [f"## {title}", "",
                  "| 场景 | 种子 | 到达请求 | 基线吞吐 | 方法吞吐 | Δ吞吐 | "
                  "基线 TTFT | 方法 TTFT | ΔTTFT | 基线 TPOT | 方法 TPOT | ΔTPOT |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for scenario in PAIR_SCENARIOS.get(pair_name, SCENARIOS):
            rows = report["pairs"][pair_name][scenario]
            for item in rows:
                metrics = item["metrics"]
                throughput = metrics["output_throughput_tokens_per_s"]
                ttft = metrics["ttft_p95_s"]
                tpot = metrics["tpot_p95_s"]
                lines.append("| " + " | ".join((SCENARIO_LABELS[scenario], str(item["seed"]),
                    str(item["arrivals"]), fmt(throughput["before"]),
                    fmt(throughput["after"]), fmt(throughput["improvement_percent"]) + "%",
                    fmt(ttft["before"]), fmt(ttft["after"]),
                    fmt(ttft["improvement_percent"]) + "%", fmt(tpot["before"]),
                    fmt(tpot["after"]), fmt(tpot["improvement_percent"]) + "%")) + " |")
            summary = report["summary"][pair_name][scenario]
            def summary_cell(key: str) -> str:
                s = summary[key]
                return f"{fmt(s['mean'])}±{fmt(s['sample_sd'])}% ({s['positive_seeds']}/3)"
            lines.append("| " + " | ".join((SCENARIO_LABELS[scenario], "均值±SD", "—", "—", "—",
                summary_cell("output_throughput_tokens_per_s"), "—", "—",
                summary_cell("ttft_p95_s"), "—", "—",
                summary_cell("tpot_p95_s"))) + " |")
        lines += ["", "其他指标（完成率、积压、官方口径请求延迟）的逐种子原值及变化见 "
                  "[summary.json](summary.json)。", ""]
    lines += ["## 建模解释性验证", "",
              "资源画像窗口为预热 60 秒后的 240 秒；Spearman 比较模型预测和实际 GPU 忙碌排名。",
              "路径集合模型的排名改善属于解释性证据，不代表绝对延迟预测准确。", "",
              "| 场景 | 种子 | 典型路径 Spearman | 路径集合 Spearman | "
              "典型路径 Top-5 | 路径集合 Top-5 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for scenario in SCENARIOS:
        for item in report["model"][scenario]:
            lines.append(f"| {SCENARIO_LABELS[scenario]} | {item['seed']} | "
                         f"{fmt(item['canonical_spearman'])} | "
                         f"{fmt(item['ensemble_spearman'])} | "
                         f"{item['canonical_top5_overlap']}/5 | "
                         f"{item['ensemble_top5_overlap']}/5 |")
    lines += ["", "离线代理与 420 秒放置移动的逐种子方向、全部原始 JSON 路径见 "
              "[summary.json](summary.json)。每次运行的日志与 JSON 同目录、同名。",
              "", "## 结果边界", "",
              "三个种子用于检查运行波动；最终放置和调度曾依据种子 1 的开发实验确定，"
              "因此种子 1 不是独立测试集。本实验只在 Helix 事件仿真器验证，未测量真实 GPU。", ""]
    return "\n".join(lines)


def main() -> None:
    validate_all()
    report: dict = {"seeds": list(SEEDS), "scenarios": list(SCENARIOS),
                    "pairs": {}, "summary": {}, "model": {}}
    for pair_name in PAIRS:
        report["pairs"][pair_name] = {}
        report["summary"][pair_name] = {}
        for scenario in PAIR_SCENARIOS.get(pair_name, SCENARIOS):
            rows = [pair_data(pair_name, scenario, seed) for seed in SEEDS]
            report["pairs"][pair_name][scenario] = rows
            report["summary"][pair_name][scenario] = {
                key: summarize([row["metrics"][key]["improvement_percent"] for row in rows])
                for key in METRICS}
    for scenario in SCENARIOS:
        report["model"][scenario] = [model_data(scenario, seed) for seed in SEEDS]
    (HERE / "summary.json").write_text(json.dumps(report, indent=2) + "\n",
                                       encoding="utf-8")
    (HERE / "RESULTS.md").write_text(make_markdown(report), encoding="utf-8")
    print(f"Validated {len(jobs(list(SEEDS), list(SCENARIOS), ['paper', 'dev', 'model', 'model_refined', 'scheduler_ablation']))} "
          f"runs; wrote {HERE / 'RESULTS.md'}")


if __name__ == "__main__":
    main()

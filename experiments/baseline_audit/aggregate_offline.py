"""Validate and summarize the three-seed 600-second offline experiment."""

from __future__ import annotations

import json
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs_dynamic"
SEEDS = (0, 1, 2)
SCENARIOS = ("single", "multi")
METHODS = ("helix", "integrated")
OFFICIAL_ARTIFACT = {"single": 252.1, "multi": 98.0}
PAPER_FIGURE = {"single": 248.0, "multi": 100.0}


def load(scenario: str, method: str, seed: int) -> dict:
    path = RUNS / f"seed{seed}" / f"{scenario}_{method}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (data["scenario"], data["method"], data["seed"]) == (
        scenario, method, seed), path
    assert (data["warmup_s"], data["measurement_s"]) == (60, 600), path
    assert data["workload"] == "offline_kv_guided", path
    assert data["gurobi_version"].startswith("13."), path
    assert data["decode_request_count"] > 0, path
    assert data["decode_throughput_tokens_per_s"] == (
        data["decode_request_count"] / 600), path
    assert data["solution_sha256"] and data["sim_cluster_sha256"], path
    return data


def main() -> None:
    records = {(scenario, method, seed): load(scenario, method, seed)
               for scenario in SCENARIOS for method in METHODS for seed in SEEDS}
    for scenario in SCENARIOS:
        observed = records[scenario, "helix", 0]["decode_throughput_tokens_per_s"]
        assert abs(observed - OFFICIAL_ARTIFACT[scenario]) < 0.11, (
            scenario, observed, OFFICIAL_ARTIFACT[scenario])
        for method in METHODS:
            assert len({records[scenario, method, seed]["solution_sha256"]
                        for seed in SEEDS}) == 1
            assert len({records[scenario, method, seed]["sim_cluster_sha256"]
                        for seed in SEEDS}) == 1

    rows = []
    summary = {}
    for scenario in SCENARIOS:
        gains = []
        for seed in SEEDS:
            helix = records[scenario, "helix", seed]
            graph = records[scenario, "integrated", seed]
            baseline = helix["decode_throughput_tokens_per_s"]
            candidate = graph["decode_throughput_tokens_per_s"]
            gain = 100 * (candidate / baseline - 1)
            gains.append(gain)
            rows.append((scenario, seed, baseline, candidate, gain,
                         helix["peak_inflight"], graph["peak_inflight"],
                         helix["decode_request_count"],
                         graph["decode_request_count"]))
        summary[scenario] = {
            "mean_relative_gain_percent": statistics.mean(gains),
            "sample_sd_relative_gain_percent": statistics.stdev(gains),
            "improved_seeds": sum(gain > 0 for gain in gains),
        }

    lines = [
        "# 离线负载三种子实验结果",
        "",
        "LLaMA-70B、24 GPU；种子 0/1/2；Gurobi 13；60 s 预热 + 600 s 测量。",
        "吞吐按 Helix 论文的离线口径计算：测量窗口内完成的 decode token 数 / 600 s。",
        "",
        "## 准入规则和可比性",
        "",
        "Helix 使用原始 `OfflineRequestFeeder` 的动态准入：初始 20 个请求，",
        "预计 KV 瓶颈利用率不超过 0.8 时继续投入请求；没有固定并发上限。",
        "新方法同样初始投入 20 个请求，并在每次 prompt 或最后一个 decode 完成时，",
        "依据自身已分配路径估算各层 KV 需求；长度估计同 Helix，采用输入长度加数据集平均输出长度，",
        "尚未分配路径的 prompt 暂按覆盖所有层计入需求。最大层利用率不超过 0.8 时投入新请求。",
        "两者使用同一个 Azure 长度采样器及相同种子；由于准入速率随方法变化，",
        "测量窗口内投入的请求数量可以不同。准入估计方式不同，",
        "因此此表是两个端到端系统在各自动态准入下的比较，不是纯粹固定请求集合上的调度消融。",
        "固定并发 20/80 的早期诊断结果已排除，不作为基线或论文主结果。",
        "",
        "## 官方基线复现",
        "",
        "| 场景 | 官方 artifact 离线 | 本地 Helix 种子 0 | 论文图示离线仿真 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for scenario in SCENARIOS:
        observed = records[scenario, "helix", 0]["decode_throughput_tokens_per_s"]
        lines.append(f"| {scenario} | {OFFICIAL_ARTIFACT[scenario]:.1f} | "
                     f"{observed:.1f} | {PAPER_FIGURE[scenario]:.0f} |")
    lines += [
        "",
        "## 完整窗口结果",
        "",
        "| 场景 | 种子 | Helix token/s | 新方法 token/s | 相对变化 | Helix 峰值在途 | 新方法峰值在途 | Helix decode 数 | 新方法 decode 数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scenario, seed, baseline, candidate, gain, helix_peak, graph_peak, helix_count, graph_count in rows:
        lines.append(f"| {scenario} | {seed} | {baseline:.3f} | {candidate:.3f} | "
                     f"{gain:+.2f}% | {helix_peak} | {graph_peak} | "
                     f"{helix_count} | {graph_count} |")
    lines += ["", "## 种子汇总", ""]
    for scenario in SCENARIOS:
        s = summary[scenario]
        lines.append(f"- {scenario}：相对吞吐变化 "
                     f"{s['mean_relative_gain_percent']:+.2f}% ± "
                     f"{s['sample_sd_relative_gain_percent']:.2f}%（样本标准差），"
                     f"{s['improved_seeds']}/3 个种子改善。")
    lines += [
        "",
        "各运行的原始 JSON 与日志位于 `runs_dynamic/seed*/`。",
        "离线吞吐是本节主指标；离线的单次 prompt/decode 请求延迟已记录在 JSON 中，",
        "不与论文仅针对在线负载展示的延迟箱线图混比。",
        "",
    ]
    (HERE / "RESULTS_OFFLINE.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "summary_offline.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n",
        encoding="utf-8")
    print("Validated 12 full-window runs and wrote RESULTS_OFFLINE.md")


if __name__ == "__main__":
    main()

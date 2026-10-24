"""Paired analysis of the frozen offline-profile edge expansion screen."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from work3_detour_ablation.report import common_tpot, gpu_work, ratio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def report() -> str:
    from work3_profiled_expansion.run import AUDIT, digest, freeze, write

    freeze()
    parity_seed = PROTOCOL["parity_seed"]
    fresh = read(HERE / "runs" / "development" / f"gate_seed{parity_seed}.json")
    old = read(ROOT / "work3_link_price" / "runs" / "v1" / "development" /
               "C1_multi" / f"gated_seed{parity_seed}.json")
    parity_keys = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s",
                   "ttft_p95_s", "tpot_p95_s", "completion_fraction",
                   "backlog_at_window_end", "route_counts", "query_samples",
                   "gpu_busy_fraction")
    if not all(fresh[key] == old[key] for key in parity_keys):
        raise AssertionError("Unchanged-gate parity failed")
    pairs = []
    for seed in PROTOCOL["development_seeds"]:
        base = read(HERE / "runs" / "development" / f"gate_seed{seed}.json")
        if base["audit_sha256"] != digest(AUDIT):
            raise AssertionError("Base audit changed")
        for cell in PROTOCOL["additional_edge_sets"]:
            if cell == "gate":
                continue
            candidate = read(HERE / "runs" / "development" / f"{cell}_seed{seed}.json")
            if candidate["audit_sha256"] != digest(AUDIT):
                raise AssertionError("Candidate audit changed")
            if base["trace_sha256"] != candidate["trace_sha256"] or base["arrivals"] != candidate["arrivals"]:
                raise AssertionError("Paired arrival trace differs")
            if {tuple(edge) for edge in candidate["additional_edges"]} != {
                    tuple(edge) for edge in PROTOCOL["additional_edge_sets"][cell]}:
                raise AssertionError("Additional edge mismatch")
            common_base, common_candidate, n = common_tpot(base, candidate)
            pairs.append({"seed": seed, "cell": cell,
                          "tpot_relative": ratio(candidate["tpot_p95_s"], base["tpot_p95_s"]),
                          "common_tpot_relative": ratio(common_candidate, common_base),
                          "ttft_relative": ratio(candidate["ttft_p95_s"], base["ttft_p95_s"]),
                          "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                                       base["output_throughput_tokens_per_s"]),
                          "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(base)),
                          "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
                          "common_completed_n": n,
                          "route_count_base": len(base["route_counts"]),
                          "route_count_candidate": len(candidate["route_counts"]),
                          "allowed_edges": candidate["allowed_edges"]})
    decisions = []
    gate = PROTOCOL["screen"]
    for cell in PROTOCOL["additional_edge_sets"]:
        if cell == "gate":
            continue
        rows = [row for row in pairs if row["cell"] == cell]
        means = {key: float(np.mean([row[key] for row in rows])) for key in
                 ("tpot_relative", "common_tpot_relative", "ttft_relative",
                  "throughput_relative", "gpu_work_relative", "completion_absolute")}
        passed = (means["tpot_relative"] <= gate["mean_tpot_relative_max"]
                  and means["common_tpot_relative"] <= gate["mean_common_completed_tpot_relative_max"]
                  and means["throughput_relative"] >= gate["mean_throughput_relative_min"]
                  and means["gpu_work_relative"] <= gate["mean_gpu_seconds_per_token_relative_max"]
                  and means["ttft_relative"] <= gate["mean_ttft_relative_max"])
        decisions.append({"cell": cell, "means": means, "screen_passed": passed})
    eligible = [row for row in decisions if row["screen_passed"]]
    selected = min(eligible, key=lambda row: row["means"]["common_tpot_relative"]) if eligible else None
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "unchanged_gate_parity": True, "parity_seed": parity_seed,
                "pairs": pairs, "decisions": decisions,
                "selected_for_held_out_test": selected["cell"] if selected else None,
                "status": "exploratory_development_only"}
    write(HERE / "analysis.json", analysis)
    lines = ["# C1 三集群：画像指导的两条高速边补充", "",
             "依据 V3 先前的开发轨迹选出两条高频、合法且高速的遗漏边；新种子 131/132",
             "各跑 300 秒，固定布局、负载和到达轨迹。相对未增边的稀疏门控配对。",
             "入口一致性：旧门控与新入口种子 121 的请求样本、路径、吞吐、延迟和 GPU 忙碌量逐项相同。",
             "本实验是方法开发，不是正式效果结论。", "",
             "| 增补边 | P95 TPOT | 共同完成 TPOT | P95 TTFT | 吞吐 | GPU 秒/token | 筛选 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in decisions:
        m = row["means"]
        lines.append(f"| {row['cell']} | {m['tpot_relative']:+.2%} | "
                     f"{m['common_tpot_relative']:+.2%} | {m['ttft_relative']:+.2%} | "
                     f"{m['throughput_relative']:+.2%} | {m['gpu_work_relative']:+.2%} | "
                     f"{'通过' if row['screen_passed'] else '未通过'} |")
    lines += ["", "门槛先于运行写在 `protocol.json`。逐种子配对、完成率和路径数见 `analysis.json`。", ""]
    lines.append(f"进入未见种子 1800 秒检验：{selected['cell']}。" if selected else
                 "无候选达到联合筛选条件；本轮停止，不把开发结果写成方法收益。")
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)

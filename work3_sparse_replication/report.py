"""Compare independent gated windows to the unchanged released V3 controls."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def report():
    from work3_sparse_replication.run import AUDIT, digest, freeze, write

    freeze()
    old = json.loads((ROOT / "experiments/v3_gated_pathspace/analysis.json")
                     .read_text(encoding="utf-8"))["formal"]
    rows = []
    for case in PROTOCOL["loads"]:
        topology = case.removeprefix("C1_")
        for seed in PROTOCOL["seeds"]:
            candidate_path = HERE / "runs" / case / f"gated_seed{seed}.json"
            control_path = ROOT / "benchmarks" / "runs" / topology / f"seed{seed}" / "rcaps_v3.json"
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            control = json.loads(control_path.read_text(encoding="utf-8"))
            relative_control = control_path.relative_to(ROOT).as_posix()
            if digest(control_path) != old["inputs"][relative_control]:
                raise AssertionError("Released control differs from original formal analysis")
            if candidate["audit_sha256"] != digest(AUDIT):
                raise AssertionError("Candidate audit differs")
            if candidate["trace_sha256"] != control["trace_sha256"]:
                raise AssertionError("Arrival trace mismatch")
            if candidate["arrivals"] != control["arrivals"]:
                raise AssertionError("Arrival count mismatch")
            qa, qb = control["query_samples"], candidate["query_samples"]
            common = [uid for uid in set(qa) & set(qb)
                      if qa[uid]["completed"] and qb[uid]["completed"]
                      and qa[uid].get("tpot_s") is not None
                      and qb[uid].get("tpot_s") is not None]
            if not common:
                raise AssertionError("No common completed requests")
            baseline_common = float(np.percentile([qa[uid]["tpot_s"] for uid in common], 95))
            candidate_common = float(np.percentile([qb[uid]["tpot_s"] for uid in common], 95))
            rows.append({"case": case, "seed": seed,
                         "trace_sha256": control["trace_sha256"],
                         "candidate_sha256": digest(candidate_path),
                         "released_control_sha256": digest(control_path),
                         "control_tpot_s": control["tpot_p95_s"],
                         "candidate_tpot_s": candidate["tpot_p95_s"],
                         "tpot_relative": candidate["tpot_p95_s"] / control["tpot_p95_s"] - 1,
                         "throughput_relative":
                         candidate["output_throughput_tokens_per_s"] /
                         control["output_throughput_tokens_per_s"] - 1,
                         "ttft_relative": candidate["ttft_p95_s"] / control["ttft_p95_s"] - 1,
                         "completion_absolute": candidate["completion_fraction"] -
                         control["completion_fraction"],
                         "backlog_delta": candidate["backlog_at_window_end"] -
                         control["backlog_at_window_end"],
                         "common_completed_n": len(common),
                         "common_tpot_relative": candidate_common / baseline_common - 1,
                         "control_routes": len(control["route_counts"]),
                         "candidate_routes": len(candidate["route_counts"]),
                         "allowed_edges": candidate["allowed_edges"]})

    multi = [row for row in rows if row["case"] == "C1_multi"]
    single = [row for row in rows if row["case"] == "C1_single"]
    rule = PROTOCOL["decision"]
    mean = lambda items, field: float(np.mean([item[field] for item in items]))
    ni1 = (mean(multi, "tpot_relative") <= rule["multi_mean_relative_tpot_max"]
           and mean(multi, "throughput_relative") >=
           rule["multi_mean_relative_throughput_min"])
    ni2 = (all(row["tpot_relative"] < 0 for row in single)
           and mean(single, "throughput_relative") >=
           rule["single_mean_relative_throughput_min"])
    result = {"rows": rows, "NI1_multi_noninferiority": ni1,
              "NI2_single_improvement": ni2, "original_protocol_replication_passed": ni1 and ni2,
              "means": {"multi_tpot_relative": mean(multi, "tpot_relative"),
                        "multi_throughput_relative": mean(multi, "throughput_relative"),
                        "single_tpot_relative": mean(single, "tpot_relative"),
                        "single_throughput_relative": mean(single, "throughput_relative")},
              "audit_sha256": digest(AUDIT),
              "disclosure": PROTOCOL["disclosure"]}
    write(HERE / "analysis.json", result)
    lines = ["# 工作三稀疏路径准入独立复验", "",
             "按既有 `v3_gated_pathspace` 正式协议重跑 6 个 gated 窗口，对照仓库发布的原始 V3 JSON。",
             "到达轨迹、负载、放置和窗口长度逐格核对；发布 V3 文件的 SHA256 与历史分析一致。",
             "候选原始窗口此前未在当前检出版本中保留，历史运行入口还依赖缺失的模块；"
             "本目录因此使用独立入口。实验仍是 Helix 离散事件仿真。", "",
             "| 拓扑 | 种子 | V3 TPOT s | gated TPOT s | TPOT 相对 | 吞吐相对 | 共同完成 TPOT 相对 | 完成率 Δ | 路径数 V3→gated |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        lines.append(f"| {row['case']} | {row['seed']} | {row['control_tpot_s']:.4f} | "
                     f"{row['candidate_tpot_s']:.4f} | {row['tpot_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} | {row['common_tpot_relative']:+.2%} | "
                     f"{row['completion_absolute']:+.3f} | {row['control_routes']}→"
                     f"{row['candidate_routes']} |")
    lines += ["", f"原协议 NI1（三集群非劣效）：{'通过' if ni1 else '未通过'}；"
             f"NI2（单集群改善）：{'通过' if ni2 else '未通过'}。",
             f"三集群均值 TPOT {result['means']['multi_tpot_relative']:+.2%}，"
             f"吞吐 {result['means']['multi_throughput_relative']:+.2%}；"
             f"单集群均值 TPOT {result['means']['single_tpot_relative']:+.2%}，"
             f"吞吐 {result['means']['single_throughput_relative']:+.2%}。", "",
             "此判定复用此前在开发失败后重新注册的非劣效门槛；不等于第三工作全面优于 V3，"
             "也不构成真实 GPU 集群测量或新颖性证明。", ""]
    output = HERE / "RESULTS_CN.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output

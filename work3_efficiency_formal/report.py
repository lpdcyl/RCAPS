"""Recompute GPU work and service guardrails from frozen formal JSON."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def gpu_seconds_per_token(run):
    return (sum(run["gpu_busy_fraction"].values()) /
            run["output_throughput_tokens_per_s"])


def report():
    from work3_efficiency_formal.run import AUDIT, digest, freeze, write

    freeze()
    rows = []
    gate = PROTOCOL["gate"]
    for case in PROTOCOL["cases"]:
        for seed in PROTOCOL["seeds"]:
            control_path = (ROOT / "experiments/m2_multistage_candidate/runs/formal" /
                            case / f"seed{seed}" / "single_a100.json")
            candidate_path = HERE / "runs" / case / f"gated_seed{seed}.json"
            base = json.loads(control_path.read_text(encoding="utf-8"))
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            if candidate["audit_sha256"] != digest(AUDIT):
                raise AssertionError("Candidate audit mismatch")
            if (base["trace_sha256"] != candidate["trace_sha256"]
                    or base["arrivals"] != candidate["arrivals"]):
                raise AssertionError("Paired arrival trace mismatch")
            layout = ROOT / "rcaps/v3_layouts" / case
            physical = ROOT / "rcaps/v3/pools" / case / "physical.ini"
            if (base["solution_sha256"] != digest(layout / "solution.ini")
                    or base["sim_cluster_sha256"] != digest(layout / "simulator_cluster.ini")
                    or base["physical_cluster_sha256"] != digest(physical)):
                raise AssertionError("Released control deployment mismatch")
            qa, qb = base["query_samples"], candidate["query_samples"]
            common = [uid for uid in set(qa) & set(qb)
                      if qa[uid]["completed"] and qb[uid]["completed"]
                      and qa[uid].get("tpot_s") is not None
                      and qb[uid].get("tpot_s") is not None]
            if not common:
                raise AssertionError("No common completed TPOT cohort")
            ca = float(np.percentile([qa[uid]["tpot_s"] for uid in common], 95))
            cb = float(np.percentile([qb[uid]["tpot_s"] for uid in common], 95))
            work_base = gpu_seconds_per_token(base)
            work_candidate = gpu_seconds_per_token(candidate)
            rows.append({"case": case, "seed": seed,
                         "control_sha256": digest(control_path),
                         "candidate_sha256": digest(candidate_path),
                         "trace_sha256": base["trace_sha256"],
                         "gpu_s_per_token_base": work_base,
                         "gpu_s_per_token_candidate": work_candidate,
                         "gpu_s_per_token_relative": work_candidate / work_base - 1,
                         "tpot_base_s": base["tpot_p95_s"],
                         "tpot_candidate_s": candidate["tpot_p95_s"],
                         "tpot_relative": candidate["tpot_p95_s"] / base["tpot_p95_s"] - 1,
                         "common_n": len(common),
                         "common_tpot_relative": cb / ca - 1,
                         "throughput_relative":
                         candidate["output_throughput_tokens_per_s"] /
                         base["output_throughput_tokens_per_s"] - 1,
                         "ttft_relative": candidate["ttft_p95_s"] / base["ttft_p95_s"] - 1,
                         "completion_absolute": candidate["completion_fraction"] -
                         base["completion_fraction"],
                         "backlog_delta": candidate["backlog_at_window_end"] -
                         base["backlog_at_window_end"],
                         "route_counts": [len(base["route_counts"]),
                                          len(candidate["route_counts"])]})
    decisions = {}
    for case in PROTOCOL["cases"]:
        subset = [row for row in rows if row["case"] == case]
        mean = lambda field: float(np.mean([row[field] for row in subset]))
        decisions[case] = {
            "gpu_each_seed": all(row["gpu_s_per_token_relative"] <=
                                 gate["gpu_seconds_per_token_relative_max_each_seed"]
                                 for row in subset),
            "throughput_mean": mean("throughput_relative") >=
                               gate["mean_throughput_relative_min_each_case"],
            "tpot_mean": mean("tpot_relative") <=
                         gate["mean_tpot_p95_relative_max_each_case"],
            "common_tpot_mean": mean("common_tpot_relative") <=
                                gate["mean_common_completed_tpot_p95_relative_max_each_case"],
            "completion_mean": mean("completion_absolute") >=
                               gate["mean_completion_fraction_absolute_min_each_case"],
            "means": {field: mean(field) for field in
                      ("gpu_s_per_token_relative", "throughput_relative",
                       "tpot_relative", "common_tpot_relative",
                       "completion_absolute", "ttft_relative")}}
        decisions[case]["passed"] = all(value for key, value in decisions[case].items()
                                        if key not in ("means", "passed"))
    overall = all(item["passed"] for item in decisions.values())
    write(HERE / "analysis.json",
          {"rows": rows, "case_decisions": decisions, "formal_passed": overall,
           "audit_sha256": digest(AUDIT),
           "discovery_disclosure": PROTOCOL["discovery_disclosure"]})
    lines = ["# 工作三：C2/C3 单位 GPU 工作量正式检验", "",
             "候选边集和 50 MB/s 门槛保持 C1 版本不变；C2/C3 均无额外高速绕行边，"
             "因此候选退化为规范路径图。每格 1800 秒、同放置同轨迹、不排空。",
             "本主指标在 C1 与 C2/C3 短窗口观察后才注册；本报告使用此前未运行过门控候选的"
             "C2/C3 正式种子 0/1/2。均为离散事件仿真。", "",
             "GPU 秒/输出 token = 窗口内各 GPU 忙碌比例之和 ÷ 输出 token/s；"
             "其中包含 Prompt 与 Decode 的 GPU 工作。", "",
             "| 资源池 | 种子 | GPU 秒/token 相对 | 全体 TPOT 相对 | 共同完成 TPOT 相对 | 吞吐相对 | 完成率 Δ | 路径数 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        lines.append(f"| {row['case']} | {row['seed']} | "
                     f"{row['gpu_s_per_token_relative']:+.2%} | "
                     f"{row['tpot_relative']:+.2%} | "
                     f"{row['common_tpot_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} | "
                     f"{row['completion_absolute']:+.3f} | "
                     f"{row['route_counts'][0]}→{row['route_counts'][1]} |")
    lines += [""]
    for case, decision in decisions.items():
        means = decision["means"]
        lines.append(f"{case} 联合门槛：{'通过' if decision['passed'] else '未通过'}；"
                     f"均值 GPU 秒/token {means['gpu_s_per_token_relative']:+.2%}，"
                     f"全体 TPOT {means['tpot_relative']:+.2%}，"
                     f"共同完成 TPOT {means['common_tpot_relative']:+.2%}，"
                     f"吞吐 {means['throughput_relative']:+.2%}。")
    lines += ["", f"总判定：{'通过' if overall else '未通过'}。门槛见 `protocol.json`；"
             "逐格原始结果及控制文件哈希见 `runs/`、`analysis.json`、`audit.json`。", ""]
    output = HERE / "RESULTS_CN.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output

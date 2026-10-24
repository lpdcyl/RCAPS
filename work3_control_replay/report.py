"""Rejudge the locked efficiency gate using same-runtime replayed controls."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from work3_efficiency_formal.report import gpu_seconds_per_token

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
FORMAL = json.loads((ROOT / "work3_efficiency_formal/protocol.json").read_text(encoding="utf-8"))


def report():
    from work3_control_replay.run import AUDIT, digest, freeze, write

    freeze()
    rows = []
    for case in PROTOCOL["cases"]:
        for seed in PROTOCOL["seeds"]:
            replay_path = HERE / "runs" / case / f"v3_seed{seed}.json"
            archived_path = (ROOT / "experiments/m2_multistage_candidate/runs/formal" /
                             case / f"seed{seed}" / "single_a100.json")
            candidate_path = (ROOT / "work3_efficiency_formal/runs" /
                              case / f"gated_seed{seed}.json")
            replay = json.loads(replay_path.read_text(encoding="utf-8"))
            archived = json.loads(archived_path.read_text(encoding="utf-8"))
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            if replay["audit_sha256"] != digest(AUDIT):
                raise AssertionError("Replay audit mismatch")
            for other in (archived, candidate):
                if (replay["trace_sha256"] != other["trace_sha256"]
                        or replay["arrivals"] != other["arrivals"]):
                    raise AssertionError("Unpaired trace")
            qa, qb = replay["query_samples"], candidate["query_samples"]
            common = [uid for uid in set(qa) & set(qb)
                      if qa[uid]["completed"] and qb[uid]["completed"]
                      and qa[uid].get("tpot_s") is not None
                      and qb[uid].get("tpot_s") is not None]
            if not common:
                raise AssertionError("No common completed cohort")
            common_replay = float(np.percentile([qa[uid]["tpot_s"] for uid in common], 95))
            common_candidate = float(np.percentile([qb[uid]["tpot_s"] for uid in common], 95))
            work_replay = gpu_seconds_per_token(replay)
            work_candidate = gpu_seconds_per_token(candidate)
            rows.append({"case": case, "seed": seed,
                         "trace_sha256": replay["trace_sha256"],
                         "replay_sha256": digest(replay_path),
                         "archived_sha256": digest(archived_path),
                         "candidate_sha256": digest(candidate_path),
                         "archived_vs_replay_tpot_relative":
                         replay["tpot_p95_s"] / archived["tpot_p95_s"] - 1,
                         "archived_vs_replay_throughput_relative":
                         replay["output_throughput_tokens_per_s"] /
                         archived["output_throughput_tokens_per_s"] - 1,
                         "gpu_s_per_token_relative": work_candidate / work_replay - 1,
                         "tpot_relative": candidate["tpot_p95_s"] / replay["tpot_p95_s"] - 1,
                         "common_tpot_relative": common_candidate / common_replay - 1,
                         "common_n": len(common),
                         "throughput_relative":
                         candidate["output_throughput_tokens_per_s"] /
                         replay["output_throughput_tokens_per_s"] - 1,
                         "completion_absolute": candidate["completion_fraction"] -
                         replay["completion_fraction"],
                         "ttft_relative": candidate["ttft_p95_s"] / replay["ttft_p95_s"] - 1,
                         "backlog_delta": candidate["backlog_at_window_end"] -
                         replay["backlog_at_window_end"],
                         "route_counts": [len(replay["route_counts"]),
                                          len(candidate["route_counts"])]})
    gate = FORMAL["gate"]
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
          {"rows": rows, "case_decisions": decisions, "same_runtime_gate_passed": overall,
           "audit_sha256": digest(AUDIT)})
    lines = ["# C2/C3 当前运行时 V3 对照复跑", "",
             "历史 V3 正式 JSON 的 `execution_sha256` 与当前核心源码不同。",
             "本卡在同一 Python/numpy、同一当前源码与相同物理配置下重跑 6 个 V3 窗口，",
             "再将此前已冻结的 gated 候选逐种子配对。到达轨迹逐格一致。",
             "主门槛沿用 `work3_efficiency_formal/protocol.json`，没有修改。", "",
             "| 资源池 | 种子 | 历史→重跑 V3 TPOT | gated 对重跑 GPU 秒/token | gated 对重跑 TPOT | 共同完成 TPOT | 吞吐 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['case']} | {row['seed']} | "
                     f"{row['archived_vs_replay_tpot_relative']:+.2%} | "
                     f"{row['gpu_s_per_token_relative']:+.2%} | "
                     f"{row['tpot_relative']:+.2%} | "
                     f"{row['common_tpot_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} |")
    lines += [""]
    for case, decision in decisions.items():
        means = decision["means"]
        lines.append(f"{case} 同运行时门槛：{'通过' if decision['passed'] else '未通过'}；"
                     f"GPU 秒/token 均值 {means['gpu_s_per_token_relative']:+.2%}，"
                     f"全体 TPOT {means['tpot_relative']:+.2%}，"
                     f"共同完成 TPOT {means['common_tpot_relative']:+.2%}，"
                     f"吞吐 {means['throughput_relative']:+.2%}。")
    lines += ["", f"总判定：{'通过' if overall else '未通过'}。"
             "历史对照只用于源码漂移敏感性说明，最终判定使用当前运行时对照。", ""]
    output = HERE / "RESULTS_CN.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output

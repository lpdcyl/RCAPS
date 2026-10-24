"""Recalculate unseen full-window results and the frozen joint decision."""

from __future__ import annotations

import json

from work3_detour_ablation.report import common_tpot, gpu_work, ratio
from work3_selective_chunk.formal_run import AUDIT, FORMAL, PROTOCOL, digest, freeze, write


def read(case: str, cell: str, seed: int) -> dict:
    path = FORMAL / "runs" / case / f"{cell}_seed{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def compare(base: dict, candidate: dict) -> dict:
    if base["trace_sha256"] != candidate["trace_sha256"] or base["arrivals"] != candidate["arrivals"]:
        raise AssertionError("Paired arrival trace differs")
    if base["audit_sha256"] != candidate["audit_sha256"]:
        raise AssertionError("Formal audit differs")
    a, b, n = common_tpot(base, candidate)
    return {"tpot_relative": ratio(candidate["tpot_p95_s"], base["tpot_p95_s"]),
            "common_tpot_relative": ratio(b, a),
            "ttft_relative": ratio(candidate["ttft_p95_s"], base["ttft_p95_s"]),
            "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                         base["output_throughput_tokens_per_s"]),
            "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(base)),
            "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
            "common_completed_n": n,
            "route_count_base": len(base["route_counts"]),
            "route_count_candidate": len(candidate["route_counts"]),
            "backlog_base": base["backlog_at_window_end"],
            "backlog_candidate": candidate["backlog_at_window_end"]}


def report() -> str:
    freeze()
    rows = []
    decisions = []
    for seed in PROTOCOL["seeds"]:
        runs = {cell: read(PROTOCOL["case"], cell, seed) for cell in PROTOCOL["methods"]}
        for cell, row in runs.items():
            if row["audit_sha256"] != digest(AUDIT):
                raise AssertionError(f"Audit mismatch: {cell}/{seed}")
            if len(row["query_samples"]) != row["arrivals"]:
                raise AssertionError(f"Incomplete query samples: {cell}/{seed}")
        primary = compare(runs["gate"], runs["chunk_slow"])
        versus_v3 = compare(runs["v3"], runs["chunk_slow"])
        versus_all = compare(runs["chunk_all"], runs["chunk_slow"])
        slow_pause = runs["chunk_slow"]["phase_link_profile"]["paused_chunks"]
        all_pause = runs["chunk_all"]["phase_link_profile"]["paused_chunks"]
        pause_relative = ratio(slow_pause, all_pause)
        if not runs["chunk_slow"]["phase_link_profile"]["eligible_link_uids"]:
            raise AssertionError("No slow link was instrumented")
        p = PROTOCOL["primary_gate_each_seed_chunk_slow_vs_gate"]
        v = PROTOCOL["overall_work3_gate_each_seed_chunk_slow_vs_v3"]
        s = PROTOCOL["selectivity_gate_each_seed_chunk_slow_vs_chunk_all"]
        primary_pass = (primary["tpot_relative"] <= p["tpot_p95_relative_max"]
                        and primary["common_tpot_relative"] <= p["common_completed_tpot_p95_relative_max"]
                        and primary["ttft_relative"] <= p["ttft_p95_relative_max"]
                        and primary["throughput_relative"] >= p["throughput_relative_min"]
                        and primary["gpu_work_relative"] <= p["gpu_seconds_per_token_relative_max"]
                        and primary["completion_absolute"] >= p["completion_fraction_absolute_min"])
        overall_pass = (versus_v3["tpot_relative"] <= v["tpot_p95_relative_max"]
                        and versus_v3["gpu_work_relative"] <= v["gpu_seconds_per_token_relative_max"]
                        and versus_v3["throughput_relative"] >= v["throughput_relative_min"])
        selectivity_pass = (versus_all["tpot_relative"] <= s["tpot_p95_relative_max"]
                            and versus_all["throughput_relative"] >= s["throughput_relative_min"]
                            and pause_relative <= s["pause_count_relative_max"])
        decisions.append({"seed": seed, "primary_pass": primary_pass,
                          "overall_work3_pass": overall_pass,
                          "selectivity_pass": selectivity_pass,
                          "all_pass": primary_pass and overall_pass and selectivity_pass})
        rows.append({"seed": seed, "chunk_slow_vs_gate": primary,
                     "chunk_slow_vs_v3": versus_v3,
                     "chunk_slow_vs_chunk_all": versus_all,
                     "slow_pauses": slow_pause, "all_pauses": all_pause,
                     "pause_relative": pause_relative,
                     "tpot_seconds": {name: run["tpot_p95_s"] for name, run in runs.items()},
                     "throughput": {name: run["output_throughput_tokens_per_s"]
                                    for name, run in runs.items()},
                     "gpu_seconds_per_token": {name: gpu_work(run) for name, run in runs.items()}})
    passed = all(decision["all_pass"] for decision in decisions)
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "rows": rows, "decisions": decisions, "formal_joint_gate_passed": passed,
                "status": "completed"}
    write(FORMAL / "analysis.json", analysis)
    lines = ["# 工作三：慢链路专用 Prompt 分块的未见种子长窗口结果", "",
             "相同 C1 三集群放置和到达轨迹，种子 201/202/203，各 1800 秒固定窗口。",
             "在看到开发窗口之后，正式种子运行之前冻结了 `formal_protocol.json`、",
             "实现与联合门槛。所有结果为 Helix 离散事件仿真。", "",
             "| 种子 | 慢链路分块对稀疏门控 TPOT | 共同完成 TPOT | TTFT | 吞吐 | GPU 秒/token | 对 V3 TPOT | 对 V3 GPU 工作 | 对全链路 TPOT | 暂停次数 慢/全 | 联合判定 |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for row, decision in zip(rows, decisions):
        p, v, a = (row["chunk_slow_vs_gate"], row["chunk_slow_vs_v3"],
                   row["chunk_slow_vs_chunk_all"])
        lines.append(f"| {row['seed']} | {p['tpot_relative']:+.2%} | "
                     f"{p['common_tpot_relative']:+.2%} | {p['ttft_relative']:+.2%} | "
                     f"{p['throughput_relative']:+.2%} | {p['gpu_work_relative']:+.2%} | "
                     f"{v['tpot_relative']:+.2%} | {v['gpu_work_relative']:+.2%} | "
                     f"{a['tpot_relative']:+.2%} | {row['slow_pauses']}/{row['all_pauses']} | "
                     f"{'通过' if decision['all_pass'] else '未通过'} |")
    lines += ["", f"三项逐种子联合门槛：{'全部通过' if passed else '未全部通过'}。",
              "每格完成率、积压、请求级共同样本、路径数和完整门槛复算见 `analysis.json`。",
              "单位 GPU 工作量仍是仿真 GPU 忙碌秒/输出 token，包含 Prompt 与 Decode；",
              "分块本身与 MoLink 相关，不能把本结果表述为分块技术的独立新颖性证明。", ""]
    path = FORMAL / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

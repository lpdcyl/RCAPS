"""Recompute paired known-seed 0/1/2 long-window outcomes from raw JSON."""

from __future__ import annotations

import json

from work3_chunk_012.run import AUDIT, HERE, PROTOCOL, ROOT, digest, freeze, write
from work3_detour_ablation.report import common_tpot, gpu_work, ratio


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def compare(base: dict, candidate: dict) -> dict:
    if base["trace_sha256"] != candidate["trace_sha256"] or base["arrivals"] != candidate["arrivals"]:
        raise AssertionError("Paired arrivals or trace differs")
    old_common, new_common, n = common_tpot(base, candidate)
    return {"tpot_relative": ratio(candidate["tpot_p95_s"], base["tpot_p95_s"]),
            "common_tpot_relative": ratio(new_common, old_common),
            "common_completed_n": n,
            "ttft_relative": ratio(candidate["ttft_p95_s"], base["ttft_p95_s"]),
            "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                         base["output_throughput_tokens_per_s"]),
            "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(base)),
            "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
            "backlog_base": base["backlog_at_window_end"],
            "backlog_candidate": candidate["backlog_at_window_end"],
            "routes_base": len(base["route_counts"]),
            "routes_candidate": len(candidate["route_counts"])}


def report() -> str:
    freeze()
    rows = []
    for seed in PROTOCOL["seeds"]:
        gate = read(ROOT / PROTOCOL["controls"]["gate"].format(seed=seed))
        v3 = read(ROOT / PROTOCOL["controls"]["v3"].format(seed=seed))
        candidate = read(HERE / "runs" / f"chunk_4MiB_seed{seed}.json")
        if candidate["audit_sha256"] != digest(AUDIT) or candidate["seed"] != seed:
            raise AssertionError(f"Candidate identity differs: {seed}")
        if candidate["chunk_bytes"] != PROTOCOL["chunk_bytes"] or candidate["allowed_edges"] != 30:
            raise AssertionError(f"Candidate method differs: {seed}")
        profile = candidate["phase_link_profile"]
        if profile["chunk_bytes"] != PROTOCOL["chunk_bytes"] or not profile["eligible_link_uids"]:
            raise AssertionError(f"Installed slow-link hook differs: {seed}")
        for name, run in (("gate", gate), ("v3", v3), ("chunk_4MiB", candidate)):
            if run["seed"] != seed or len(run["query_samples"]) != run["arrivals"]:
                raise AssertionError(f"Run samples differ: {seed}/{name}")
        if len({run["trace_sha256"] for run in (gate, v3, candidate)}) != 1:
            raise AssertionError(f"Trace differs: {seed}")
        primary = compare(gate, candidate)
        overall = compare(v3, candidate)
        p = PROTOCOL["primary_gate_each_seed_vs_gate"]
        v = PROTOCOL["overall_work3_gate_each_seed_vs_v3"]
        primary_pass = (primary["tpot_relative"] <= p["tpot_p95_relative_max"]
                        and primary["common_tpot_relative"] <= p["common_completed_tpot_p95_relative_max"]
                        and primary["ttft_relative"] <= p["ttft_p95_relative_max"]
                        and primary["throughput_relative"] >= p["throughput_relative_min"]
                        and primary["gpu_work_relative"] <= p["gpu_seconds_per_token_relative_max"]
                        and primary["completion_absolute"] >= p["completion_fraction_absolute_min"])
        overall_pass = (overall["tpot_relative"] <= v["tpot_p95_relative_max"]
                        and overall["gpu_work_relative"] <= v["gpu_seconds_per_token_relative_max"]
                        and overall["throughput_relative"] >= v["throughput_relative_min"])
        rows.append({"seed": seed, "versus_gate": primary, "versus_v3": overall,
                     "primary_pass": primary_pass, "overall_pass": overall_pass,
                     "all_pass": primary_pass and overall_pass,
                     "paused_chunks": profile["paused_chunks"],
                     "eligible_slow_link_uids": profile["eligible_link_uids"],
                     "raw": {"v3": {"tpot_p95_s": v3["tpot_p95_s"],
                                     "gpu_seconds_per_token": gpu_work(v3)},
                             "gate": {"tpot_p95_s": gate["tpot_p95_s"],
                                      "gpu_seconds_per_token": gpu_work(gate)},
                             "chunk_4MiB": {"tpot_p95_s": candidate["tpot_p95_s"],
                                            "gpu_seconds_per_token": gpu_work(candidate)}}})
    passed = all(row["all_pass"] for row in rows)
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "rows": rows, "known_seed_joint_gate_passed": passed,
                "status": "completed_known_seed_supplementary_replay"}
    write(HERE / "analysis.json", analysis)
    lines = ["# 稀疏路径准入＋慢链路 4 MiB：0/1/2 长窗口补充复验", "",
             "C1 三集群，固定放置、同到达轨迹，种子 0/1/2 各 1800 秒、不排空。",
             "使用既有同种子 V3 与稀疏门控原始窗口作为对照；新运行的只有组合方法三格。",
             "协议及两组与 301/302/303 相同的主要护栏在运行前冻结。",
             "0/1/2 的旧对照结果此前已观察，故本组是已知种子补充复验，不能称为独立未见种子确认。", "",
             "| 种子 | 对门控 TPOT | 共同完成 TPOT | TTFT | 吞吐 | GPU 秒/token | 对 V3 TPOT | 对 V3 GPU 工作 | 分块暂停 | 联合护栏 |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        p, v = row["versus_gate"], row["versus_v3"]
        lines.append(f"| {row['seed']} | {p['tpot_relative']:+.2%} | "
                     f"{p['common_tpot_relative']:+.2%} | {p['ttft_relative']:+.2%} | "
                     f"{p['throughput_relative']:+.2%} | {p['gpu_work_relative']:+.2%} | "
                     f"{v['tpot_relative']:+.2%} | {v['gpu_work_relative']:+.2%} | "
                     f"{row['paused_chunks']} | {'通过' if row['all_pass'] else '未通过'} |")
    lines += ["", f"逐种子联合护栏：{'全部通过' if passed else '未全部通过'}。",
              "完整相对值、完成率、积压、路径数、请求级配对和原始窗口见 `analysis.json` 与 `runs/`。",
              "源码、物理配置及既有对照文件哈希见 `audit.json`。",
              "旧 hook 的 `treatment` 文本固定写着 `1MiB`；实际分块大小由",
              "`chunk_bytes=4194304`、协议和运行时检查确认。结果仅为 Helix 离散事件仿真。", ""]
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

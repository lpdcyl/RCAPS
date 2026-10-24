"""Recompute the development-only path admission × transmission matrix."""

from __future__ import annotations

import json
import math

from work3_detour_ablation.report import common_tpot, gpu_work, ratio
from work3_joint_diagnostic.run import AUDIT, HERE, PROTOCOL, digest, freeze, write


def read(cell: str, seed: int) -> dict:
    return json.loads((HERE / "runs" / "development" / f"{cell}_seed{seed}.json").read_text(encoding="utf-8"))


def compare(base: dict, candidate: dict) -> dict:
    if base["trace_sha256"] != candidate["trace_sha256"] or base["arrivals"] != candidate["arrivals"]:
        raise AssertionError("Paired arrival traces differ")
    a, b, common_n = common_tpot(base, candidate)
    return {
        "tpot_relative": ratio(candidate["tpot_p95_s"], base["tpot_p95_s"]),
        "common_completed_tpot_relative": ratio(b, a),
        "common_completed_n": common_n,
        "ttft_relative": ratio(candidate["ttft_p95_s"], base["ttft_p95_s"]),
        "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                     base["output_throughput_tokens_per_s"]),
        "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(base)),
        "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
        "route_count_base": len(base["route_counts"]),
        "route_count_candidate": len(candidate["route_counts"]),
    }


def report() -> str:
    freeze()
    rows = []
    for seed in PROTOCOL["seeds"]:
        runs = {cell: read(cell, seed) for cell in PROTOCOL["cells"]}
        for cell, row in runs.items():
            if row["audit_sha256"] != digest(AUDIT):
                raise AssertionError(f"Run identity differs: {seed}/{cell}")
            if len(row["query_samples"]) != row["arrivals"]:
                raise AssertionError(f"Missing query samples: {seed}/{cell}")
            if row["duration_s"] != PROTOCOL["duration_s"]:
                raise AssertionError(f"Window duration differs: {seed}/{cell}")
            if cell.startswith("gate") and row["allowed_edges"] != 30:
                raise AssertionError(f"Gate graph differs: {seed}/{cell}")
            if cell.endswith(("slow4", "all4")):
                if row["phase_link_profile"]["chunk_bytes"] != PROTOCOL["chunk_bytes"]:
                    raise AssertionError(f"Chunk size differs: {seed}/{cell}")
        if len({run["trace_sha256"] for run in runs.values()}) != 1:
            raise AssertionError(f"Trace differs across cells: {seed}")
        comparisons = {
            "gate_vs_full": compare(runs["full"], runs["gate"]),
            "gate_slow4_vs_gate": compare(runs["gate"], runs["gate_slow4"]),
            "full_slow4_vs_full": compare(runs["full"], runs["full_slow4"]),
            "gate_slow4_vs_full_slow4": compare(runs["full_slow4"], runs["gate_slow4"]),
            "gate_all4_vs_gate_slow4": compare(runs["gate_slow4"], runs["gate_all4"]),
            "full_all4_vs_full_slow4": compare(runs["full_slow4"], runs["full_all4"]),
        }
        interaction = (math.log(runs["gate_slow4"]["tpot_p95_s"] / runs["gate"]["tpot_p95_s"])
                       - math.log(runs["full_slow4"]["tpot_p95_s"] / runs["full"]["tpot_p95_s"]))
        rows.append({"seed": seed, "comparisons": comparisons,
                     "interaction_log_tpot": interaction,
                     "raw": {cell: {
                         "tpot_p95_s": run["tpot_p95_s"], "ttft_p95_s": run["ttft_p95_s"],
                         "throughput": run["output_throughput_tokens_per_s"],
                         "gpu_seconds_per_token": gpu_work(run),
                         "completion_fraction": run["completion_fraction"],
                         "backlog": run["backlog_at_window_end"],
                         "route_count": len(run["route_counts"]),
                         "paused_chunks": (run.get("phase_link_profile") or {}).get("paused_chunks", 0),
                     } for cell, run in runs.items()}})
    data = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT), "rows": rows,
            "status": "development_diagnostic_only"}
    write(HERE / "analysis.json", data)
    lines = ["# 路径准入 × Prompt 传输分块：开发诊断", "",
             "C1 三集群，同轨迹配对，种子 161/162 各 300 秒。该矩阵在运行前冻结，",
             "只用于识别方法问题，不构成新算法或正式收益验证。", "",
             "| 种子 | 门控对完整图 TPOT | 门控对完整图 GPU 工作 | 慢链路 4 MiB 对门控 TPOT | 慢链路 4 MiB 对完整图 TPOT | 门控+4 MiB 对完整图+4 MiB TPOT | TPOT 对数交互 |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        c = row["comparisons"]
        lines.append(f"| {row['seed']} | {c['gate_vs_full']['tpot_relative']:+.2%} | "
                     f"{c['gate_vs_full']['gpu_work_relative']:+.2%} | "
                     f"{c['gate_slow4_vs_gate']['tpot_relative']:+.2%} | "
                     f"{c['full_slow4_vs_full']['tpot_relative']:+.2%} | "
                     f"{c['gate_slow4_vs_full_slow4']['tpot_relative']:+.2%} | "
                     f"{row['interaction_log_tpot']:+.4f} |")
    lines += ["", "交互项为 log(门控+4 MiB / 门控) − log(完整图+4 MiB / 完整图)。",
              "负值表示分块在门控图上的相对 TPOT 收益更大；正值相反。",
              "它只是两个开发种子的观察量，不能单独证明机制或统计显著性。", "",
              "| 种子 | 门控全链路对仅慢链路 TPOT | 门控暂停次数 全/慢 | 完整图全链路对仅慢链路 TPOT | 完整图暂停次数 全/慢 |",
              "| ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        c, raw = row["comparisons"], row["raw"]
        lines.append(f"| {row['seed']} | {c['gate_all4_vs_gate_slow4']['tpot_relative']:+.2%} | "
                     f"{raw['gate_all4']['paused_chunks']}/{raw['gate_slow4']['paused_chunks']} | "
                     f"{c['full_all4_vs_full_slow4']['tpot_relative']:+.2%} | "
                     f"{raw['full_all4']['paused_chunks']}/{raw['full_slow4']['paused_chunks']} |")
    lines += ["", "完整六格的吞吐、TTFT、GPU 工作、完成率、积压、路径数和共同完成请求配对",
              "见 `analysis.json`；原始窗口和日志见 `runs/`，源码与环境哈希见 `audit.json`。", ""]
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

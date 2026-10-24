"""Independent paired endpoint checks and registered selective-chunk screen."""

from __future__ import annotations

import json
from pathlib import Path

from work3_detour_ablation.report import common_tpot, gpu_work, ratio

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def read(phase: str, cell: str, seed: int) -> dict:
    return json.loads((HERE / "runs" / phase / f"{cell}_seed{seed}.json").read_text(encoding="utf-8"))


def compare(base: dict, candidate: dict, cell: str, seed: int) -> dict:
    if base["trace_sha256"] != candidate["trace_sha256"] or base["arrivals"] != candidate["arrivals"]:
        raise AssertionError("Paired arrival trace differs")
    if base["audit_sha256"] != candidate["audit_sha256"]:
        raise AssertionError("Audit differs")
    a, b, n = common_tpot(base, candidate)
    return {"seed": seed, "cell": cell,
            "tpot_relative": ratio(candidate["tpot_p95_s"], base["tpot_p95_s"]),
            "common_tpot_relative": ratio(b, a),
            "ttft_relative": ratio(candidate["ttft_p95_s"], base["ttft_p95_s"]),
            "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                         base["output_throughput_tokens_per_s"]),
            "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(base)),
            "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
            "common_completed_n": n,
            "route_count_base": len(base["route_counts"]),
            "route_count_candidate": len(candidate["route_counts"]),
            "chunk_pauses": candidate["phase_link_profile"]["paused_chunks"],
            "eligible_links": candidate["phase_link_profile"].get("eligible_link_uids")}


def report() -> str:
    from work3_selective_chunk.run import AUDIT, digest, freeze, write

    freeze()
    smoke_seed = PROTOCOL["smoke_seed"]
    base = read("smoke", "gate", smoke_seed)
    noop = read("smoke", "slow_noop", smoke_seed)
    smoke_keys = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s",
                  "ttft_p95_s", "tpot_p95_s", "completion_fraction",
                  "backlog_at_window_end", "route_counts", "query_samples",
                  "gpu_busy_fraction")
    if not all(base[key] == noop[key] for key in smoke_keys):
        raise AssertionError("Large-chunk selective hook is not a no-op")
    if not noop["phase_link_profile"]["eligible_link_uids"]:
        raise AssertionError("No physical slow link selected")
    rows = []
    decisions = []
    gate = PROTOCOL["development_screen"]
    for seed in PROTOCOL["development_seeds"]:
        base = read("development", "gate", seed)
        if base["audit_sha256"] != digest(AUDIT):
            raise AssertionError("Base audit differs")
        for cell in ("chunk_all", "chunk_slow"):
            candidate = read("development", cell, seed)
            row = compare(base, candidate, cell, seed)
            rows.append(row)
            if cell == "chunk_slow":
                passed = (row["tpot_relative"] <= gate["tpot_p95_relative_max_each_seed"]
                          and row["common_tpot_relative"] <= gate["common_completed_tpot_p95_relative_max_each_seed"]
                          and row["ttft_relative"] <= gate["ttft_p95_relative_max_each_seed"]
                          and row["throughput_relative"] >= gate["throughput_relative_min_each_seed"]
                          and row["gpu_work_relative"] <= gate["gpu_seconds_per_token_relative_max_each_seed"])
                decisions.append({"seed": seed, "passed": passed})
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "smoke_noop_parity": True,
                "smoke_eligible_slow_links": noop["phase_link_profile"]["eligible_link_uids"],
                "rows": rows, "decisions": decisions,
                "development_passed": all(row["passed"] for row in decisions),
                "status": "exploratory_development_only"}
    write(HERE / "analysis.json", analysis)
    lines = ["# 工作三：稀疏路径上的慢链路专用 Prompt 传输分块", "",
             "同一放置、路径规则、负载与到达轨迹；种子 141/142、300 秒固定窗口。",
             "1 MiB 分块可在块间调度已就绪 Decode；`chunk_all` 对全部计算链路应用，",
             "`chunk_slow` 只作用于带宽不超过 50 MB/s 的计算链路。该技术与 MoLink 相关，",
             "此处检验与稀疏路径准入结合的系统效果，不宣称分块本身新颖。", "",
             "大块 no-op 烟测与原门控的请求样本、路径、吞吐、延迟和 GPU 工作逐项一致。", "",
             "| 种子 | 方法 | P95 TPOT 相对门控 | 共同完成 TPOT | P95 TTFT | 吞吐 | GPU 秒/token | 分块暂停次数 |",
             "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['seed']} | {row['cell']} | {row['tpot_relative']:+.2%} | "
                     f"{row['common_tpot_relative']:+.2%} | {row['ttft_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} | {row['gpu_work_relative']:+.2%} | "
                     f"{row['chunk_pauses']} |")
    lines += ["", f"开发联合门槛：{'通过' if analysis['development_passed'] else '未通过'}。",
              "两种子每格都需通过预定延迟、吞吐和 GPU 工作护栏；详见 `protocol.json` 和 `analysis.json`。"]
    lines.append("下一步可登记未见种子 1800 秒确认。" if analysis["development_passed"] else
                 "按预定规则停止此候选；不调分块大小或门槛来补过。")
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)

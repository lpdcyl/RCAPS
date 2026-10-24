"""Recompute the unseen 4 MiB formal gate from raw paired windows."""

from __future__ import annotations

import json

from work3_detour_ablation.report import gpu_work, ratio
from work3_selective_chunk.formal_report import compare
from work3_chunk_size.formal_run import AUDIT, FORMAL, PROTOCOL, digest, freeze, write


def read(cell: str, seed: int) -> dict:
    path = FORMAL / "runs" / PROTOCOL["case"] / f"{cell}_seed{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def report() -> str:
    freeze()
    rows = []
    decisions = []
    for seed in PROTOCOL["seeds"]:
        runs = {cell: read(cell, seed) for cell in PROTOCOL["methods"]}
        for cell, row in runs.items():
            if row["audit_sha256"] != digest(AUDIT) or row["chunk_bytes"] != PROTOCOL["methods"][cell]:
                raise AssertionError(f"Wrong run identity: {seed}/{cell}")
            if len(row["query_samples"]) != row["arrivals"]:
                raise AssertionError(f"Missing request samples: {seed}/{cell}")
            if row["allowed_edges"] != (0 if cell == "v3" else 30):
                raise AssertionError(f"Unexpected admitted graph: {seed}/{cell}")
        candidate = runs["chunk_4MiB"]
        old = runs["chunk_1MiB"]
        base = runs["gate"]
        full = runs["v3"]
        primary = compare(base, candidate)
        overall = compare(full, candidate)
        tradeoff = compare(old, candidate)
        pauses = {cell: runs[cell]["phase_link_profile"]["paused_chunks"]
                  for cell in ("chunk_1MiB", "chunk_4MiB")}
        pause_relative = ratio(pauses["chunk_4MiB"], pauses["chunk_1MiB"])
        if candidate["phase_link_profile"]["chunk_bytes"] != 4_194_304:
            raise AssertionError("Actual hook chunk size differs")
        p = PROTOCOL["primary_gate_each_seed_4MiB_vs_gate"]
        v = PROTOCOL["overall_work3_gate_each_seed_4MiB_vs_v3"]
        t = PROTOCOL["chunk_tradeoff_gate_each_seed_4MiB_vs_1MiB"]
        primary_pass = (primary["tpot_relative"] <= p["tpot_p95_relative_max"]
                        and primary["common_tpot_relative"] <= p["common_completed_tpot_p95_relative_max"]
                        and primary["ttft_relative"] <= p["ttft_p95_relative_max"]
                        and primary["throughput_relative"] >= p["throughput_relative_min"]
                        and primary["gpu_work_relative"] <= p["gpu_seconds_per_token_relative_max"]
                        and primary["completion_absolute"] >= p["completion_fraction_absolute_min"])
        overall_pass = (overall["tpot_relative"] <= v["tpot_p95_relative_max"]
                        and overall["gpu_work_relative"] <= v["gpu_seconds_per_token_relative_max"]
                        and overall["throughput_relative"] >= v["throughput_relative_min"])
        tradeoff_pass = (tradeoff["tpot_relative"] <= t["tpot_p95_relative_max"]
                         and tradeoff["throughput_relative"] >= t["throughput_relative_min"]
                         and pause_relative <= t["pause_count_relative_max"])
        decisions.append({"seed": seed, "primary_pass": primary_pass,
                          "overall_work3_pass": overall_pass,
                          "chunk_tradeoff_pass": tradeoff_pass,
                          "all_pass": primary_pass and overall_pass and tradeoff_pass})
        rows.append({"seed": seed, "chunk_4MiB_vs_gate": primary,
                     "chunk_4MiB_vs_v3": overall, "chunk_4MiB_vs_1MiB": tradeoff,
                     "pause_counts": pauses, "pause_relative": pause_relative,
                     "tpot_seconds": {name: run["tpot_p95_s"] for name, run in runs.items()},
                     "throughput": {name: run["output_throughput_tokens_per_s"]
                                    for name, run in runs.items()},
                     "gpu_seconds_per_token": {name: gpu_work(run) for name, run in runs.items()}})
    passed = all(decision["all_pass"] for decision in decisions)
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "rows": rows, "decisions": decisions,
                "formal_joint_gate_passed": passed, "status": "completed"}
    write(FORMAL / "analysis.json", analysis)
    lines = ["# 4 MiB 慢链路专用分块：未见种子长窗口", "",
             "C1 三集群冻结放置、同到达轨迹，种子 301/302/303、各 1800 秒、不排空。",
             "4 MiB 在新开发种子 151/152 中按预定规则选出，再在本组未见种子运行前冻结协议、",
             "源码和联合门槛；所有结果是 Helix 离散事件仿真。", "",
             "| 种子 | 4 MiB 对门控 TPOT | 共同完成 TPOT | TTFT | 吞吐 | GPU 秒/token | 对 V3 TPOT | 对 V3 GPU 工作 | 对 1 MiB TPOT | 暂停次数 4/1 MiB | 判定 |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for row, decision in zip(rows, decisions):
        p = row["chunk_4MiB_vs_gate"]
        v = row["chunk_4MiB_vs_v3"]
        t = row["chunk_4MiB_vs_1MiB"]
        counts = row["pause_counts"]
        lines.append(f"| {row['seed']} | {p['tpot_relative']:+.2%} | "
                     f"{p['common_tpot_relative']:+.2%} | {p['ttft_relative']:+.2%} | "
                     f"{p['throughput_relative']:+.2%} | {p['gpu_work_relative']:+.2%} | "
                     f"{v['tpot_relative']:+.2%} | {v['gpu_work_relative']:+.2%} | "
                     f"{t['tpot_relative']:+.2%} | "
                     f"{counts['chunk_4MiB']}/{counts['chunk_1MiB']} | "
                     f"{'通过' if decision['all_pass'] else '未通过'} |")
    lines += ["", f"逐种子三项联合门槛：{'全部通过' if passed else '未全部通过'}。",
              "完整请求级配对、完成率、积压、路径数、原始窗口与源码哈希见 `analysis.json`、`runs/` 和 `audit.json`。",
              "旧分块 hook 的 `treatment` 文本固定写着 `1MiB`，实际分块大小以每格的",
              "`chunk_bytes` 与协议为准；报告已核对 4 MiB 窗口实际值为 4194304 字节。",
              "分块与 MoLink 的既有思想相关；本表不构成新颖性或真实 GPU 集群收益证明。", ""]
    path = FORMAL / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

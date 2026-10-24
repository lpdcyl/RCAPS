"""Frozen fresh-seed screen for coarser slow-link chunk sizes."""

from __future__ import annotations

import json
from statistics import mean

from work3_chunk_size.run import AUDIT, HERE, PROTOCOL, digest, freeze, write
from work3_selective_chunk.formal_report import compare


def read(cell: str, seed: int) -> dict:
    path = HERE / "runs" / "development" / f"{cell}_seed{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def report() -> str:
    freeze()
    rows = []
    decisions = []
    gate = PROTOCOL["screen_each_seed_vs_gate"]
    for seed in PROTOCOL["development_seeds"]:
        base = read("gate", seed)
        if base["audit_sha256"] != digest(AUDIT):
            raise AssertionError("Base audit changed")
        for cell in PROTOCOL["cells"]:
            if cell == "gate":
                continue
            candidate = read(cell, seed)
            if candidate["audit_sha256"] != digest(AUDIT) or candidate["chunk_bytes"] != PROTOCOL["cells"][cell]:
                raise AssertionError("Candidate identity changed")
            result = compare(base, candidate)
            result.update({"cell": cell, "seed": seed,
                           "chunk_pauses": candidate["phase_link_profile"]["paused_chunks"],
                           "eligible_links": candidate["phase_link_profile"]["eligible_link_uids"]})
            rows.append(result)
            if cell in PROTOCOL["eligible_candidates"]:
                passed = (result["tpot_relative"] <= gate["tpot_p95_relative_max"]
                          and result["common_tpot_relative"] <= gate["common_completed_tpot_p95_relative_max"]
                          and result["ttft_relative"] <= gate["ttft_p95_relative_max"]
                          and result["throughput_relative"] >= gate["throughput_relative_min"]
                          and result["gpu_work_relative"] <= gate["gpu_seconds_per_token_relative_max"]
                          and result["completion_absolute"] >= gate["completion_fraction_absolute_min"])
                decisions.append({"cell": cell, "seed": seed, "passed": passed})
    eligible = []
    for cell in PROTOCOL["eligible_candidates"]:
        tests = [decision for decision in decisions if decision["cell"] == cell]
        if len(tests) != len(PROTOCOL["development_seeds"]):
            raise AssertionError("Candidate missing a paired seed")
        if all(test["passed"] for test in tests):
            eligible.append(cell)
    selected = (min(eligible, key=lambda cell: mean(row["common_tpot_relative"]
                                                   for row in rows if row["cell"] == cell))
                if eligible else None)
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "rows": rows, "decisions": decisions,
                "selected_for_held_out_test": selected,
                "status": "exploratory_development_only"}
    write(HERE / "analysis.json", analysis)
    lines = ["# 慢链路分块大小修订：新开发种子结果", "",
             "在 1 MiB 正式窗口暴露 GPU 工作护栏风险后，事前登记 2 MiB 和 4 MiB 两个候选；",
             "种子 151/152、各 300 秒，同放置与到达轨迹。1 MiB 是同种子参考，不参加选择。",
             "所有相对值均以未分块的稀疏门控为基线。", "",
             "| 种子 | 分块 | P95 TPOT | 共同完成 TPOT | P95 TTFT | 吞吐 | GPU 秒/token | 暂停数 | 筛选 |",
             "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        verdict = next((d["passed"] for d in decisions
                        if d["cell"] == row["cell"] and d["seed"] == row["seed"]), None)
        label = "参考" if verdict is None else ("通过" if verdict else "未通过")
        lines.append(f"| {row['seed']} | {row['cell']} | {row['tpot_relative']:+.2%} | "
                     f"{row['common_tpot_relative']:+.2%} | {row['ttft_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} | {row['gpu_work_relative']:+.2%} | "
                     f"{row['chunk_pauses']} | {label} |")
    lines += ["", f"进入新种子 1800 秒检验：{selected or '无'}。",
              "选择规则与历史发现时间写在 `protocol.json`；原始配对及审计哈希见 `analysis.json`。", ""]
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

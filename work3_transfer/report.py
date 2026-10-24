"""Verify paired traces and judge the registered short-window transfer gate."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def report():
    from work3_transfer.run import AUDIT, digest, freeze, write

    freeze()
    rows = []
    for case in PROTOCOL["cases"]:
        for seed in PROTOCOL["seeds"]:
            paths = {cell: HERE / "runs" / case / f"{cell}_seed{seed}.json"
                     for cell in PROTOCOL["methods"]}
            baseline, candidate = (json.loads(paths[cell].read_text(encoding="utf-8"))
                                   for cell in ("v3", "gated"))
            for item in (baseline, candidate):
                if item["audit_sha256"] != digest(AUDIT):
                    raise AssertionError("Audit mismatch")
            if (baseline["trace_sha256"] != candidate["trace_sha256"]
                    or baseline["arrivals"] != candidate["arrivals"]):
                raise AssertionError("Unpaired traces")
            qa, qb = baseline["query_samples"], candidate["query_samples"]
            common = [uid for uid in set(qa) & set(qb)
                      if qa[uid]["completed"] and qb[uid]["completed"]
                      and qa[uid].get("tpot_s") is not None
                      and qb[uid].get("tpot_s") is not None]
            if not common:
                raise ValueError("No common completed requests")
            ca = float(np.percentile([qa[uid]["tpot_s"] for uid in common], 95))
            cb = float(np.percentile([qb[uid]["tpot_s"] for uid in common], 95))
            rows.append({"case": case, "seed": seed,
                         "trace_sha256": baseline["trace_sha256"],
                         "arrivals": baseline["arrivals"],
                         "base_tpot_s": baseline["tpot_p95_s"],
                         "gated_tpot_s": candidate["tpot_p95_s"],
                         "tpot_relative": candidate["tpot_p95_s"] / baseline["tpot_p95_s"] - 1,
                         "throughput_relative":
                         candidate["output_throughput_tokens_per_s"] /
                         baseline["output_throughput_tokens_per_s"] - 1,
                         "ttft_relative": candidate["ttft_p95_s"] / baseline["ttft_p95_s"] - 1,
                         "common_n": len(common),
                         "common_tpot_relative": cb / ca - 1,
                         "completion_absolute": candidate["completion_fraction"] -
                         baseline["completion_fraction"],
                         "backlog_delta": candidate["backlog_at_window_end"] -
                         baseline["backlog_at_window_end"],
                         "base_route_count": len(baseline["route_counts"]),
                         "gated_route_count": len(candidate["route_counts"]),
                         "allowed_edges": candidate["allowed_edges"],
                         "base_sha256": digest(paths["v3"]),
                         "gated_sha256": digest(paths["gated"])})
    gate = PROTOCOL["gate"]
    for row in rows:
        bound = (gate["C2_tpot_relative_max_each_seed"] if row["case"] == "C2"
                 else gate["C3_tpot_relative_max_each_seed"])
        row["gate_passed"] = (row["tpot_relative"] <= bound
                              and row["throughput_relative"] >=
                              gate["throughput_relative_min_each_seed"]
                              and row["common_tpot_relative"] <=
                              gate["common_completed_tpot_relative_max_each_seed"])
    passed = all(row["gate_passed"] for row in rows)
    write(HERE / "analysis.json",
          {"rows": rows, "development_passed": passed,
           "gate": gate, "audit_sha256": digest(AUDIT)})
    lines = ["# 工作三路径空间规则：C2/C3 迁移开发检查", "",
             "沿用 C1 的 50 MB/s 规则；C2/C3 均没有慢规范边，因此候选是规范路径图。",
             "固定原有放置，V3 与候选使用相同到达轨迹；种子 124/125、300 秒、不排空。",
             "这是开发筛选，不是正式泛化结论。", "",
             "| 资源池 | 种子 | V3 TPOT | gated TPOT | TPOT 相对 | 吞吐相对 | 共同完成 TPOT 相对 | 路径数 | 判定 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['case']} | {row['seed']} | {row['base_tpot_s']:.4f} | "
                     f"{row['gated_tpot_s']:.4f} | {row['tpot_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} | "
                     f"{row['common_tpot_relative']:+.2%} | "
                     f"{row['base_route_count']}→{row['gated_route_count']} | "
                     f"{'通过' if row['gate_passed'] else '未通过'} |")
    lines += ["", f"预定迁移开发门槛：{'通过' if passed else '未通过'}。",
             "逐格原始 JSON、轨迹与审计哈希见 `runs/`、`analysis.json`、`audit.json`。", ""]
    output = HERE / "RESULTS_CN.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output

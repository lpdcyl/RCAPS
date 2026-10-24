"""Recalculate the paired development ablation and enforce the frozen screen."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def common_tpot(base: dict, candidate: dict) -> tuple[float, float, int]:
    a, b = base["query_samples"], candidate["query_samples"]
    ids = [uid for uid in a.keys() & b.keys()
           if a[uid]["completed"] and b[uid]["completed"]
           and a[uid].get("tpot_s") is not None and b[uid].get("tpot_s") is not None]
    if not ids:
        raise ValueError("No common-completed TPOT samples")
    return (float(np.percentile([a[uid]["tpot_s"] for uid in ids], 95)),
            float(np.percentile([b[uid]["tpot_s"] for uid in ids], 95)), len(ids))


def gpu_work(run: dict) -> float:
    return sum(run["gpu_busy_fraction"].values()) / run["output_throughput_tokens_per_s"]


def ratio(candidate: float, base: float) -> float:
    return candidate / base - 1


def report() -> str:
    from work3_detour_ablation.run import AUDIT, digest, freeze, write

    freeze()
    pairs = []
    parity = []
    candidates = [tuple(edge) for edge in PROTOCOL["detours_from_frozen_audit"]]
    for seed in PROTOCOL["seeds"]:
        baseline = read(HERE / "runs" / "development" / f"unchanged_seed{seed}.json")
        historic = read(ROOT / "work3_link_price" / "runs" / "v1" / "development" /
                        "C1_multi" / f"gated_seed{seed}.json")
        parity_keys = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s",
                       "ttft_p95_s", "tpot_p95_s", "completion_fraction",
                       "backlog_at_window_end", "route_counts", "query_samples",
                       "gpu_busy_fraction")
        if not all(baseline[key] == historic[key] for key in parity_keys):
            raise AssertionError(f"Unchanged-gate source parity failed: seed {seed}")
        parity.append(seed)
        if baseline["audit_sha256"] != digest(AUDIT):
            raise AssertionError("Baseline audit mismatch")
        for edge in candidates:
            label = f"without_{edge[0]}_{edge[1]}"
            candidate = read(HERE / "runs" / "development" / f"{label}_seed{seed}.json")
            if candidate["audit_sha256"] != digest(AUDIT):
                raise AssertionError("Candidate audit mismatch")
            if (baseline["trace_sha256"] != candidate["trace_sha256"] or
                    baseline["arrivals"] != candidate["arrivals"]):
                raise AssertionError("Paired arrival trace changed")
            if candidate["excluded_edge"] != list(edge):
                raise AssertionError("Wrong excluded edge")
            common_base, common_candidate, n = common_tpot(baseline, candidate)
            pairs.append({"seed": seed, "excluded_edge": list(edge),
                          "tpot_relative": ratio(candidate["tpot_p95_s"], baseline["tpot_p95_s"]),
                          "common_tpot_relative": ratio(common_candidate, common_base),
                          "ttft_relative": ratio(candidate["ttft_p95_s"], baseline["ttft_p95_s"]),
                          "throughput_relative": ratio(candidate["output_throughput_tokens_per_s"],
                                                       baseline["output_throughput_tokens_per_s"]),
                          "gpu_work_relative": ratio(gpu_work(candidate), gpu_work(baseline)),
                          "completion_absolute": candidate["completion_fraction"] - baseline["completion_fraction"],
                          "common_completed_n": n,
                          "route_count_base": len(baseline["route_counts"]),
                          "route_count_candidate": len(candidate["route_counts"]),
                          "allowed_edges": candidate["allowed_edges"]})
    decisions = []
    for edge in candidates:
        rows = [row for row in pairs if row["excluded_edge"] == list(edge)]
        means = {key: float(np.mean([row[key] for row in rows])) for key in
                 ("tpot_relative", "common_tpot_relative", "ttft_relative",
                  "throughput_relative", "gpu_work_relative", "completion_absolute")}
        merits_test = (means["tpot_relative"] < 0 and means["common_tpot_relative"] < 0
                       and means["throughput_relative"] >= -0.005
                       and means["gpu_work_relative"] <= 0.10)
        decisions.append({"excluded_edge": list(edge), "means": means,
                          "merits_held_out_test": merits_test})
    passed = [row for row in decisions if row["merits_held_out_test"]]
    selected = (min(passed, key=lambda row: row["means"]["common_tpot_relative"])
                if passed else None)
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "unchanged_gate_parity_seeds": parity, "pairs": pairs,
                "decisions": decisions,
                "selected_for_held_out_test": selected["excluded_edge"] if selected else None,
                "status": "exploratory_development_only"}
    write(HERE / "analysis.json", analysis)
    lines = ["# C1 三集群四条高速绕行边：单边消融开发结果", "",
             "固定 300 秒窗口、种子 121/122、相同布局和到达轨迹；未移除边的实现与原门控逐项一致。",
             "这是筛选实验，不能单独证明新方法收益。所有百分比均相对原门控，按种子算相对值后取均值。", "",
             "| 移除边 | P95 TPOT | 共同完成 TPOT | P95 TTFT | 吞吐 | GPU 秒/token | 进入未见种子检验 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in decisions:
        m = row["means"]
        lines.append(f"| {row['excluded_edge'][0]}→{row['excluded_edge'][1]} | "
                     f"{m['tpot_relative']:+.2%} | {m['common_tpot_relative']:+.2%} | "
                     f"{m['ttft_relative']:+.2%} | {m['throughput_relative']:+.2%} | "
                     f"{m['gpu_work_relative']:+.2%} | "
                     f"{'是' if row['merits_held_out_test'] else '否'} |")
    lines += ["", "逐种子数值、共同完成请求数、路径数和审核哈希见 `analysis.json`。",
              "筛选规则已在运行前冻结于 `protocol.json`；若有候选，需另用未见种子和完整窗口验证。", ""]
    if selected:
        lines.append(f"开发筛选选择移除 {selected['excluded_edge'][0]}→{selected['excluded_edge'][1]}。")
    else:
        lines.append("四个单边移除候选均未满足预定筛选规则；停止这一改动方向。")
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)

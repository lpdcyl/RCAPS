"""Independent raw-result checks and preregistered development verdict."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))


def read(phase: str, case: str, cell: str, seed: int) -> dict:
    path = HERE / "runs" / "v1" / phase / case / f"{cell}_seed{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def relative(candidate: float, baseline: float) -> float:
    return candidate / baseline - 1


def common_completed_tpot(a: dict, b: dict) -> tuple[float, float, int]:
    qa, qb = a["query_samples"], b["query_samples"]
    common = sorted(set(qa) & set(qb), key=int)
    common = [uid for uid in common if qa[uid]["completed"] and qb[uid]["completed"]
              and qa[uid].get("tpot_s") is not None
              and qb[uid].get("tpot_s") is not None]
    if not common:
        raise ValueError("No common completed requests with TPOT")
    return (float(np.percentile([qa[uid]["tpot_s"] for uid in common], 95)),
            float(np.percentile([qb[uid]["tpot_s"] for uid in common], 95)),
            len(common))


def compare(base: dict, candidate: dict) -> dict:
    if base["trace_sha256"] != candidate["trace_sha256"]:
        raise AssertionError("Different arrival traces")
    if base["arrivals"] != candidate["arrivals"]:
        raise AssertionError("Different arrival counts")
    if base["audit_sha256"] != candidate["audit_sha256"]:
        raise AssertionError("Different registered code")
    cbase, ccandidate, n = common_completed_tpot(base, candidate)
    return {
        "trace_sha256": base["trace_sha256"],
        "arrivals": base["arrivals"],
        "tpot_base_s": base["tpot_p95_s"],
        "tpot_candidate_s": candidate["tpot_p95_s"],
        "tpot_relative": relative(candidate["tpot_p95_s"], base["tpot_p95_s"]),
        "throughput_base": base["output_throughput_tokens_per_s"],
        "throughput_candidate": candidate["output_throughput_tokens_per_s"],
        "throughput_relative": relative(candidate["output_throughput_tokens_per_s"],
                                        base["output_throughput_tokens_per_s"]),
        "ttft_relative": relative(candidate["ttft_p95_s"], base["ttft_p95_s"]),
        "completion_absolute": candidate["completion_fraction"] - base["completion_fraction"],
        "common_completed_n": n,
        "common_completed_tpot_base_s": cbase,
        "common_completed_tpot_candidate_s": ccandidate,
        "common_completed_tpot_relative": relative(ccandidate, cbase),
        "route_count_base": len(base["route_counts"]),
        "route_count_candidate": len(candidate["route_counts"]),
        "backlog_base": base["backlog_at_window_end"],
        "backlog_candidate": candidate["backlog_at_window_end"],
        "evaluated_positive_link_prices": candidate.get("link_price_count", 0),
    }


def report() -> str:
    from work3_link_price.run import check_frozen, digest, AUDIT, write

    check_frozen()
    checks = []
    for case in PROTOCOL["topologies"]:
        seed = PROTOCOL["smoke_seed"]
        base = read("smoke", case, "gated", seed)
        off = read("smoke", case, "priced_off", seed)
        priced = read("smoke", case, "priced", seed)
        parity_fields = ("trace_sha256", "output_throughput_tokens_per_s",
                         "ttft_p95_s", "tpot_p95_s", "completion_fraction",
                         "backlog_at_window_end", "route_counts", "query_samples")
        identical = all(base[key] == off[key] for key in parity_fields)
        if not identical:
            raise AssertionError(f"Switch-off source parity failed: {case}")
        if priced["trace_sha256"] != base["trace_sha256"]:
            raise AssertionError(f"Smoke trace mismatch: {case}")
        checks.append({"case": case, "switch_off_parity": identical,
                       "price_evaluations": priced["link_price_count"]})

    pairs = []
    gates = []
    for seed in PROTOCOL["development_seeds"]:
        for case in PROTOCOL["topologies"]:
            base = read("development", case, "gated", seed)
            priced = read("development", case, "priced", seed)
            for row in (base, priced):
                if row["audit_sha256"] != digest(AUDIT):
                    raise AssertionError("Result audit mismatch")
            result = compare(base, priced)
            result.update({"seed": seed, "case": case, "control": "gated",
                           "candidate": "priced"})
            if case == "C1_multi":
                reference = read("development", case, "v3", seed)
                result["v3_tpot_s"] = reference["tpot_p95_s"]
                result["v3_throughput"] = reference["output_throughput_tokens_per_s"]
                if reference["trace_sha256"] != result["trace_sha256"]:
                    raise AssertionError("V3 reference trace mismatch")
                rule = PROTOCOL["primary_gate"]
                passed = (result["tpot_relative"] <= rule["tpot_p95_relative_max_each_seed"]
                          and result["throughput_relative"] >= rule["throughput_relative_min_each_seed"]
                          and result["ttft_relative"] <= rule["ttft_p95_relative_max_each_seed"]
                          and result["completion_absolute"] >= rule["completion_fraction_absolute_min_each_seed"]
                          and result["common_completed_tpot_relative"] <=
                          rule["common_completed_tpot_p95_relative_max_each_seed"])
                gates.append(passed)
            else:
                rule = PROTOCOL["single_cluster_safety"]
                passed = (result["tpot_relative"] <= rule["tpot_p95_relative_max_each_seed"]
                          and result["throughput_relative"] >= rule["throughput_relative_min_each_seed"])
                gates.append(passed)
            result["gate_passed"] = passed
            pairs.append(result)

    data = {"protocol": PROTOCOL, "smoke_checks": checks, "pairs": pairs,
            "development_passed": all(gates), "all_windows_valid": True,
            "interpretation": ("Formal validation may be registered separately" if all(gates)
                               else "Stop; do not tune on these seeds or claim closure")}
    write(HERE / "runs" / "v1" / "development_analysis.json", data)
    lines = ["# 工作三：入场时链路干扰价格开发结果", "",
             "固定稀疏 DAG 与 V3 路由价格，只新增无拟合参数的 Prompt 对现有 Decode 链路阻塞价格。",
             "同一布局、到达轨迹和种子；300 秒固定窗口，不排空。以下为离散事件仿真。", "",
             f"关闭价格的源码/行为一致性：{len(checks)}/{len(checks)}；"
             f"主判定：{'通过' if all(gates) else '未通过'}。", "",
             "| 拓扑 | 种子 | gated TPOT | priced TPOT | TPOT 相对 | 吞吐相对 | TTFT 相对 | 共同完成 TPOT 相对 | 判定 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in pairs:
        lines.append(f"| {row['case']} | {row['seed']} | {row['tpot_base_s']:.4f} | "
                     f"{row['tpot_candidate_s']:.4f} | {row['tpot_relative']:+.2%} | "
                     f"{row['throughput_relative']:+.2%} | {row['ttft_relative']:+.2%} | "
                     f"{row['common_completed_tpot_relative']:+.2%} | "
                     f"{'通过' if row['gate_passed'] else '未通过'} |")
    lines += ["", "开发门槛见 `protocol.json`；每个种子均须满足。逐窗口原始结果、轨迹哈希、共同完成请求数与审计哈希见 `runs/v1/`。", ""]
    (HERE / "runs" / "v1" / "development_RESULTS_CN.md").write_text(
        "\n".join(lines), encoding="utf-8")
    return str(HERE / "runs" / "v1" / "development_RESULTS_CN.md")

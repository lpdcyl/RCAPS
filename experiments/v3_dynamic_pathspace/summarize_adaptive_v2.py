"""Validate and summarize the registered adaptive path-control formal windows."""
from __future__ import annotations
import json
from pathlib import Path
from statistics import mean
from experiments.v3_cycle_pricing.run import ROOT, write

HERE = Path(__file__).resolve().parent
PHASE = "formal_adaptive"
CONDITIONS = ("C1_single", "C1_multi")
SEEDS = (0, 1, 2)
CELLS = ("static", "adaptive_link")


def load_row(condition: str, cell: str, seed: int) -> dict:
    path = HERE / "runs" / PHASE / condition / f"{cell}_seed{seed}.json"
    if not path.exists():
        raise SystemExit(f"Missing formal result: {path}")
    row = json.loads(path.read_text(encoding="utf-8"))
    expected = {"condition": condition, "cell": cell, "seed": seed,
                "duration_s": 1800, "pythonhashseed": "0"}
    for key, value in expected.items():
        if row.get(key) != value:
            raise SystemExit(f"Identity mismatch {path}: {key}={row.get(key)!r}, expected {value!r}")
    if row["arrivals"] != len(row["query_samples"]):
        raise SystemExit(f"Incomplete query samples: {path}")
    capacities = row["kv_capacity"]
    peaks = row["kv_peak_reserved"]
    if any(peaks.get(uid, 0) > cap for uid, cap in capacities.items()):
        raise SystemExit(f"KV reservation exceeds capacity: {path}")
    expected_gpu = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
    if abs(expected_gpu - row["gpu_seconds_per_output_token"]) > 1e-10:
        raise SystemExit(f"GPU-seconds/token mismatch: {path}")
    return row


def metrics(row: dict) -> dict:
    throughput = row["output_throughput_tokens_per_s"]
    duration = row["duration_s"]
    arrivals = row["arrivals"]
    gate = row.get("gate_counts", {})
    return {
        "arrivals": arrivals,
        "completion_fraction": row["completion_fraction"],
        "backlog_at_window_end": row["backlog_at_window_end"],
        "throughput_tokens_s": throughput,
        "ttft_p95_s": row["ttft_p95_s"],
        "tpot_p95_s": row["tpot_p95_s"],
        "e2e_p95_s": row["e2e_p95_s"],
        "mean_decode_batch": row["decode_batches"]["mean_batch"],
        "single_decode_share": row["decode_batches"]["single_share"],
        "gpu_seconds_per_output_token": row["gpu_seconds_per_output_token"],
        "link_service_seconds_per_output_token": sum(row["link_service_request_s"].values()) / (throughput * duration),
        "dispatch_wait_seconds_per_arrival": sum(row["link_dispatch_wait_request_s"].values()) / arrivals,
        "max_link_occupied_fraction": max(row["link_occupied_fraction"].values(), default=0.0),
        "routes_used": len(row["route_counts"]),
        "selected_extra_edges": gate.get("dynamic_selected", 0),
        "admitted_dynamic_edges": gate.get("dynamic_admitted", 0),
        "candidate_edge_checks": gate.get("candidate_checks", 0),
        "minimum_relief_vetoed": gate.get("minimum_relief_vetoed", 0),
        "kv_admitted": row["kv_admission"]["admitted"],
        "kv_deferred_checks": row["kv_admission"]["deferred_checks"],
        "kv_peak_reserved_fraction": row["kv_peak_fraction"],
        "kv_minimum_headroom": row["kv_admission"]["minimum_headroom"],
        "trace_sha256": row["trace_sha256"],
        "solution_sha256": row["solution_sha256"],
        "sim_cluster_sha256": row["sim_cluster_sha256"],
        "physical_sha256": row["physical_sha256"],
        "scheduler_sha256": row["scheduler_sha256"],
    }


def build() -> dict:
    out = {"experiment": "v3_dynamic_pathspace_adaptive_link_deadband_v2",
           "seeds": list(SEEDS), "duration_s": 1800, "pythonhashseed": "0",
           "pairs": {}, "paired_delta": {}, "means": {}}
    for condition in CONDITIONS:
        pairs = []
        records = []
        for seed in SEEDS:
            rows = {cell: load_row(condition, cell, seed) for cell in CELLS}
            static, adaptive = rows["static"], rows["adaptive_link"]
            for key in ("trace_sha256", "solution_sha256", "sim_cluster_sha256", "physical_sha256"):
                if static[key] != adaptive[key]:
                    raise SystemExit(f"Pair mismatch for {condition} seed {seed}: {key}")
            if (static["python_version"], static["numpy_version"]) != (adaptive["python_version"], adaptive["numpy_version"]):
                raise SystemExit(f"Environment mismatch for {condition} seed {seed}")
            sm, am = metrics(static), metrics(adaptive)
            record = {"seed": seed, "static": sm, "adaptive_link": am,
                      "delta": {
                          "throughput_pct": (am["throughput_tokens_s"] / sm["throughput_tokens_s"] - 1) * 100,
                          "tpot_p95_pct": (am["tpot_p95_s"] / sm["tpot_p95_s"] - 1) * 100,
                          "ttft_p95_pct": (am["ttft_p95_s"] / sm["ttft_p95_s"] - 1) * 100,
                          "e2e_p95_pct": (am["e2e_p95_s"] / sm["e2e_p95_s"] - 1) * 100,
                          "gpu_seconds_per_output_token_pct": (am["gpu_seconds_per_output_token"] / sm["gpu_seconds_per_output_token"] - 1) * 100,
                          "link_service_seconds_per_output_token_pct": (am["link_service_seconds_per_output_token"] / sm["link_service_seconds_per_output_token"] - 1) * 100,
                          "dispatch_wait_seconds_per_arrival_pct": (am["dispatch_wait_seconds_per_arrival"] / sm["dispatch_wait_seconds_per_arrival"] - 1) * 100 if sm["dispatch_wait_seconds_per_arrival"] else None,
                      }}
            records.append(record)
            pairs.append(record)
        out["pairs"][condition] = pairs
        metric_names = ("throughput_tokens_s", "ttft_p95_s", "tpot_p95_s", "e2e_p95_s",
                        "mean_decode_batch", "single_decode_share", "gpu_seconds_per_output_token",
                        "link_service_seconds_per_output_token", "dispatch_wait_seconds_per_arrival",
                        "max_link_occupied_fraction", "selected_extra_edges", "admitted_dynamic_edges",
                        "kv_admitted", "kv_deferred_checks", "kv_peak_reserved_fraction")
        means = {}
        for cell in CELLS:
            means[cell] = {metric: mean(rec[cell][metric] for rec in records) for metric in metric_names}
        deltas = {metric: mean(rec["delta"][metric] for rec in records if rec["delta"][metric] is not None)
                  for metric in ("throughput_pct", "ttft_p95_pct", "tpot_p95_pct", "e2e_p95_pct",
                                 "gpu_seconds_per_output_token_pct", "link_service_seconds_per_output_token_pct",
                                 "dispatch_wait_seconds_per_arrival_pct")}
        out["means"][condition] = means
        out["paired_delta"][condition] = deltas
    return out


def fmt(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def markdown(report: dict) -> str:
    lines = ["# 工作三动态路径控制：正式结果 V2", "",
             "正式窗口采用 seed 0、1、2，每个窗口 1800 秒，Python hash seed 为 0；每个 seed 中 static 与 adaptive 使用相同请求轨迹、布局、物理拓扑和软件环境。结果是三种子描述性汇总，不表示统计显著性。开发阶段 seed 102 通过预设进入正式实验门槛。", "",
             "## 逐 seed 配对结果", "",
             "| 条件 | Seed | 静态吞吐 (token/s) | 自适应吞吐 (token/s) | 吞吐变化 | 静态 P95 TPOT (s) | 自适应 P95 TPOT (s) | TPOT 变化 | 动态边准入/选中 | KV 峰值占用 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for condition in CONDITIONS:
        for rec in report["pairs"][condition]:
            s, a, d = rec["static"], rec["adaptive_link"], rec["delta"]
            lines.append(f"| {condition} | {rec['seed']} | {fmt(s['throughput_tokens_s'])} | {fmt(a['throughput_tokens_s'])} | {fmt(d['throughput_pct'])}% | {fmt(s['tpot_p95_s'])} | {fmt(a['tpot_p95_s'])} | {fmt(d['tpot_p95_pct'])}% | {a['admitted_dynamic_edges']}/{a['selected_extra_edges']} | {fmt(a['kv_peak_reserved_fraction']*100, 1)}% |")
    lines += ["", "## 三种子均值与机制量", "", "| 条件 | 方法 | 吞吐 (token/s) | P95 TTFT (s) | P95 TPOT (s) | Decode 平均批大小 | GPU 秒/token | 链路服务秒/token | 每请求链路派发等待 (s) |"]
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for condition in CONDITIONS:
        for cell, label in (("static", "static"), ("adaptive_link", "adaptive")):
            m=report["means"][condition][cell]
            lines.append(f"| {condition} | {label} | {fmt(m['throughput_tokens_s'])} | {fmt(m['ttft_p95_s'])} | {fmt(m['tpot_p95_s'])} | {fmt(m['mean_decode_batch'])} | {fmt(m['gpu_seconds_per_output_token'])} | {fmt(m['link_service_seconds_per_output_token'])} | {fmt(m['dispatch_wait_seconds_per_arrival'])} |")
    lines += ["", "## 机制解释", "", "动态控制器按 prompt 到达时的链路释放压力更新额外候选边集合；静态规范边和既定慢链路绕行边始终可用，M3 的路径代价排序保持冻结。正式结果据此检查三件事：候选边是否真正准入并被路由选中；吞吐/TPOT变化是否与 decode 批次和链路服务/排队变化一致；KV 生命周期预约是否保持容量安全。表中动态边准入与选中分别统计，准入不等同于采用。", "",
             "每个窗口另保留逐 GPU KV 峰值、容量、headroom、decode 批次分布、逐链路服务/派发等待、路线计数、轨迹与部署哈希；复算 JSON 保存这些窗口的摘要和校验哈希。", "",
             "## 判定", "", "根据三种子的逐 seed 配对结果报告效果方向和波动；不把三个 seed 的均值写成显著性结论。若任一 pair 的 trace 或部署哈希不一致、采样数不完整或 KV 预约超容量，复算器会中止。", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    result = build()
    write(HERE / "analysis_adaptive_v2.json", result)
    (HERE / "RESULTS_ADAPTIVE_V2_CN.md").write_text(markdown(result), encoding="utf-8")
    print(HERE / "RESULTS_ADAPTIVE_V2_CN.md")

"""Strict same-seed no-op parity check outside the slow-link C1 multi case."""

from __future__ import annotations

import json

from work3_chunk_safety.run import AUDIT, HERE, PROTOCOL, digest, freeze, write


def read(case: str, cell: str) -> dict:
    path = HERE / "runs" / case / f"{cell}_seed{PROTOCOL['seed']}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def report() -> str:
    freeze()
    fields = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s",
              "ttft_p95_s", "tpot_p95_s", "completion_fraction",
              "backlog_at_window_end", "route_counts", "query_samples",
              "gpu_busy_fraction")
    rows = []
    for case in PROTOCOL["cases"]:
        base = read(case, "gate")
        candidate = read(case, "chunk_4MiB")
        if base["audit_sha256"] != digest(AUDIT) or candidate["audit_sha256"] != digest(AUDIT):
            raise AssertionError("Safety audit differs")
        differences = [field for field in fields if base[field] != candidate[field]]
        paused = candidate["phase_link_profile"]["paused_chunks"]
        if differences or paused or base["allowed_edges"] != candidate["allowed_edges"]:
            raise AssertionError(f"No-op safety parity failed: {case}, {differences}, pauses={paused}")
        rows.append({"case": case, "allowed_edges": base["allowed_edges"],
                     "exact_fields": list(fields), "paused_chunks": paused,
                     "instrumented_slow_links": len(candidate["phase_link_profile"]["eligible_link_uids"]),
                     "passed": True})
    analysis = {"protocol": PROTOCOL, "audit_sha256": digest(AUDIT),
                "rows": rows, "safety_parity_passed": True,
                "status": "smoke_safety_only"}
    write(HERE / "analysis.json", analysis)
    lines = ["# 4 MiB 慢链路分块：其他资源池无作用烟测", "",
             "C1 单集群、C2、C3 在当前稀疏门控准入边集上没有慢计算链路需要分块。",
             "每池使用未见种子 311、60 秒固定窗口，比较门控与安装 4 MiB 慢链路 hook 的结果。",
             "这是行为安全烟测，不是新的长窗口性能证明。", "",
             "| 资源池 | 准入边 | 安装的物理慢链路 | 实际暂停分块 | 请求、路由、延迟、吞吐、GPU 完全一致 |",
             "| --- | ---: | ---: | ---: | --- |"]
    for row in rows:
        lines.append(f"| {row['case']} | {row['allowed_edges']} | "
                     f"{row['instrumented_slow_links']} | {row['paused_chunks']} | 是 |")
    lines += ["", "完整逐字段比对、原始窗口和审计哈希见 `analysis.json`、`runs/`、`audit.json`。", ""]
    path = HERE / "RESULTS_CN.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

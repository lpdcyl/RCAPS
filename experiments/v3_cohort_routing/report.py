"""Development-window report for decode-cohort pricing."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.v3_cycle_pricing.run import CASES, ROOT, digest, read, rel

HERE = Path(__file__).resolve().parent
CONTROL = ROOT / "experiments/v3_cycle_pricing/runs"


def batch_of(row: dict, case: str, cell: str) -> dict:
    if "decode_batches" in row:
        return row["decode_batches"]
    probe = CONTROL / "batch" / case / f"{cell}_seed100.json"
    if probe.exists():
        data = read(probe)
        return {"mean_batch": data["mean_decode_batch"], "single_share": data["single_decode_share"]}
    return {}


def dev_rows(cells: list[tuple[str, Path]]) -> tuple[list[str], dict]:
    """Seed-100 rows relative to frozen V3 on the same trace."""
    lines = ["| 拓扑 | 方法 | 吞吐 | 相对 V3 | P95 TTFT | P95 TPOT | TPOT 相对 V3 | 平均 Decode 批 | 单请求批占比 | 实际路径数 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    data = {}
    for case in CASES:
        base = read(CONTROL / "dev" / case / "v3_seed100.json")
        table = [("v3", CONTROL / "dev" / case / "v3_seed100.json"),
                 ("canonical", CONTROL / "dev" / case / "canonical_seed100.json")]
        table += [(cell, path.parent.parent / case / path.name) for cell, path in cells]
        for cell, path in table:
            row = read(path)
            if row["trace_sha256"] != base["trace_sha256"]:
                raise ValueError(f"Trace mismatch: {path}")
            batch = batch_of(row, case, cell)
            tp = row["output_throughput_tokens_per_s"] / base["output_throughput_tokens_per_s"] - 1
            tpot = row["tpot_p95_s"] / base["tpot_p95_s"] - 1
            data[f"{case}/{cell}"] = {"source": rel(path), "sha256": digest(path),
                                      "relative_throughput": tp, "relative_tpot_p95": tpot,
                                      "ttft_p95_s": row["ttft_p95_s"], "tpot_p95_s": row["tpot_p95_s"],
                                      **batch}
            mb = f"{batch['mean_batch']:.2f}" if batch else "—"
            ss = f"{batch['single_share']:.3f}" if batch else "—"
            lines.append(f"| {case} | {cell} | {row['output_throughput_tokens_per_s']:.2f} | {tp:+.2%} | "
                         f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | {tpot:+.2%} | {mb} | {ss} | "
                         f"{len(row['route_counts'])} |")
    return lines, data


def main() -> None:
    lines, data = dev_rows([("step", HERE / "runs/dev/x/step_seed100.json"),
                            ("lifetime", HERE / "runs/dev/x/lifetime_seed100.json")])
    parity = []
    for case in CASES:
        a = read(HERE / "runs/parity" / case / "v3.json")
        b = read(HERE / "runs/parity" / case / "zero.json")
        fields = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                  "completion_fraction", "route_counts", "query_samples", "trace_sha256")
        parity.append({"case": case, "identical": all(a[f] == b[f] for f in fields)})
    eligible = {cell: all(data[f"{c}/{cell}"]["relative_throughput"] >= -0.005 for c in CASES)
                for cell in ("step", "lifetime")}
    score = {cell: max(data[f"{c}/{cell}"]["relative_tpot_p95"] for c in CASES)
             for cell in ("step", "lifetime")}
    choice = min((c for c in score if eligible[c]), key=score.get, default=None)
    go = choice is not None and score[choice] < 0
    out = ["# V3 M3 Decode 批次队列定价：开发阶段", "",
           "规则见 `protocol_dev.json`（先于开发窗口提交）。种子 100、300 秒；对照为同轨迹的冻结 V3 与规范路径窗口"
           "（`experiments/v3_cycle_pricing/runs/dev/`）。批大小来自被动探针。", "",
           "零系数一致性：" + "；".join(f"{p['case']} {'逐项相同' if p['identical'] else '不同'}" for p in parity), ""]
    out += lines
    out += ["", "## 预注册选择", "",
            f"- 可选（两拓扑吞吐相对 V3 ≥ −0.5%）：step {'是' if eligible['step'] else '否'}，"
            f"lifetime {'是' if eligible['lifetime'] else '否'}",
            f"- 两拓扑最差 P95 TPOT 相对变化：step {score['step']:+.2%}，lifetime {score['lifetime']:+.2%}",
            f"- 结论：**{'进入正式窗口：' + choice if go else '没有变体满足条件，停止，不跑正式窗口'}**", "",
            "## 解读", "",
            "- lifetime（按 154 个 Decode token 计开辟代价）把全部流量压到一条路径：批大小显著变大，"
            "但吞吐下降约 25%、TPOT 大幅上升。批凝聚不能以放弃负载分摊为代价。",
            "- step（按 1 个 token 计）在单集群小幅改善，在三集群 TPOT 变差。"
            "单一标量系数无法同时满足两种拓扑：单集群受批碎片化限制，三集群受慢链路限制。",
            "- 这一负结果直接导出 `experiments/v3_gated_pathspace/` 的按慢链路门控路径准入。"]
    (HERE / "analysis.json").write_text(json.dumps(
        {"dev": data, "parity": parity, "eligible": eligible, "worst_tpot": score,
         "selected": choice if go else None}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()

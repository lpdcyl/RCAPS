"""Paired report for full-cycle session pricing against frozen V3."""

from __future__ import annotations

import json
from collections import defaultdict
from statistics import mean, stdev

from experiments.v3_cycle_pricing.run import (
    CANONICAL, CASES, DEV_SEED, FORMAL_SEEDS, HERE, PARITY_FIELDS, RELEASED,
    ROOT, digest, read, rel)

METRICS = (("output_throughput_tokens_per_s", "吞吐 token/s"),
           ("ttft_p95_s", "P95 TTFT s"), ("tpot_p95_s", "P95 TPOT s"),
           ("completion_fraction", "完成率"), ("backlog_at_window_end", "末端积压"))


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))] if ordered else float("nan")


def hop_profile(row: dict) -> dict:
    hops = row.get("route_hops", {})
    if not hops:
        return {}
    samples = row["query_samples"]
    by_partial = defaultdict(list)
    for uid, record in hops.items():
        sample = samples.get(uid)
        if sample and sample.get("tpot_s") is not None:
            by_partial[min(record["partial_hops"], 2)].append(sample["tpot_s"])
    return {"requests": len(hops),
            "mean_hops": mean(r["hops"] for r in hops.values()),
            "mean_partial_hops": mean(r["partial_hops"] for r in hops.values()),
            "partial_share": mean(r["partial_hops"] > 0 for r in hops.values()),
            "tpot_by_partial_hops": {
                ("2+" if k == 2 else str(k)): {"n": len(v), "mean_s": mean(v), "p95_s": p95(v)}
                for k, v in sorted(by_partial.items())}}


def common_p95(left: dict, right: dict, field: str) -> tuple[int, float, float]:
    shared = [uid for uid, sample in left["query_samples"].items()
              if sample.get("completed") and right["query_samples"].get(uid, {}).get("completed")]
    a = [left["query_samples"][u][field] for u in shared if left["query_samples"][u][field] is not None]
    b = [right["query_samples"][u][field] for u in shared if right["query_samples"][u][field] is not None]
    return len(shared), p95(a), p95(b)


def summary(values: list[float]) -> str:
    if len(values) < 2:
        return f"{values[0]:+.4f}" if values else "—"
    return f"{mean(values):+.4f} ± {stdev(values):.4f}"


def main() -> None:
    protocol = read(HERE / "protocol.json")
    analysis = {"protocol_sha256": digest(HERE / "protocol.json"),
                "scheduler_sha256": digest(HERE / "scheduler.py"),
                "dev": {}, "formal": {}, "parity": [], "inputs": {}}
    lines = ["# V3 M3 全周期会话定价：闭环验证", "",
             "协议与判定规则见 `protocol.json`（先于正式窗口提交）。"
             "差值一律为右侧减左侧；吞吐、完成率正值较好，TTFT、TPOT、积压负值较好。"
             "三个种子只描述方向与波动，不作显著性检验。", ""]

    # Development mechanism check (seed 100, 300 s).
    lines += ["## 开发种子 100（300 秒）：机制检查，不参与判定", "",
              "| 拓扑 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 平均跳数 | 含部分段跳的请求比例 | 平均部分段跳数 |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in CASES:
        for cell in ("canonical", "v3", "cycle"):
            path = HERE / "runs/dev" / case / f"{cell}_seed{DEV_SEED}.json"
            if not path.exists():
                continue
            row = read(path)
            hop = hop_profile(row)
            analysis["dev"][f"{case}/{cell}"] = {
                "source": rel(path), "sha256": digest(path),
                **{k: row[k] for k, _ in METRICS}, "hops": hop}
            lines.append(f"| {case} | {cell} | {row['output_throughput_tokens_per_s']:.3f} | "
                         f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                         f"{hop['mean_hops']:.3f} | {hop['partial_share']:.3f} | "
                         f"{hop['mean_partial_hops']:.3f} |")
    lines += ["", "### 同一窗口内：按部分段跳数分组的请求 TPOT（冻结 V3）", "",
              "| 拓扑 | 部分段跳数 | 请求数 | 平均 TPOT s | P95 TPOT s |",
              "| --- | --- | ---: | ---: | ---: |"]
    for case in CASES:
        hop = analysis["dev"].get(f"{case}/v3", {}).get("hops", {})
        for k, v in hop.get("tpot_by_partial_hops", {}).items():
            lines.append(f"| {case} | {k} | {v['n']} | {v['mean_s']:.4f} | {v['p95_s']:.4f} |")

    # Formal windows.
    deltas = defaultdict(lambda: defaultdict(list))
    rows = {}
    for case in CASES:
        for seed in FORMAL_SEEDS:
            released = ROOT / RELEASED[case].format(seed=seed)
            canonical = ROOT / CANONICAL.format(case=case, seed=seed)
            cand_path = HERE / "runs/formal" / case / f"cycle_seed{seed}.json"
            rerun_path = HERE / "runs/formal" / case / f"v3_seed{seed}.json"
            if not cand_path.exists():
                continue
            for p in (released, canonical):
                analysis["inputs"][rel(p)] = digest(p)
            v3, can, cand = read(released), read(canonical), read(cand_path)
            if not (v3["trace_sha256"] == can["trace_sha256"] == cand["trace_sha256"]):
                raise ValueError(f"Trace mismatch {case}/{seed}")
            rerun = read(rerun_path) if rerun_path.exists() else None
            if rerun is not None:
                diffs = [f for f in PARITY_FIELDS if rerun[f] != v3[f]]
                analysis["parity"].append({"case": case, "seed": seed,
                                           "rerun": rel(rerun_path),
                                           "released": rel(released),
                                           "status": "identical" if not diffs else "different",
                                           "different_fields": diffs})
            rows[(case, seed)] = {"canonical": can, "v3": v3, "cycle": cand,
                                  "v3_hops": hop_profile(rerun) if rerun else {},
                                  "cycle_hops": hop_profile(cand)}
            for key, _ in METRICS:
                deltas[case][f"cycle-v3/{key}"].append(cand[key] - v3[key])
                deltas[case][f"cycle-canonical/{key}"].append(cand[key] - can[key])
                deltas[case][f"v3-canonical/{key}"].append(v3[key] - can[key])
            for field in ("ttft_s", "tpot_s"):
                n, a, b = common_p95(v3, cand, field)
                deltas[case][f"common/{field}"].append(b - a)
            deltas[case]["common/n"].append(n)

    lines += ["", "## 正式窗口（种子 0/1/2，1800 秒，零预热，不排空）", ""]
    if analysis["parity"]:
        same = sum(p["status"] == "identical" for p in analysis["parity"])
        lines += [f"本环境重跑冻结 V3：{same}/{len(analysis['parity'])} 个窗口在 "
                  f"{', '.join(PARITY_FIELDS)} 上与发布窗口逐项相同。", ""]
    lines += ["| 拓扑 | 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 平均跳数 | 部分段跳请求比例 |",
              "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for (case, seed), r in sorted(rows.items()):
        for cell in ("canonical", "v3", "cycle"):
            row = r[cell]
            hop = (r["v3_hops"] if cell == "v3" else r["cycle_hops"] if cell == "cycle" else {})
            routes = row["route_counts"]
            mean_hops = sum(len(p.split("-")) * c for p, c in routes.items()) / sum(routes.values())
            share = f"{hop['partial_share']:.3f}" if hop else "—"
            lines.append(f"| {case} | {seed} | {cell} | {row['output_throughput_tokens_per_s']:.3f} | "
                         f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                         f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} | "
                         f"{mean_hops:.3f} | {share} |")
    lines += ["", "## 配对差值（三种子均值 ± 样本标准差；逐种子见 analysis.json）", "",
              "| 拓扑 | 对照 | " + " | ".join(label for _, label in METRICS) + " |",
              "| --- | --- | " + " | ".join("---:" for _ in METRICS) + " |"]
    for case in CASES:
        for pair in ("cycle-v3", "v3-canonical", "cycle-canonical"):
            if not deltas[case]:
                continue
            lines.append(f"| {case} | {pair} | " + " | ".join(
                summary(deltas[case][f"{pair}/{key}"]) for key, _ in METRICS) + " |")
    lines += ["", "| 拓扑 | 共同完成请求数 | 共同 P95 TTFT Δ (cycle−v3) | 共同 P95 TPOT Δ (cycle−v3) |",
              "| --- | --- | ---: | ---: |"]
    for case in CASES:
        if deltas[case]:
            lines.append(f"| {case} | {', '.join(str(n) for n in deltas[case]['common/n'])} | "
                         f"{summary(deltas[case]['common/ttft_s'])} | "
                         f"{summary(deltas[case]['common/tpot_s'])} |")
    analysis["formal"] = {case: {k: v for k, v in d.items()} for case, d in deltas.items()}

    # Pre-registered decision.
    verdict = {}
    if all(len(deltas[c]["cycle-v3/tpot_p95_s"]) == len(FORMAL_SEEDS) for c in CASES):
        rule = protocol["decision"]
        rel_tp = {c: mean(deltas[c]["cycle-v3/output_throughput_tokens_per_s"]) /
                  mean(rows[(c, s)]["v3"]["output_throughput_tokens_per_s"] for s in FORMAL_SEEDS)
                  for c in CASES}
        r1 = all(rel_tp[c] >= rule["min_relative_throughput_delta"] and
                 mean(deltas[c]["cycle-v3/tpot_p95_s"]) <= 0 for c in CASES)
        gap_v3 = mean(deltas["C1_single"]["v3-canonical/tpot_p95_s"])
        gap_cycle = mean(deltas["C1_single"]["cycle-canonical/tpot_p95_s"])
        closed = 1 - gap_cycle / gap_v3 if gap_v3 > 0 else float("nan")
        r2 = (closed >= rule["min_single_tpot_gap_closed"] and
              all(d < 0 for d in deltas["C1_single"]["cycle-v3/tpot_p95_s"]))
        multi_ttft = (mean(deltas["C1_multi"]["cycle-v3/ttft_p95_s"]) /
                      mean(rows[("C1_multi", s)]["v3"]["ttft_p95_s"] for s in FORMAL_SEEDS))
        r3 = (multi_ttft <= rule["max_multi_relative_ttft_increase"] and
              mean(deltas["C1_multi"]["cycle-canonical/tpot_p95_s"]) < 0 and
              mean(deltas["C1_multi"]["cycle-canonical/ttft_p95_s"]) < 0)
        verdict = {"relative_throughput_delta": rel_tp, "R1_no_harm": r1,
                   "single_tpot_gap_closed": closed, "R2_single_gap": r2,
                   "multi_relative_ttft_delta": multi_ttft, "R3_multi_retained": r3,
                   "adopt": r1 and r2 and r3}
        lines += ["", "## 预注册判定", "",
                  f"- R1 不伤害：两拓扑相对吞吐差 {', '.join(f'{c} {v:+.2%}' for c, v in rel_tp.items())}，"
                  f"P95 TPOT 均值不升 → **{'通过' if r1 else '不通过'}**",
                  f"- R2 单集群：与规范路径的 P95 TPOT 差距缩小 {closed:.1%}"
                  f"（要求 ≥ {rule['min_single_tpot_gap_closed']:.0%}），三个种子 TPOT 均下降 → "
                  f"**{'通过' if r2 else '不通过'}**",
                  f"- R3 三集群保留：P95 TTFT 相对变化 {multi_ttft:+.2%}"
                  f"（上限 {rule['max_multi_relative_ttft_increase']:+.0%}），且 TTFT/TPOT 仍优于规范路径 → "
                  f"**{'通过' if r3 else '不通过'}**",
                  f"- 结论：**{'采纳为 M3 改进候选' if verdict['adopt'] else '不采纳，作为负结果报告'}**"]
    analysis["verdict"] = verdict
    (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

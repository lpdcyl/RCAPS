"""Per-condition paired report and pre-registered verdict."""

from __future__ import annotations

import json
from statistics import mean, stdev

from experiments.v3_cycle_pricing.report import common_p95
from experiments.v3_cycle_pricing.run import FORMAL_SEEDS, digest, read, rel
from experiments.v3_gated_generalization.run import CELLS, CONDITIONS, GATED, HERE


def ms(values: list[float], pct: bool = False) -> str:
    if len(values) < 2:
        return "—"
    return (f"{mean(values):+.2%} ± {stdev(values):.2%}" if pct
            else f"{mean(values):+.4f} ± {stdev(values):.4f}")


def main() -> None:
    protocol = read(HERE / "protocol.json")
    audit = read(HERE / "audit.json")["conditions"]
    analysis = {"protocol_sha256": digest(HERE / "protocol.json"),
                "gated_scheduler_sha256": digest(GATED), "inputs": {}, "failures": [],
                "conditions": {}}
    out = ["# 慢链路门控路径准入：资源池与带宽泛化", "",
           "协议见 `protocol.json`（先于正式窗口提交）。冻结布局，不重新规划；对照为本环境同轨迹重跑的冻结 V3。"
           "种子 0/1/2，1800 秒，零预热，不排空。差值为门控 − V3。三个种子不作显著性检验。", "",
           "## 条件与准入边（`audit.json`）", "",
           "| 条件 | 负载 | 慢链路数 | 慢链路带宽范围 Mbps | 完整 DAG 边 | 准入边 | 绕行边 |",
           "| --- | ---: | ---: | --- | ---: | ---: | --- |"]
    for c, a in audit.items():
        rng = (f"{a['slow_link_Bps_range'][0] / 1e6:g}–{a['slow_link_Bps_range'][1] / 1e6:g}"
               if a["slow_link_Bps_range"] else "无")
        det = ", ".join(f"{x}→{y}" for x, y in a["detours"]) or "无（= 规范路径）"
        out.append(f"| {c} | {a['load']:g} | {a['slow_links']} | {rng} | {a['full_edges']} | "
                   f"{a['admitted_edges']} | {det} |")
    out += ["", "## 逐窗口", "",
            "| 条件 | 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 平均 Decode 批 | 单请求批占比 | 实际路径数 |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    rows = {}
    for c in CONDITIONS:
        for seed in FORMAL_SEEDS:
            cells = {}
            for cell in CELLS:
                path = HERE / "runs/formal" / c / f"{cell}_seed{seed}.json"
                failure = path.with_suffix(".failure.json")
                if failure.exists():
                    analysis["failures"].append(rel(failure))
                if path.exists():
                    analysis["inputs"][rel(path)] = digest(path)
                    cells[cell] = read(path)
            for cell, row in cells.items():
                b = row["decode_batches"]
                out.append(f"| {c} | {seed} | {cell} | {row['output_throughput_tokens_per_s']:.3f} | "
                           f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                           f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} | "
                           f"{b['mean_batch']:.2f} | {b['single_share']:.3f} | {len(row['route_counts'])} |")
            if len(cells) == 2:
                if cells["v3"]["trace_sha256"] != cells["gated"]["trace_sha256"]:
                    raise ValueError(f"Trace mismatch {c}/{seed}")
                rows[(c, seed)] = cells

    out += ["", "## 配对差值（门控 − 冻结 V3）", "",
            "| 条件 | 种子 | 吞吐相对 | TTFT Δ s | TPOT Δ s | TPOT 相对 | 完成率 Δ | 积压 Δ | 共同完成数 | 共同 TTFT Δ | 共同 TPOT Δ |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    verdict_lines = []
    rule = protocol["decision"]
    for c, spec in protocol["conditions"].items():
        per = []
        for seed in FORMAL_SEEDS:
            if (c, seed) not in rows:
                continue
            v, g = rows[(c, seed)]["v3"], rows[(c, seed)]["gated"]
            n, a, b = common_p95(v, g, "ttft_s")
            _, x, y = common_p95(v, g, "tpot_s")
            item = {"seed": seed,
                    "throughput_rel": g["output_throughput_tokens_per_s"] / v["output_throughput_tokens_per_s"] - 1,
                    "ttft": g["ttft_p95_s"] - v["ttft_p95_s"], "tpot": g["tpot_p95_s"] - v["tpot_p95_s"],
                    "tpot_rel": g["tpot_p95_s"] / v["tpot_p95_s"] - 1,
                    "completion": g["completion_fraction"] - v["completion_fraction"],
                    "backlog": g["backlog_at_window_end"] - v["backlog_at_window_end"],
                    "common_n": n, "common_ttft": b - a, "common_tpot": y - x}
            per.append(item)
            out.append(f"| {c} | {seed} | {item['throughput_rel']:+.2%} | {item['ttft']:+.3f} | "
                       f"{item['tpot']:+.4f} | {item['tpot_rel']:+.2%} | {item['completion']:+.4f} | "
                       f"{item['backlog']:+d} | {n} | {item['common_ttft']:+.3f} | {item['common_tpot']:+.4f} |")
        if len(per) >= 2:
            col = lambda k, pct=False: ms([p[k] for p in per], pct)
            out.append(f"| {c} | 均值 ± SD | {col('throughput_rel', True)} | {col('ttft')} | {col('tpot')} | "
                       f"{col('tpot_rel', True)} | {col('completion')} | {col('backlog')} | — | "
                       f"{col('common_ttft')} | {col('common_tpot')} |")
        failed = any(f"/{c}/" in f for f in analysis["failures"])
        complete = len(per) == len(FORMAL_SEEDS) and not failed
        result = {"class": spec["class"], "per_seed": per, "complete": complete}
        if complete:
            tp = mean(p["throughput_rel"] for p in per)
            tpot = mean(p["tpot_rel"] for p in per)
            if spec["class"] == "flat":
                passed = all(p["tpot"] < 0 for p in per) and tp >= -0.005
                why = (f"三种子 TPOT 均降：{'是' if all(p['tpot'] < 0 for p in per) else '否'}，"
                       f"吞吐均值 {tp:+.2%}")
            else:
                passed = tpot <= 0.02 and tp >= -0.005
                why = f"TPOT 相对均值 {tpot:+.2%}（≤ +2%），吞吐均值 {tp:+.2%}（≥ −0.5%）"
            result.update({"passed": passed, "mean_rel_tpot": tpot, "mean_rel_throughput": tp})
            verdict_lines.append(f"- {c}（{'平坦' if spec['class'] == 'flat' else '慢链路'}）：{why} → "
                                 f"**{'通过' if passed else '不通过'}**")
        else:
            result["passed"] = False
            verdict_lines.append(f"- {c}：窗口未完成或失败 → **不通过**")
        analysis["conditions"][c] = result
    everything = all(r["passed"] for r in analysis["conditions"].values())
    analysis["generalizes"] = everything
    pending = [c for c, r in analysis["conditions"].items()
               if not r["complete"] and not any(f"/{c}/" in f for f in analysis["failures"])]
    if pending:
        analysis["pending"] = pending
        out += ["", "## 预注册判定", "",
                f"正式窗口仍在运行（未完成条件：{', '.join(pending)}），暂不作判定。"]
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
        (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
        print("\n".join(out))
        return
    out += ["", "## 预注册判定", ""] + verdict_lines + [
        "", f"- 总体：**{'四个条件全部通过，泛化成立' if everything else '泛化只限于通过的条件；未通过条件如实报告'}**"]
    if analysis["failures"]:
        out += ["", "失败窗口（保留，不重跑）：" + "、".join(analysis["failures"])]
    (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()

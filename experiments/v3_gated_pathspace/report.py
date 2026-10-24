"""Development-window report for slow-link-gated path admission."""

from __future__ import annotations

import json
from pathlib import Path

from statistics import mean, stdev

from experiments.v3_cohort_routing.report import dev_rows
from experiments.v3_cycle_pricing.report import common_p95
from experiments.v3_cycle_pricing.run import (
    CANONICAL, CASES, FORMAL_SEEDS, RELEASED, ROOT, digest, read, rel)

HERE = Path(__file__).resolve().parent


def main() -> None:
    lines, data = dev_rows([("gated", HERE / "runs/dev/x/gated_seed100.json")])
    audit = read(HERE / "audit.json")["cases"]
    single = read(HERE / "runs/dev/C1_single/gated_seed100.json")
    canonical = read(Path(data["C1_single/canonical"]["source"]).resolve()
                     if Path(data["C1_single/canonical"]["source"]).is_absolute()
                     else HERE.parents[1] / data["C1_single/canonical"]["source"])
    same = all(single[k] == canonical[k] for k in (
        "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s", "route_counts", "query_samples"))
    multi = data["C1_multi/gated"]
    go = multi["relative_throughput"] >= -0.005 and multi["relative_tpot_p95"] <= 0
    gap = (data["C1_multi/canonical"]["tpot_p95_s"] - multi["tpot_p95_s"]) / (
        data["C1_multi/canonical"]["tpot_p95_s"] - data["C1_multi/v3"]["tpot_p95_s"])
    out = ["# V3 M3 慢链路门控路径准入：开发阶段", "",
           "规则见 `protocol_dev.json`（先于开发窗口提交）。种子 100、300 秒。", "",
           "## 准入边（`audit.json`）", "",
           "| 拓扑 | 完整 DAG 边 | 规范边 | 准入边 | 绕行边 | 慢规范边 |", "| --- | ---: | ---: | ---: | --- | --- |"]
    for case, info in audit.items():
        detours = ", ".join(f"{d['edge'][0]}→{d['edge'][1]}" for d in info["detours"]) or "无"
        slow = ", ".join(f"{a}→{b}" for a, b in info["slow_canonical_edges"]) or "无"
        out.append(f"| {case} | {info['full_edges']} | {info['canonical_edges']} | "
                   f"{info['admitted_edges']} | {detours} | {slow} |")
    out += ["", "## 开发窗口", ""] + lines
    out += ["", "## 预注册判定", "",
            f"- 单集群准入边与规范路径相同，开发窗口与规范路径窗口逐项相同：{'是' if same else '否'}",
            f"- 三集群相对冻结 V3：吞吐 {multi['relative_throughput']:+.2%}，P95 TPOT "
            f"{multi['relative_tpot_p95']:+.2%}（要求吞吐 ≥ −0.5% 且 TPOT ≤ 0）",
            f"- 结论：**{'进入正式窗口' if go else '未满足 TPOT 不升，按规则停止，不跑正式窗口'}**", "",
            "## 描述（不作判定依据）", "",
            f"- 三集群：4 条绕行边收回了规范路径到完整 DAG 之间 {gap:.0%} 的 P95 TPOT 差距，"
            f"平均 Decode 批 {multi['mean_batch']:.2f}（完整 DAG 3.07，规范路径 7.19）。",
            "- 单集群：无慢链路，候选即规范路径，吞吐与 TPOT 相对冻结 V3 的改善与路径空间消融方向一致。",
            "- 单个 300 秒开发窗口在三集群只有约 100 个请求，1% 的 TPOT 差约 7 ms，"
            "不能区分噪声与系统性差距；是否以非劣效边界重新预注册正式验证，需要研究者决定。"]
    formal_lines, formal = formal_section()
    out += formal_lines
    (HERE / "analysis.json").write_text(json.dumps(
        {"dev": data, "single_equals_canonical": same, "go": go,
         "multi_tpot_gap_recovered": gap, "formal": formal},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


METRICS = (("output_throughput_tokens_per_s", "吞吐"), ("ttft_p95_s", "P95 TTFT"),
           ("tpot_p95_s", "P95 TPOT"), ("completion_fraction", "完成率"),
           ("backlog_at_window_end", "积压"))


def robustness(rows: dict, result: dict) -> list[str]:
    """Same-environment check: frozen V3 rerun here instead of the released window."""
    local = ROOT / "experiments/v3_cycle_pricing/runs/formal"
    lines = ["", "### 稳健性（不作判定）：对照换成本环境重跑的冻结 V3", "",
             "发布窗口在 Python 3.10/numpy 2.2 运行，本环境为 Python 3.13/numpy 2.5。"
             "冻结 V3 单集群种子 0、2 的重跑与发布窗口从首批请求起选路分叉"
             "（`experiments/v3_cycle_pricing/analysis.json` 的 parity），其余四个窗口逐项相同；"
             "候选单集群窗口与在原环境产生的规范路径窗口逐项相同。", "",
             "| 拓扑 | 种子 | 本地 V3 P95 TPOT | 候选 P95 TPOT | TPOT 相对 | 吞吐相对 |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    rel_tpot = {case: [] for case in CASES}
    rel_tp = {case: [] for case in CASES}
    for (case, seed), cells in sorted(rows.items()):
        path = local / case / f"v3_seed{seed}.json"
        v3 = read(path)
        result["inputs"][rel(path)] = digest(path)
        g = cells["gated"]
        t = g["tpot_p95_s"] / v3["tpot_p95_s"] - 1
        q = g["output_throughput_tokens_per_s"] / v3["output_throughput_tokens_per_s"] - 1
        rel_tpot[case].append(t)
        rel_tp[case].append(q)
        lines.append(f"| {case} | {seed} | {v3['tpot_p95_s']:.4f} | {g['tpot_p95_s']:.4f} | {t:+.2%} | {q:+.2%} |")
    ni1 = mean(rel_tpot["C1_multi"]) <= 0.02 and mean(rel_tp["C1_multi"]) >= -0.005
    ni2 = all(t < 0 for t in rel_tpot["C1_single"]) and mean(rel_tp["C1_single"]) >= -0.005
    result["same_environment"] = {"rel_tpot": rel_tpot, "rel_throughput": rel_tp, "NI1": ni1, "NI2": ni2}
    lines += ["", f"同环境下 NI1 {'通过' if ni1 else '不通过'}（三集群 TPOT 均值 {mean(rel_tpot['C1_multi']):+.2%}），"
              f"NI2 {'通过' if ni2 else '不通过'}（单集群 TPOT 均值 {mean(rel_tpot['C1_single']):+.2%}）。"]
    return lines


def formal_section() -> tuple[list[str], dict]:
    protocol_path = HERE / "protocol.json"
    if not protocol_path.exists():
        return [], {}
    rows, inputs, failures = {}, {}, []
    for case in CASES:
        for seed in FORMAL_SEEDS:
            path = HERE / "runs/formal" / case / f"gated_seed{seed}.json"
            failure = path.with_suffix(".failure.json")
            if failure.exists():
                failures.append(rel(failure))
            if not path.exists():
                continue
            v3 = ROOT / RELEASED[case].format(seed=seed)
            can = ROOT / CANONICAL.format(case=case, seed=seed)
            for item in (path, v3, can):
                inputs[rel(item)] = digest(item)
            cells = {"canonical": read(can), "v3": read(v3), "gated": read(path)}
            if len({c["trace_sha256"] for c in cells.values()}) != 1:
                raise ValueError(f"Trace mismatch {case}/{seed}")
            rows[(case, seed)] = cells
    lines = ["", "## 正式窗口：非劣效检验（`protocol.json` 第 2 版，先于正式窗口提交）", "",
             "种子 0/1/2，1800 秒，零预热，不排空；单集群 700、三集群 320 offered token/s。", "",
             "| 拓扑 | 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 平均 Decode 批 | 实际路径数 |",
             "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for (case, seed), cells in sorted(rows.items()):
        for cell, row in cells.items():
            batch = row.get("decode_batches", {}).get("mean_batch")
            lines.append(f"| {case} | {seed} | {cell} | {row['output_throughput_tokens_per_s']:.3f} | "
                         f"{row['ttft_p95_s']:.3f} | {row['tpot_p95_s']:.3f} | "
                         f"{row['completion_fraction']:.3f} | {row['backlog_at_window_end']} | "
                         f"{f'{batch:.2f}' if batch else '—'} | {len(row['route_counts'])} |")
    result = {"inputs": inputs, "failures": failures, "per_seed": {}, "summary": {}}
    lines += ["", "### 配对差值（逐种子；最后一行为三种子均值 ± 样本标准差）", "",
              "| 拓扑 | 对照 | 种子 | 吞吐 Δ | 吞吐相对 | TTFT Δ s | TPOT Δ s | TPOT 相对 | 完成率 Δ | 积压 Δ | 共同完成数 | 共同 TTFT Δ | 共同 TPOT Δ |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in CASES:
        for ref in ("v3", "canonical"):
            per = []
            for seed in FORMAL_SEEDS:
                if (case, seed) not in rows:
                    continue
                g, r = rows[(case, seed)]["gated"], rows[(case, seed)][ref]
                n, a, b = common_p95(r, g, "ttft_s")
                _, c, d = common_p95(r, g, "tpot_s")
                item = {"seed": seed,
                        "throughput": g["output_throughput_tokens_per_s"] - r["output_throughput_tokens_per_s"],
                        "throughput_rel": g["output_throughput_tokens_per_s"] / r["output_throughput_tokens_per_s"] - 1,
                        "ttft": g["ttft_p95_s"] - r["ttft_p95_s"],
                        "tpot": g["tpot_p95_s"] - r["tpot_p95_s"],
                        "tpot_rel": g["tpot_p95_s"] / r["tpot_p95_s"] - 1,
                        "completion": g["completion_fraction"] - r["completion_fraction"],
                        "backlog": g["backlog_at_window_end"] - r["backlog_at_window_end"],
                        "common_n": n, "common_ttft": b - a, "common_tpot": d - c}
                per.append(item)
                lines.append(f"| {case} | gated−{ref} | {seed} | {item['throughput']:+.3f} | "
                             f"{item['throughput_rel']:+.2%} | {item['ttft']:+.3f} | {item['tpot']:+.4f} | "
                             f"{item['tpot_rel']:+.2%} | {item['completion']:+.4f} | {item['backlog']:+d} | "
                             f"{n} | {item['common_ttft']:+.3f} | {item['common_tpot']:+.4f} |")
            if len(per) >= 2:
                def ms(key, pct=False):
                    values = [p[key] for p in per]
                    m, s = mean(values), stdev(values)
                    return f"{m:+.2%} ± {s:.2%}" if pct else f"{m:+.4f} ± {s:.4f}"
                lines.append(f"| {case} | gated−{ref} | 均值 | {ms('throughput')} | {ms('throughput_rel', True)} | "
                             f"{ms('ttft')} | {ms('tpot')} | {ms('tpot_rel', True)} | {ms('completion')} | "
                             f"{ms('backlog')} | — | {ms('common_ttft')} | {ms('common_tpot')} |")
            result["per_seed"][f"{case}/gated-{ref}"] = per
    complete = all((c, s) in rows for c in CASES for s in FORMAL_SEEDS) and not failures
    if complete:
        multi = result["per_seed"]["C1_multi/gated-v3"]
        single = result["per_seed"]["C1_single/gated-v3"]
        m_tpot = mean(p["tpot_rel"] for p in multi)
        m_tp = mean(p["throughput_rel"] for p in multi)
        s_tp = mean(p["throughput_rel"] for p in single)
        ni1 = m_tpot <= 0.02 and m_tp >= -0.005
        ni2 = all(p["tpot"] < 0 for p in single) and s_tp >= -0.005
        result["summary"] = {"multi_mean_rel_tpot": m_tpot, "multi_mean_rel_throughput": m_tp,
                             "single_mean_rel_throughput": s_tp, "NI1": ni1, "NI2": ni2,
                             "adopt": ni1 and ni2}
        lines += ["", "### 预注册判定", "",
                  f"- NI1 三集群非劣效：P95 TPOT 相对冻结 V3 均值 {m_tpot:+.2%}（上限 +2%），"
                  f"吞吐 {m_tp:+.2%}（下限 −0.5%）→ **{'通过' if ni1 else '不通过'}**",
                  f"- NI2 单集群改善：三个种子 P95 TPOT 均低于冻结 V3："
                  f"{'是' if all(p['tpot'] < 0 for p in single) else '否'}，吞吐 {s_tp:+.2%} → "
                  f"**{'通过' if ni2 else '不通过'}**",
                  f"- 结论：**{'采纳为 M3 路径准入改进候选' if ni1 and ni2 else '不采纳，作为负结果报告'}**"]
        lines += robustness(rows, result)
    else:
        lines += ["", f"正式窗口尚未全部完成或有失败（失败：{', '.join(failures) or '无'}），不作判定。"]
    return lines, result


if __name__ == "__main__":
    main()

"""Audit and summarize independent capacity-guided M2/M3 validation."""

from __future__ import annotations

import csv
from collections import defaultdict

from .joint import CASES, HERE, ROOT, digest, read, relative, write
from .joint import case_inputs, observed_edge_counts
from .report import common_completed
from .joint_capacity import BASE
from rcaps.v3.placement import validate as validate_layout


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def build():
    code_files = (HERE / "capacity.py", HERE / "capacity_route.py",
                  HERE / "capacity_search.py", HERE / "joint_capacity.py",
                  ROOT / "benchmarks/fixed_window.py",
                  ROOT / "rcaps/v3/resource_graph.py",
                  ROOT / "rcaps/v3/online_scheduler.py")
    summary = {"cases": {}, "code_sha256":
               {relative(path): digest(path) for path in code_files}}
    delta_rows = []
    lines = ["# 容量约束放置 × 实时路由：独立候选验证", "",
             "M1 只提供资源与层兼容图。M2 用类别流 LP 和开发种子 100 的短窗口选布局；"
             "M3 在合法图上保留每状态最多四个 Pareto 标签，并在最早路由成本 10% 内按容量压力选路。",
             "Decode 沿原 Prompt 路径；冻结 V3 和原始结果没有覆盖。", "",
             "本报告的正式对照使用 1800 秒固定窗口及种子 0／1／2。"
             "三个种子只表示波动，不作为显著性检验。", ""]
    for case in CASES:
        plan = read(BASE / "plans" / f"{case}.json")
        selected = read(BASE / "plans" / f"{case}_selected.json")
        formal = read(BASE / "validation" / f"{case}.json")
        search = read(BASE / "plans" / f"{case}_capacity_search.json")
        planning_wall = 0.0
        for candidate in selected["rows"]:
            for outcome in candidate["outcomes"]:
                source = ROOT / outcome["path"]
                if digest(source) != outcome["sha256"]:
                    raise ValueError(f"Planning result hash changed: {source}")
                planning_wall += read(source).get("wall_s", 0.0)
        rows = defaultdict(dict)
        for entry in formal["rows"]:
            source = ROOT / entry["path"]
            if digest(source) != entry["sha256"]:
                raise ValueError(f"Raw result hash changed: {source}")
            raw = read(source)
            # Frozen formal V3 records predate this candidate's explicit status field.
            # Their completed state was checked by reused_formal during validation.
            if entry["reused"] and "status" not in raw:
                raw["status"] = "completed"
            if raw.get("status") != entry["status"]:
                raise ValueError(f"Status mismatch: {source}")
            if raw.get("trace_sha256") != entry["trace_sha256"]:
                raise ValueError(f"Trace mismatch: {source}")
            rows[(entry["mode"], entry["seed"])][entry["arm"]] = (entry, raw)
        best = next(row for row in plan["capacity_ranked"]
                    if row["layout"] == selected["winner"])
        top_rate = max(row["lp"]["requests_per_s"]
                       for row in plan["capacity_ranked"])
        tied = {row["layout"] for row in plan["capacity_ranked"]
                if abs(row["lp"]["requests_per_s"] - top_rate) <= 1e-6}
        trained = {row["layout"]: row["outcomes"] for row in selected["rows"]}
        model, _, _ = case_inputs(case)
        checked = validate_layout(model, read(ROOT / best["path"] /
                                             "placement.json")["state"])
        lines.extend([f"## {case}", "",
                      f"选中布局：`{selected['winner']}`；层段副本数 {best['widths']}；"
                      f"LP 静态容量 {best['lp']['requests_per_s']:.3f} 请求/s。",
                      f"LP 首要瓶颈：`{best['lp']['bottlenecks'][0]['resource']}`。"
                      f"固定形状搜索检查 {search['legal_layouts_evaluated']} 个合法布局，"
                      f"耗时 {search['planning_wall_s']:.1f} 秒；"
                      f"短名单在线规划窗口累计 {planning_wall:.1f} 秒。"
                      "未进入训练短名单的布局没有在线验证。",
                      "", "静态容量并列诊断：LP 容量最高的布局有 "
                      f"{len(tied)} 个（{', '.join(sorted(tied))}）；"
                      "这些布局在容量代理下无法区分。下表只列开发种子 100 的在线短窗口范围，"
                      "用于说明选择依据，不作为独立性能证据。", "",
                      "| 开发到达模式 | 并列布局数 | 完成率范围 | P95 TTFT 范围 s | P95 TPOT 范围 s |",
                      "| --- | ---: | ---: | ---: | ---: |"])
        for mode in ("uniform", "burst"):
            outcomes = [outcome for label in tied if label in trained
                        for outcome in trained[label]
                        if outcome["mode"] == mode and outcome["status"] == "completed"]
            if outcomes:
                def span(key: str) -> str:
                    values = [row[key] for row in outcomes]
                    return f"{min(values):.3f}–{max(values):.3f}"

                lines.append(f"| {mode} | {len(outcomes)} | {span('completion')} | "
                             f"{span('ttft_p95_s')} | {span('tpot_p95_s')} |")
        lines.extend(["", "| 到达模式 | 种子 | 方法 | 输出 token/s | P95 TTFT s | P95 TPOT s | 完成率 | 积压 | 路径数 | 原始结果 |",
                      "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
        paired = []
        failures = []
        for mode, seed in sorted(rows):
            pair = rows[mode, seed]
            if set(pair) != {"released_v3", "capacity_joint"}:
                failures.append({"mode": mode, "seed": seed,
                                 "reason": "missing arm"})
                continue
            a_info, a = pair["released_v3"]
            b_info, b = pair["capacity_joint"]
            for label, info, raw in (("V3", a_info, a),
                                     ("联合候选", b_info, b)):
                if raw["status"] != "completed":
                    lines.append(f"| {mode} | {seed} | {label} | 失败 | — | — | — | — | — | {info['path']} |")
                    failures.append({"mode": mode, "seed": seed,
                                     "arm": label, "reason": raw.get("error")})
                    continue
                lines.append("| " + " | ".join((
                    mode, str(seed), label,
                    f"{raw['output_throughput_tokens_per_s']:.3f}",
                    f"{raw['ttft_p95_s']:.3f}", f"{raw['tpot_p95_s']:.3f}",
                    f"{raw['completion_fraction']:.3f}",
                    str(raw['backlog_at_window_end']),
                    str(len(raw['route_counts'])), info["path"])) + " |")
            if a["status"] != "completed" or b["status"] != "completed":
                continue
            observed_edge_counts(b["route_counts"], checked["dag"])
            if a["trace_sha256"] != b["trace_sha256"]:
                raise ValueError(f"Paired traces differ: {case}/{mode}/{seed}")
            item = {"case": case, "mode": mode, "seed": seed,
                    "v3_source": a_info["path"], "candidate_source": b_info["path"],
                    "trace_sha256": a["trace_sha256"],
                    "common_completed": common_completed(a, b, 1800)}
            for name in METRICS:
                item[name + "_delta"] = b[name] - a[name]
            paired.append(item)
            delta_rows.append(item)
        lines.extend(["", "配对差值为联合候选减去 V3。延迟与积压越低越好。", ""])
        for mode in ("uniform", "burst"):
            subset = [row for row in paired if row["mode"] == mode]
            if not subset:
                lines.append(f"- {mode}：没有完整的配对窗口。")
                continue
            means = {name: sum(row[name + "_delta"] for row in subset) / len(subset)
                     for name in METRICS}
            lines.append(f"- {mode}：{len(subset)} 个完整种子的平均配对差值为"
                         f"吞吐 {means[METRICS[0]]:+.3f} token/s，"
                         f"P95 TTFT {means[METRICS[1]]:+.3f} s，"
                         f"P95 TPOT {means[METRICS[2]]:+.3f} s，"
                         f"完成率 {means[METRICS[3]]:+.3f}，"
                         f"积压 {means[METRICS[4]]:+.1f}。")
        lines.append("")
        summary["cases"][case] = {"selected": selected["winner"],
                                   "capacity_ranked": plan["capacity_ranked"],
                                   "shape_search": search,
                                   "planning_window_wall_s": planning_wall,
                                   "paired": paired, "failures": failures}
    all_paired = [row for case in summary["cases"].values()
                  for row in case["paired"]]
    complete = len(all_paired) == len(CASES) * 2 * 3
    lines.extend(["## 判定", "",
                  "这项候选只在部署前用在线短窗口反馈选择布局；运行时没有模型层迁移或重新放置。"
                  "因此它检验的是离线放置选择与在线路由的耦合，不是运行时放置闭环。", ""])
    if complete and all(row["tpot_p95_s_delta"] > 0 for row in all_paired):
        lines.append("两拓扑、均匀与突发到达的 12 个正式配对窗口中，联合候选的 P95 TPOT 均高于冻结 V3。"
                     "吞吐差值很小且方向不一致；开发短窗口选出的布局未在独立正式种子上带来稳定收益。"
                     "当前证据不支持把这个联合候选升级为主方法，也不能据此声称已经解决静态评价与在线表现不一致。")
    elif not complete:
        lines.append("存在失败或缺失的正式配对窗口；只对已完成窗口给出逐种子差值，不作整体收益结论。")
    else:
        lines.append("正式配对结果方向混合；请依据上表逐拓扑和到达模式解释，勿以开发短窗口替代正式结论。")
    lines.extend(["", "LP 最大容量在两个拓扑各有四个布局并列，而开发窗口的完成率和尾延迟有差异。"
                  "这是静态容量代理区分力不足的直接诊断；并不证明当前短窗口反馈规则已经修复该问题。", ""])
    write(BASE / "summary.json", summary)
    (BASE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (BASE / "paired_deltas.csv").open("w", encoding="utf-8", newline="") as stream:
        columns = ("case", "mode", "seed", *[key + "_delta" for key in METRICS],
                   "v3_source", "candidate_source", "trace_sha256")
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(delta_rows)
    return summary


if __name__ == "__main__":
    build()

"""Enrich an already audited reconciliation with absolute/outcome/mechanism tables."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from statistics import mean, stdev

from experiments.v4_formal.run import read, write, digest, stamp, ROOT

HERE = Path(__file__).resolve().parent


def summary(values):
    if not values or any(v is None or not math.isfinite(float(v)) for v in values):
        return None
    return dict(n=len(values), mean=mean(values), sample_std=stdev(values) if len(values) > 1 else None,
                values=values)


def route_mechanism(row):
    counts = list(row["route_counts"].values())
    total = sum(counts)
    probabilities = [v / total for v in counts if v] if total else []
    entropy = -sum(p * math.log(p) for p in probabilities) if probabilities else 0.0
    return dict(distinct_paths=len(counts), max_path_share=max(probabilities) if probabilities else None,
                normalized_route_entropy=entropy / math.log(len(probabilities)) if len(probabilities) > 1 else 0.)


def main():
    source = HERE / "results.json"
    archive = HERE / "reconciliation_v1.json"
    amend = HERE / "report_enrichment.json"
    if archive.exists() or amend.exists():
        raise RuntimeError("Enrichment already exists; inspect its recorded outputs")
    result = read(source)
    if result["status"] != "verified_with_failed_windows" or result["problems"] or result["missing"]:
        raise RuntimeError("Unexpected audit status; do not enrich unverified evidence")
    # Reconfirm each displayed source against its reconciled SHA before use.
    raw = {}
    for window in result["windows"]:
        path = ROOT / window["source"]
        if digest(path) != window["sha256"]:
            raise RuntimeError(f"Source hash drift: {window['source']}")
        if window["kind"] in {"new_execution", "reused_reference"}:
            raw[window["source"]] = read(path)

    for pair in result["paired"]:
        pair["aggregate_absolute"] = {}
        for metric in pair["seeds"][0]["absolute_change"] if pair["seeds"] else []:
            values = [s["absolute_change"][metric] for s in pair["seeds"]]
            # Partial groups remain explicit seed observations, without a group estimate.
            pair["aggregate_absolute"][metric] = summary(values) if pair["complete_three_seed"] else None
        if pair["experiment"] == "session":
            mechanisms = []
            for seed in pair["seeds"]:
                full_path = next(w["source"] for w in result["windows"] if
                    w["kind"] == "reused_reference" and w["scenario"] == pair["scenario"] and
                    w["load"] == pair["load"] and w["cell"] == "v4" and w["seed"] == seed["seed"])
                no_path = next(w["source"] for w in result["windows"] if
                    w["kind"] == "new_execution" and w["experiment"] == "session" and
                    w["scenario"] == pair["scenario"] and w["seed"] == seed["seed"])
                full, no_session = route_mechanism(raw[full_path]), route_mechanism(raw[no_path])
                mechanisms.append(dict(seed=seed["seed"], complete_rcaps=full,
                    no_session=no_session, full_over_no_session=dict(
                        distinct_paths_change=full["distinct_paths"] - no_session["distinct_paths"],
                        max_path_share_change_pp=100 * (full["max_path_share"] - no_session["max_path_share"]),
                        normalized_route_entropy_change=full["normalized_route_entropy"] -
                            no_session["normalized_route_entropy"])))
            pair["route_mechanism_by_seed"] = mechanisms

    original_hash = digest(source)
    shutil.copyfile(source, archive)
    result["initial_reconciliation_sha256"] = original_hash
    result["report_enrichment"] = dict(source="enrich_results.py", source_sha256=digest(Path(__file__)),
        generated_at=stamp(), archived_initial_reconciliation=archive.name,
        archived_initial_reconciliation_sha256=digest(archive),
        note="Deterministic reporting enrichment from previously audited, hash-verified seed records; no simulation rerun")
    write(source, result)

    paired = result["paired"]
    by_group = {(p["experiment"], p["scenario"], p["cell"], p["comparator"]): p for p in paired}

    def relative_cell(p, metric):
        s = p["aggregate"].get(metric)
        return "不完整" if s is None else f"{s['mean']:+.2f} ± {s['sample_std']:.2f}"

    def absolute_cell(p, metric, factor=1):
        s = p["aggregate_absolute"].get(metric)
        return "不完整" if s is None else f"{s['mean']*factor:+.2f} ± {s['sample_std']*factor:.2f}"

    lines = ["# RCAPS 收紧主线后的核心补证结果", "",
        f"核验时间：{result['finished_at']}。逐请求记录和哈希核验见 results.json、individual.csv；本报告不包含新增或重跑窗口。", "",
        "## 执行状态与核验", "",
        "正式预登记15个窗口：14个成功、1个失败；缺失0个，14个成功记录均通过核验，固定到达后尾部观察均无右删失。成功窗口的峰值并发为2。", "",
        "失败条件为 multi/320、100 ms/中间边界、seed 1，进程在 `network_link.finish_sending` 发生 Windows access violation，退出码 3221225477。失败日志、启动身份及哈希均保留；依照预登记策略不重跑。该成本点因此只有 seed 0、2，不报告三种子聚合结论。", "",
        "另有15次更早的启动适配器派发失败，均发生在创建仿真进程之前，不是15个额外实验结果；原 index、错误日志及修正说明均保留。", "",
        f"最终审计状态为 `{result['status']}`，727项检查中失败0项，遗漏0项；14个结果和9个复用参照均按登记哈希读取。真实异构硬件校准未完成。", "",
        "到达前缀1800秒，观察至5400秒。下表为逐种子处理效应的均值±样本标准差（不是置信区间，也不表示三种子显著性）。正负号表示完整 RCAPS 减弱/增加后的对应差异，方向见首列。", "",
        "## 会话持续服务代价", "",
        "方向为完整 RCAPS / no_session − 1；完成率与积压用绝对差。每组3个种子且双方完成相同输出工作量。", "",
        "|场景|TPOT P95 相对变化 %|TTFT P95 相对变化 %|吞吐相对变化 %|完成率差百分点|积压差请求|GPU 工作/token 相对变化 %|", "|---|---:|---:|---:|---:|---:|---:|"]
    for scenario, load in (("single", 700), ("multi", 320)):
        p = by_group["session", scenario, "no_session", "v4"]
        lines.append(f"|{scenario} {load}|{relative_cell(p,'tpot_p95_s')}|{relative_cell(p,'ttft_p95_s')}|"
            f"{relative_cell(p,'output_throughput_tokens_per_s')}|{absolute_cell(p,'completion_fraction',100)}|"
            f"{absolute_cell(p,'backlog_at_window_end')}|{relative_cell(p,'gpu_seconds_per_output_token')}|")
    lines += ["", "两个场景中，会话代价均与更低 TPOT 相联系：单集群平均 −20.40%，三集群 −26.30%；三集群 TTFT 平均 −4.40%，单集群 TTFT 均值接近零（+0.05%）。完整系统相对 no_session 的 GPU 工作/token 分别增加约48.94%和76.84%。吞吐、完成率和末端积压没有变化，因为配对队列工作量相同且全部完成。", "",
        "路径统计与批量画像揭示了取舍方向，但属于同一消融下的伴随机制证据，不等于独立中介效应：", "",
        "|场景|完整 RCAPS 活跃路径数|no_session 活跃路径数|完整系统最大单路径请求份额|no_session 最大单路径份额|Decode token 加权批量（完整 / no_session）|", "|---|---:|---:|---:|---:|---:|"]
    for scenario, load in (("single", 700), ("multi", 320)):
        p = by_group["session", scenario, "no_session", "v4"]
        rows = p["route_mechanism_by_seed"]
        def av(field, variant=None):
            return mean([r[variant][field] if variant else r[field] for r in rows])
        fullbatch = mean([s["numerator"]["token_weighted_decode_batch"] for s in p["seeds"]])
        nonbatch = mean([s["denominator"]["token_weighted_decode_batch"] for s in p["seeds"]])
        lines.append(f"|{scenario} {load}|{av('distinct_paths','complete_rcaps'):.1f}|{av('distinct_paths','no_session'):.1f}|"
            f"{100*av('max_path_share','complete_rcaps'):.1f}%|{100*av('max_path_share','no_session'):.1f}%|"
            f"{fullbatch:.1f} / {nonbatch:.1f}|")
    lines += ["", "例如三集群中，关闭会话代价后平均从8条实际路径收缩到4条，最大单路径承载约79%请求；完整系统较均衡地分流，但平均 Decode batch 较小、GPU 工作增多。观测与“通过会话代价避免路径过度集中、以更多 GPU 工作换取响应性”的解释一致。该解释受当前画像和工作负载限制。", "",
        "## 分块边界成本敏感性", "",
        "成本作用于有效载荷完成后的资源保留时间，不增加传输字节。下表方向为成本处理 / 对照 − 1，所有有效窗口均完成相同队列；100 ms仅展示两个有效种子的原始变化，不汇总。", "",
        "|每中间边界假设成本|完整种子|对照|TPOT P95变化 %|TTFT P95变化 %|GPU 工作/token变化 %|解释|", "|---:|---:|---|---:|---:|---:|---|"]
    for ms, comparator in ((1,"v4"),(1,"spatial"),(10,"v4"),(10,"spatial"),(100,"v4"),(100,"spatial")):
        p = by_group["boundary_cost", "multi", f"hold_{ms}ms", comparator]
        if ms < 100:
            tpot, ttft, gpu = (relative_cell(p,m) for m in ("tpot_p95_s","ttft_p95_s","gpu_seconds_per_output_token"))
            n, note = "3/3", "三种子完整"
        else:
            n, tpot, ttft, gpu = "2/3（部分）", "；".join(
                f"s{s['seed']} {s['relative_change_percent']['tpot_p95_s']:+.2f}" for s in p['seeds']), \
                "；".join(f"s{s['seed']} {s['relative_change_percent']['ttft_p95_s']:+.2f}" for s in p['seeds']), \
                "；".join(f"s{s['seed']} {s['relative_change_percent']['gpu_seconds_per_output_token']:+.2f}" for s in p['seeds'])
            note = "seed 1 原生崩溃；不聚合"
        label = "无分块" if comparator == "spatial" else "完整系统（零附加成本）"
        lines.append(f"|{ms} ms|{n}|{label}|{tpot}|{ttft}|{gpu}|{note}|")
    lines += ["", "1 ms和10 ms下，分块相对无分块的 TPOT P95均值分别低14.51%和13.93%，GPU工作/token高5.41%和4.36%；两组完成率均为100%，吞吐和积压不变。相对零附加成本的完整分块系统，TPOT均值变化分别为−0.21%和+0.47%，样本离散度较大，不应解释为显著差异。", "",
        "100 ms的两个存活种子中，TPOT相对无分块仍低8.65%和11.38%，但TTFT高8.16%和6.31%；相对零附加成本完整系统，TPOT高5.07%和6.19%。第三种子发生原生崩溃，因此只能陈述这两个配对观察；未得到完整三种子结果，也没有可报告的可靠交叉阈值。", "",
        "成本敏感性是人工注入的持有时延假设，不是实测协议或CPU开销，结果只能界定当前离散假设点。报告的GPU工作/token、TTFT及TPOT同时列出；无法据此证明真实推理引擎采用相同成本时会有相同结果。", "",
        "## 论文主线结论与范围", "",
        "会话项独立消融支持：完整系统中的会话持续服务代价有助于路径分散，并在两个测试场景中以更高GPU工作换来更低TPOT；第二项贡献宜围绕会话感知路由的延迟—工作量权衡，而非把工作项写成无代价收益。", "",
        "时空执行整形的现有完整系统结果与本次假设成本结果共同表明：传输分块在当前三集群画像下的延迟收益仍可见，但对成本模型、响应指标与工作量的影响并不完全一致。100 ms组不完整，且实机协议开销未校准；只能以这些已运行假设点描述适用边界。", "",
        "完整 RCAPS 相对外部方法的主结果仍应放在全文最前，随后呈现完整系统消融，再讲机制和敏感性。V3→V4不作为论文中心。既有高负载外部系统失败、近期机制对照范围、单机仿真边界及新颖性未独立验证等限制仍成立；本轮没有证明跨所有负载全面优于外部系统或满足CCF-A录用条件。", "",
        "## 可复核文件", "",
        "`results.json` 含审计检查、种子级配对、未完成样本、哈希及本报告的派生表；`individual.csv` 保留逐条件和逐种子指标；`reconciliation_v1.json` 保留首次综合核验原件；`execution/runs/` 保存每个条件的源 JSON、PID、日志或失败记录；`manifest.json` 和修正登记文件固定了实验身份。", ""]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    report = dict(enriched_at=stamp(), previous_results_sha256=original_hash,
        results_sha256=digest(source), results_archive_sha256=digest(archive),
        report_sha256=digest(HERE / "RESULTS_CN.md"), evidence_count=14,
        failures=1, missing=0, note="No simulation rerun; deterministic presentation enrichment only")
    write(amend, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

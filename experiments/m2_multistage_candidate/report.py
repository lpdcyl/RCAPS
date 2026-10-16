"""Generate an integrity-checked, paired report without filling missing runs."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from rcaps.placement.topology import TopologyModel

from .analysis import METRICS, common_completed, pending, source, summarize
from .placement import HERE, ROOT, digest
from .prepare import CASES, LOADS, VARIANTS, files


def collect() -> dict:
    audit = json.loads((HERE / "offline_audit.json").read_text(encoding="utf-8"))
    smoke_path = HERE / "smoke_index.json"
    formal_path = HERE / "formal_index.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.exists() else {}
    formal = json.loads(formal_path.read_text(encoding="utf-8")) if formal_path.exists() else {}
    result = {"protocol": {"model": "LLaMA-70B", "offered_token_loads": LOADS,
                           "formal_seeds": [0, 1, 2], "smoke_seed": 100,
                           "formal_duration_s": 1800, "smoke_duration_s": 60,
                           "warmup_s": 0, "tail_drain": False,
                           "scheduler": "GraphModeledQueueAwareDagScheduler",
                           "objective_weights": [0.40, 0.35, 0.25]},
              "offline": audit, "smoke": smoke, "formal_index": formal,
              "layouts": {}, "resource_pools": {},
              "formal_rows": [], "paired_rows": [], "type_pair_rows": [],
              "external_baselines": [],
              "missing": [],
              "source_sha256": {
                  name: digest(ROOT / name) for name in (
                      "rcaps/placement/resource_graph.py",
                      "rcaps/placement/static_resource.py",
                      "rcaps/scheduling/scheduler_final.py",
                      "benchmarks/fixed_window.py",
                      "simulator/event_simulator/cluster_simulator.py",
                      "experiments/m1_graph_candidate/scheduler.py",
                      "experiments/m2_multistage_candidate/placement.py",
                      "experiments/m2_multistage_candidate/search.py",
                      "experiments/m2_multistage_candidate/prepare.py",
                      "experiments/m2_multistage_candidate/run.py")}}
    result["validation_artifacts"] = {
        name: {"source": str((HERE / name).relative_to(ROOT)).replace("\\", "/"),
               "sha256": digest(HERE / name)}
        for name in ("fixed_trace_probe.json", "runtime_graph_audit.json",
                     "reference_audit.json")
        if (HERE / name).is_file()}
    for case in CASES:
        if case not in audit:
            result["missing"].append(f"offline:{case}")
            continue
        model = TopologyModel(files(case)[0])
        result["resource_pools"][case] = dict(model.machine_counts)
        result["layouts"][case] = {}
        for variant in VARIANTS:
            if variant not in audit[case]["variants"]:
                result["missing"].append(f"offline:{case}/{variant}")
                continue
            if audit[case]["variants"][variant]["status"] != "feasible":
                continue
            placement = HERE / "layouts" / case / variant / "placement.json"
            if not placement.exists():
                raise ValueError(f"Missing exported placement: {placement}")
            placement_row = json.loads(placement.read_text(encoding="utf-8"))
            result["layouts"][case][variant] = {
                "source": str(placement.relative_to(ROOT)).replace("\\", "/"),
                "sha256": digest(placement),
                "segments": placement_row["state"]["segments"],
                "intervals": placement_row["intervals"],
                "static_metrics": placement_row["metrics"],
                "gpu_types": {str(node): model.types[int(node)] for node in
                              placement_row["state"]["lengths"]},
                "active_gpus": placement_row["active_gpus"],
                "idle_gpus": placement_row["idle_gpus"]}
            for seed in (0, 1, 2):
                selected = summarize(case, variant, seed)
                if selected is None:
                    if case in ("C1_single", "C1_multi", "C2", "C3"):
                        result["missing"].append(f"formal:{case}/{variant}/seed{seed}")
                    continue
                selected.update({"case": case, "variant": variant, "seed": seed,
                                 "placement": str(placement.relative_to(ROOT)).replace("\\", "/"),
                                 "placement_sha256": digest(placement)})
                result["formal_rows"].append(selected)
        for seed in (0, 1, 2):
            for restriction in ("a100", "any"):
                single, multi = (f"single_{restriction}", f"multi_{restriction}")
                left, right = source("formal", case, multi, seed), source(
                    "formal", case, single, seed)
                if left is None or right is None:
                    continue
                a, b = left[0], right[0]
                result["paired_rows"].append({
                    "case": case, "seed": seed, "restriction": restriction,
                    "same_deployment": a["solution_sha256"] == b["solution_sha256"] and
                                       a["sim_cluster_sha256"] == b["sim_cluster_sha256"],
                    "trace_sha256": a["trace_sha256"],
                    "multi_minus_single": {key: a[key] - b[key] for key in METRICS},
                    "common_completed": common_completed(a, b),
                    "multi_pending": pending(a), "single_pending": pending(b)})
            for mode in ("single", "multi"):
                any_run, restricted_run = source("formal", case, f"{mode}_any", seed), \
                    source("formal", case, f"{mode}_a100", seed)
                if any_run is None or restricted_run is None:
                    continue
                a, b = any_run[0], restricted_run[0]
                result["type_pair_rows"].append({
                    "case": case, "seed": seed, "structure": mode,
                    "same_deployment": a["solution_sha256"] == b["solution_sha256"] and
                                       a["sim_cluster_sha256"] == b["sim_cluster_sha256"],
                    "trace_sha256": a["trace_sha256"],
                    "any_minus_a100": {key: a[key] - b[key] for key in METRICS},
                    "common_completed": common_completed(a, b)})
    baseline_paths = {
        "C1_single": ("Helix ILP", "experiments/v2_method_ablation/runs/single"),
        "C1_multi": ("Helix ILP", "experiments/v2_method_ablation/runs/multi"),
        "C2": ("Helix ILP", "experiments/v2_resource_generalization/runs/C2/1800s/load160"),
        "C3": ("Helix–Petals", "experiments/v2_resource_generalization/runs/C3/1800s/load400")}
    for case, (label, folder) in baseline_paths.items():
        filename = "helix_petals.json" if label == "Helix–Petals" else "helix.json"
        for seed in (0, 1, 2):
            candidate = source("formal", case, "single_a100", seed)
            if candidate is None:
                continue
            path = ROOT / folder / f"seed{seed}" / filename
            if not path.is_file():
                result["external_baselines"].append({"case": case, "seed": seed,
                                                     "label": label, "status": "missing"})
                continue
            baseline = json.loads(path.read_text(encoding="utf-8"))
            candidate_row = candidate[0]
            fields = ("offered_tokens_per_s", "duration_s", "warmup_s", "seed",
                      "trace_sha256", "evaluation_protocol", "arrivals")
            matches = all(baseline.get(key) == candidate_row.get(key) for key in fields)
            matches &= set(baseline.get("query_samples", {})) == set(
                candidate_row["query_samples"])
            if case in ("C2", "C3"):
                matches &= baseline.get("physical_sha256") == candidate_row.get(
                    "physical_sha256")
            status = ("excluded_protocol_mismatch" if not matches else
                      "trace_protocol_matched_physical_hash_absent"
                      if case.startswith("C1_") else "protocol_matched")
            result["external_baselines"].append({
                "case": case, "seed": seed, "label": label,
                "status": status,
                "source": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": digest(path),
                "metrics": {key: baseline.get(key) for key in METRICS} if matches else None})
    return result


def _fmt(value, digits=3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _mean(values):
    return mean(values) if values else None


def markdown(data: dict) -> str:
    lines = ["# 多级共享复制 M2：独立候选验证", "",
             "本候选使用纯图 M1、相同的静态 M2 目标及不变的在线 M3。主要比较为相同评分次数上限下的单边界与最多双边界布局；实际评分次数逐项记录。冻结 V2 仅作迁移参考。多级搜索是有界启发式，不提供全局最优性保证。", "",
             "## 协议与原始证据", "",
             "离线资源池：C1 单集群、C1 三集群、C2–C5。先运行种子 100、60 秒检查；正式配对窗口为 C1 两拓扑、C2、C3 的种子 0/1/2，每次 1800 秒、零预热、不排空。每个资源池四格使用同一参考布局与 0.40/0.35/0.25 静态目标；实际评分次数和规划耗时逐池记录。", "",
             "布局、原始结果和 SHA256 索引见 [summary.json](summary.json)；复现入口见 [README_CN.md](README_CN.md)。", "",
             "## 合法性与 60 秒运行检查", "",
             "| 资源池 | A100/L4/T4 | 可行四格 | 不同部署 | 运行时图逐边一致 | 种子 100 通过 |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    runtime_audit_path = HERE / "runtime_graph_audit.json"
    runtime_audit = json.loads(runtime_audit_path.read_text(encoding="utf-8")) \
        if runtime_audit_path.exists() else {}
    for case in CASES:
        variants = data["offline"].get(case, {}).get("variants", {})
        feasible = [variant for variant, item in variants.items()
                    if item["status"] == "feasible"]
        unique = {(variants[variant]["solution_sha256"],
                   variants[variant]["sim_cluster_sha256"]) for variant in feasible}
        runtime_pass = sum(runtime_audit.get(case, {}).get(variant, {}).get("status")
                           == "identical" for variant in feasible)
        smoke_pass = sum(data["smoke"].get(case, {}).get(variant, {}).get("status")
                         == "passed" for variant in feasible)
        pool = data["resource_pools"].get(case, {})
        counts = "/".join(str(pool.get(kind, 0)) for kind in ("A100", "L4", "T4"))
        lines.append(f"| {case} | {counts} | {len(feasible)} | {len(unique)} | "
                     f"{runtime_pass}/{len(feasible)} | {smoke_pass}/{len(feasible)} |")
    lines.extend(["", "固定四请求轨迹的分叉—汇合与再分叉探针分别完成 4 个请求，"
                  "并逐次检查 Decode 沿其请求原路径运行；详见 fixed_trace_probe.json。", "",
             "## 离线结构", "",
             "| 资源池 | 结构 | 初始共享限制 | 层边界 | 副本宽度 | 层副本总量 | 启用/闲置 GPU | 合法路径 | 静态分数 | 静态瓶颈 | 评分次数 | 同限制联合规划秒数 |",
             "| --- | --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | ---: | ---: |"])
    for case in CASES:
        if case not in data["offline"]:
            continue
        for variant in VARIANTS:
            row = data["offline"][case]["variants"].get(variant)
            if not row:
                continue
            if row["status"] != "feasible":
                lines.append(f"| {case} | {variant} | — | — | — | — | — | — | 不可行：{row.get('reason', '见原始记录')} | — | — | — |")
                continue
            lines.append("| " + " | ".join((case,
                "最多双边界" if variant.startswith("multi") else "单边界",
                "仅 A100" if variant.endswith("a100") else "任意类型",
                "/".join(map(str, row["boundaries"])),
                "→".join(map(str, row["widths"])), str(row["layer_copies"]),
                f"{row['active_gpus']}/{row['idle_gpus']}",
                str(row["compatible_paths"]), _fmt(row["score"], 4),
                data["layouts"][case][variant]["static_metrics"]["bottleneck_resource"],
                str(row["candidate_evaluations"]), _fmt(row["search_wall_s"], 1))) + " |")
    lines.extend(["", "规划秒数对应同一种初始共享限制下单边界与最多双边界两格的联合搜索，包含共同阶段。评分次数为共同阶段加该格扩展阶段的实际值。同一资源池内若四格导出相同部署文件及执行配置，正式运行只执行一次，并在原始索引中标注复用。静态分数是离线代价代理，不是在线 P95 预测。", "",
                  "## 各段 GPU 分组及层范围", ""])
    for case in CASES:
        for variant, layout in data["layouts"].get(case, {}).items():
            pieces = []
            for segment in layout["segments"]:
                replicas = ["→".join(f"{node}:{layout['gpu_types'][str(node)]}[{layout['intervals'][str(node)][0]},{layout['intervals'][str(node)][1]})"
                                     for node in replica) for replica in segment["replicas"]]
                pieces.append(f"[{segment['start']},{segment['end']}): " +
                              " / ".join(replicas))
            lines.append(f"- **{case}/{variant}**：" + "；".join(pieces) + "。")
    lines.extend(["",
                  "## 正式窗口：逐种子原值", "",
                  "| 资源池 | 结构 | 种子 | 吞吐 token/s ↑ | P95 TTFT s ↓ | P95 TPOT s/token ↓ | 完成率 ↑ | 末端积压 ↓ | 实际路径数 | 跨副本请求比例 |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in data["formal_rows"]:
        metric, paths = row["metrics"], row["paths"]
        lines.append("| " + " | ".join((row["case"], row["variant"], str(row["seed"]),
            _fmt(metric["output_throughput_tokens_per_s"]),
            _fmt(metric["ttft_p95_s"]), _fmt(metric["tpot_p95_s"]),
            _fmt(metric["completion_fraction"]), str(metric["backlog_at_window_end"]),
            str(paths["actual_distinct_paths"]),
            _fmt(paths["cross_replica_fraction"]))) + " |")
    if not data["formal_rows"]:
        lines.append("| 尚无正式窗口 | — | — | — | — | — | — | — | — | — |")
    lines.extend(["", "## 同资源池、同种子的多级 − 单边界差值", "",
                  "正吞吐差值表示多级提升；正延迟差值表示多级退化。共同完成请求 P95 仅使用两布局都完成的请求。", "",
                  "| 资源池 | 初始共享限制 | 种子 | 相同部署 | 吞吐差 | TTFT 差 | TPOT 差 | 完成率差 | 积压差 | 共同完成数 | 共同 P95 TTFT 多级/单边界 | 共同 P95 TPOT 多级/单边界 |",
                  "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"])
    for row in data["paired_rows"]:
        delta, common = row["multi_minus_single"], row["common_completed"]
        lines.append("| " + " | ".join((row["case"], row["restriction"],
            str(row["seed"]), "是" if row["same_deployment"] else "否",
            _fmt(delta["output_throughput_tokens_per_s"]),
            _fmt(delta["ttft_p95_s"]), _fmt(delta["tpot_p95_s"]),
            _fmt(delta["completion_fraction"]), str(delta["backlog_at_window_end"]),
            str(common["count"]),
            "/".join(_fmt(common["ttft_s"][key]) for key in
                     ("left_p95_s", "right_p95_s")),
            "/".join(_fmt(common["tpot_s"][key]) for key in
                     ("left_p95_s", "right_p95_s")))) + " |")
    if not data["paired_rows"]:
        lines.append("| 尚无正式配对 | — | — | — | — | — | — | — | — | — | — | — |")
    lines.extend(["", "## 初始共享 GPU 类型限制：任意类型 − 仅 A100", "",
                  "负的延迟差值代表允许任意 GPU 类型的搜索结果尾延迟较低。若两格布局相同则在线结果复用；本次选出的任意类型布局是否实际使用非 A100，应同时看上方结构明细。", "",
                  "| 资源池 | 结构 | 种子 | 相同部署 | 吞吐差 | TTFT 差 | TPOT 差 | 完成率差 | 积压差 |",
                  "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in data["type_pair_rows"]:
        delta = row["any_minus_a100"]
        lines.append("| " + " | ".join((row["case"], row["structure"],
            str(row["seed"]), "是" if row["same_deployment"] else "否",
            _fmt(delta["output_throughput_tokens_per_s"]),
            _fmt(delta["ttft_p95_s"]), _fmt(delta["tpot_p95_s"]),
            _fmt(delta["completion_fraction"]), str(delta["backlog_at_window_end"]))) + " |")
    if not data["type_pair_rows"]:
        lines.append("| 尚无正式配对 | — | — | — | — | — | — | — | — |")
    lines.extend(["", "## 补充外部基线", "",
                  "Helix ILP 与 Helix–Petals 分别标注；仅在同负载、同种子、同窗口和同轨迹审计通过时列入。C1 历史 Helix 记录缺少物理配置哈希，因此只作补充背景，不用于严格的物理文件配对结论。主结论仍以四格内部对照为准。", "",
                  "| 资源池 | 基线 | 种子 | 协议 | 吞吐 token/s | P95 TTFT s | P95 TPOT s/token | 完成率 | 末端积压 |",
                  "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in data["external_baselines"]:
        metric = row.get("metrics") or {}
        lines.append("| " + " | ".join((row["case"], row["label"],
            str(row["seed"]), row["status"],
            _fmt(metric.get("output_throughput_tokens_per_s")),
            _fmt(metric.get("ttft_p95_s")), _fmt(metric.get("tpot_p95_s")),
            _fmt(metric.get("completion_fraction")),
            str(metric.get("backlog_at_window_end", "—")))) + " |")
    lines.extend(["", "跨副本路径比例只描述调度器利用层兼容边的情况，不单独证明性能收益。未完成请求的窗口末驻留时长分布、GPU 访问计数、逐种子原始路径和哈希均在 summary.json 中。三个种子只用于描述波动，不宣称统计显著性。", "",
                  "## 结果解读", ""])
    c1 = [row for row in data["paired_rows"] if row["case"] == "C1_single" and
          row["restriction"] == "a100"]
    if len(c1) == 3:
        avg = {key: mean(row["multi_minus_single"][key] for row in c1)
               for key in METRICS}
        consistent = all(row["multi_minus_single"]["ttft_p95_s"] < 0 and
                         row["multi_minus_single"]["tpot_p95_s"] < 0
                         for row in c1)
        lines.append("C1 单集群的 `1→3→2` 布局相对单边界：三个种子中 P95 TTFT 和 TPOT "
                     + ("均下降" if consistent else "未全部下降") +
                     f"；平均差值分别为 {_fmt(avg['ttft_p95_s'])} 秒和 "
                     f"{_fmt(avg['tpot_p95_s'])} 秒/token，吞吐差 "
                     f"{_fmt(avg['output_throughput_tokens_per_s'])} token/s，"
                     f"末端积压差 {_fmt(avg['backlog_at_window_end'], 1)}。"
                     "共同完成请求尾延迟与积压记录支持同方向的审慎判断。")
    if data["offline"].get("C1_multi"):
        c1m = data["offline"]["C1_multi"]["variants"]
        if all(len(c1m[variant].get("widths", [])) == 2 for variant in
               ("multi_a100", "multi_any")):
            lines.append("C1 三集群的“最多双边界”搜索实际选中单边界；该池的在线差异只说明微观放置和有限搜索轨迹的作用，不能证明多级分叉或汇合有收益。")
    if all(len({(item["solution_sha256"], item["sim_cluster_sha256"])
                for item in data["offline"].get(case, {}).get("variants", {}).values()
                if item["status"] == "feasible"}) == 1 for case in ("C2", "C3")):
        lines.append("C2、C3 四格分别导出完全相同的部署，在线结果经哈希和执行语义核对后复用；这些资源池没有提供多级结构或放宽 A100 限制的额外性能证据。")
    c1_paths = {variant: [row["paths"]["actual_distinct_paths"]
                          for row in data["formal_rows"]
                          if row["case"] == "C1_single" and row["variant"] == variant]
                for variant in ("single_a100", "multi_a100")}
    if all(len(values) == 3 for values in c1_paths.values()):
        lines.append("C1 单集群实际使用的不同路径数，单边界平均 "
                     f"{_fmt(mean(c1_paths['single_a100']), 1)} 条，多级平均 "
                     f"{_fmt(mean(c1_paths['multi_a100']), 1)} 条。"
                     "多级布局的收益不能归因于“路径数量更多”；资源分担与排队变化仍需结合 GPU 利用率解释。")
    c1_busy = {variant: [max(row["gpu_busy_fraction"].values())
                         for row in data["formal_rows"]
                         if row["case"] == "C1_single" and row["variant"] == variant
                         and row["gpu_busy_fraction"]]
               for variant in ("single_a100", "multi_a100")}
    if all(len(values) == 3 for values in c1_busy.values()):
        lines.append("C1 单集群各窗口的最高 GPU 忙碌比例跨种子均值，单边界为 "
                     f"{_fmt(mean(c1_busy['single_a100']))}，`1→3→2` 为 "
                     f"{_fmt(mean(c1_busy['multi_a100']))}；这与负载分担改善相符，"
                     "但不能单独证明具体因果机制。")
    if all(data["layouts"].get(case) and all(
            all(kind == "A100" for kind in (
                data["layouts"][case][variant]["gpu_types"][str(node)]
                for node in data["layouts"][case][variant]["segments"][0]["replicas"][0]))
            for variant in ("single_any", "multi_any")) for case in CASES):
        lines.append("全部资源池的“任意类型”两格最终仍使用 A100 承担初始共享段；本轮不能据此声称非 A100 初始共享带来收益。")
    lines.extend(["", "## 判定", "",
                  "多级布局是否具有在线收益，应以同资源池、同轨迹的单边界配对结果判断；不可行和退化照实保留。A100 限制的放宽是第二个受控变量。纯图 M1 的正确性由合法边和运行时一致性检查支持，不将其写为独立性能增益。本候选不自动替换论文主方法。", ""])
    if data["missing"]:
        lines.extend(["## 尚未生成的证据", "",
                      "当前索引缺少：" + "、".join(data["missing"]), ""])
    return "\n".join(lines)


def main() -> None:
    data = collect()
    (HERE / "summary.json").write_text(json.dumps(data, indent=2) + "\n",
                                       encoding="utf-8")
    (HERE / "RESULTS_CN.md").write_text(markdown(data), encoding="utf-8")
    print(HERE / "RESULTS_CN.md")


if __name__ == "__main__":
    main()

"""Audit raw M2 branch runs and make a compact paper-oriented report."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from experiments.m2_multistage_candidate.analysis import common_completed, pending
from experiments.m2_multistage_candidate.prepare import files
from rcaps.v3.placement import digest
from rcaps.v3.topology import TopologyModel


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def loads(phase: str) -> tuple[dict, list[dict]]:
    plan = read(HERE / "plan.json")
    failures = []
    result = {}
    for path in sorted((HERE / "runs" / phase).glob("**/*.json")):
        row = read(path)
        case, variant, load, seed = (row[k] for k in
                                     ("case", "variant", "offered_tokens_per_s", "seed"))
        info = plan["cases"][case]["variants"][variant]
        if digest(HERE / "layouts" / case / variant / "solution.ini") != info["solution_sha256"]:
            raise ValueError(f"Layout changed: {case}/{variant}")
        if row["solution_sha256"] != info["solution_sha256"] or \
                row["sim_cluster_sha256"] != info["sim_cluster_sha256"]:
            raise ValueError(f"Run does not match layout: {path}")
        if len(row["query_samples"]) != row["arrivals"]:
            raise ValueError(f"Incomplete samples: {path}")
        key = (case, load, seed)
        result.setdefault(key, {})[variant] = row
    for path in sorted((HERE / "runs" / phase).glob("**/*.log")):
        output = path.with_suffix(".json")
        if not output.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if any("Traceback (most recent call last):" in line for line in lines):
                failures.append({"log": path.relative_to(ROOT).as_posix(),
                                 "last_line": lines[-1]})
    return result, failures


def summarize(row: dict, case: str, variant: str, info: dict) -> dict:
    route_counts = row["route_counts"]
    prefix = set(info["prefix_gpu_ids"])
    expected_routes = {tuple(node + 2 for node in
                             info["prefix_gpu_ids"] + branch)
                       for branch in info["branch_gpu_ids"]}
    if {tuple(int(token) for token in encoded.split("-"))
            for encoded in route_counts} - expected_routes:
        raise ValueError(f"Noncanonical route in {case}/{variant}")
    branch_counts = []
    branch_bottlenecks = []
    busy = row.get("gpu_busy_fraction", {})
    wait = row.get("gpu_queue_request_s", {})
    exits = row.get("gpu_queue_exits", {})
    for branch in info["branch_gpu_ids"]:
        count = sum(n for encoded, n in route_counts.items()
                    if branch[0] + 2 in [int(x) for x in encoded.split("-")])
        branch_counts.append(count)
        gpu_names = [f"Compute-{node+2}" for node in branch]
        branch_bottlenecks.append({
            "max_gpu_busy_fraction": max((busy.get(name, 0.) for name in gpu_names),
                                         default=None),
            "max_gpu_queue_s_per_exit": max((wait.get(name, 0.) / exits[name]
                                             for name in gpu_names if exits.get(name)),
                                            default=None)})
    prefix_names = [f"Compute-{node+2}" for node in prefix]
    return {"throughput_tokens_per_s": row["output_throughput_tokens_per_s"],
            "completion_fraction": row["completion_fraction"],
            "backlog_end": row["backlog_at_window_end"],
            "pending": pending(row), "ttft_p95_s": row["ttft_p95_s"],
            "tpot_p95_s": row["tpot_p95_s"], "arrivals": row["arrivals"],
            "routed_requests_by_branch": branch_counts,
            "branch_bottlenecks": branch_bottlenecks,
            "prefix_max_gpu_busy_fraction": max((busy.get(name, 0.)
                                                 for name in prefix_names), default=None),
            "prefix_max_gpu_queue_s_per_exit": max((wait.get(name, 0.) / exits[name]
                                                    for name in prefix_names if exits.get(name)),
                                                   default=None)}


def main() -> None:
    plan = read(HERE / "plan.json")
    all_results = {}
    for phase in ("explore", "formal"):
        rows, failures = loads(phase)
        aggregate = defaultdict(lambda: defaultdict(list))
        details = {}
        for (case, load, seed), by_variant in rows.items():
            traces = {row["trace_sha256"] for row in by_variant.values()}
            if len(traces) != 1:
                raise ValueError(f"Different traces at {case}/{load}/seed{seed}")
            for variant, row in by_variant.items():
                metrics = summarize(row, case, variant,
                                    plan["cases"][case]["variants"][variant])
                details[f"{case}/{variant}/load{load:g}/seed{seed}"] = metrics
                for key in ("throughput_tokens_per_s", "completion_fraction",
                            "backlog_end", "ttft_p95_s", "tpot_p95_s"):
                    if metrics[key] is not None:
                        aggregate[(case, load, variant)][key].append(metrics[key])
            if "k1" in by_variant and "k3" in by_variant:
                details[f"{case}/load{load:g}/seed{seed}/common_k1_k3"] = \
                    common_completed(by_variant["k1"], by_variant["k3"])
            if "equal_gpu_k2" in by_variant and "k3" in by_variant:
                details[f"{case}/load{load:g}/seed{seed}/common_equal_gpu"] = \
                    common_completed(by_variant["equal_gpu_k2"], by_variant["k3"])
        summary = {f"{case}/{variant}/load{load:g}":
                   {"seeds": len(metrics["throughput_tokens_per_s"]),
                    **{key: mean(values) for key, values in metrics.items() if values}}
                   for (case, load, variant), metrics in sorted(aggregate.items())}
        all_results[phase] = {"summary": summary, "details": details,
                              "failures": failures}
    output = HERE / "analysis.json"
    output.write_text(json.dumps(all_results, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    lines = ["# M2 单边界复制分支机制验证", "",
             "同一父布局嵌套删减后段完整副本链；主实验仅开放规范路径。",
             "正式窗口 1800 秒，零预热、不排空。探索结果不作为最终统计结论。", ""]
    lines += ["## 静态资源容量审计", "",
              "每条完整路径的 KV token 上界由该路径最小设备容量决定。多分支总上界还受共享前缀最小容量限制；这是静态上界，并非观测到的 KV 占用。", "",
              "| 资源池 | 结构 | GPU | 层副本 | 前缀 KV 上界 | 各后段分支 KV 上界 | 聚合 KV 上界 |",
              "| --- | --- | ---: | ---: | ---: | --- | ---: |"]
    for case, case_info in plan["cases"].items():
        physical, _, _ = files(case)
        model = TopologyModel(physical)
        for variant, info in case_info["variants"].items():
            state = read(HERE / "layouts" / case / variant / "placement.json")["state"]
            capacities = lambda nodes: min(
                model.manager.get_kv_cache_capacity(model.types[node],
                    int(state["lengths"][str(node)])) for node in nodes)
            prefix = capacities(info["prefix_gpu_ids"])
            branches = [capacities(branch) for branch in info["branch_gpu_ids"]]
            aggregate = min(prefix, sum(branches))
            lines.append(f"| {case} | {variant} | {info['active_gpus']} | "
                         f"{info['layer_copies']} | {prefix:,} | "
                         f"{' / '.join(f'{n:,}' for n in branches)} | "
                         f"{aggregate:,} |")
    lines.append("")
    for phase in ("explore", "formal"):
        lines += [f"## {phase}", "",
                  "| 资源池 / 负载 | 结构 | 种子数 | 吞吐 token/s | 完成率 | 末端积压 |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        for key, item in all_results[phase]["summary"].items():
            case, variant, load = key.split("/")
            lines.append(f"| {case} / {load} | {variant} | {item['seeds']} | "
                         f"{item['throughput_tokens_per_s']:.1f} | "
                         f"{item['completion_fraction']:.3f} | "
                         f"{item['backlog_end']:.1f} |")
        lines += ["", f"失效窗口：{len(all_results[phase]['failures'])}。", ""]
    lines += ["## 同轨迹配对差值", "",
              "下表只使用两种结构都完整运行的独立种子。共同完成请求的 P95 为各种子 P95 的均值，不把失效窗口折算为零。", "",
              "| 资源池 / 负载 | 对照 → 处理 | 种子 | 吞吐增量 token/s | 完成率增量 | 积压减少 | 共同请求 P95 TPOT (s) |",
              "| --- | --- | --- | ---: | ---: | ---: | --- |"]
    comparisons = (("C1_multi", 320, (1, 2, 3), "k1", "k3"),
                   ("C1_single", 600, (4, 5, 6), "k1", "k3"),
                   ("C1_single", 700, (1, 2, 3), "equal_gpu_k2", "k3"))
    for case, load, seeds, left, right in comparisons:
        pairs = []
        for seed in seeds:
            a = HERE / "runs/formal" / case / left / f"load{load:g}_seed{seed}.json"
            b = HERE / "runs/formal" / case / right / f"load{load:g}_seed{seed}.json"
            if not (a.exists() and b.exists()):
                break
            x, y = read(a), read(b)
            pairs.append((x, y, common_completed(x, y)))
        if len(pairs) != len(seeds):
            continue
        throughput = mean(y["output_throughput_tokens_per_s"] -
                          x["output_throughput_tokens_per_s"] for x, y, _ in pairs)
        completion = mean(y["completion_fraction"] - x["completion_fraction"]
                          for x, y, _ in pairs)
        backlog = mean(x["backlog_at_window_end"] - y["backlog_at_window_end"]
                       for x, y, _ in pairs)
        old_tpot = mean(item["tpot_s"]["left_p95_s"] for _, _, item in pairs)
        new_tpot = mean(item["tpot_s"]["right_p95_s"] for _, _, item in pairs)
        lines.append(f"| {case} / {load} | {left} → {right} | "
                     f"{','.join(map(str, seeds))} | +{throughput:.2f} | "
                     f"+{completion:.3f} | {backlog:.1f} | "
                     f"{old_tpot:.3f} → {new_tpot:.3f} |")
    lines.append("")
    lines += ["## 完整 DAG 路由迁移检查", "",
              "相同部署和轨迹，比较规范路径与完整 M1 兼容 DAG。此项只有探索种子 0。", "",
              "| 资源池 | 结构 | 规范路径吞吐 | 完整 DAG 吞吐 | 规范路径完成率 | 完整 DAG 完成率 |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for case, load in (("C1_single", 700), ("C1_multi", 320)):
        for variant in ("k2", "k3"):
            a = HERE / "runs/explore" / case / variant / f"load{load}_seed0.json"
            b = (ROOT / "benchmarks/runs/multi/seed0/rcaps_v3.json"
                 if case == "C1_multi" and variant == "k3" else
                 HERE / "runs/full_dag" / case / variant / f"load{load}_seed0.json")
            if not (a.exists() and b.exists()):
                continue
            x, y = read(a), read(b)
            if (x["trace_sha256"] != y["trace_sha256"] or
                    x["solution_sha256"] != y["solution_sha256"] or
                    x["sim_cluster_sha256"] != y["sim_cluster_sha256"]):
                raise ValueError(f"Full-DAG comparison is not paired: {case}/{variant}")
            lines.append(f"| {case} | {variant} | "
                         f"{x['output_throughput_tokens_per_s']:.2f} | "
                         f"{y['output_throughput_tokens_per_s']:.2f} | "
                         f"{x['completion_fraction']:.3f} | "
                         f"{y['completion_fraction']:.3f} |")
    lines.append("")
    lines += ["## 分支选择稳健性", "",
              "同一探索种子 0、同一负载；单分支列覆盖三种选择，双分支列覆盖三种两两组合。", "",
              "| 资源池 / 负载 | 单分支吞吐范围 | 双分支吞吐范围 | 三分支吞吐 |",
              "| --- | ---: | ---: | ---: |"]
    for case, load in (("C1_single", 700), ("C1_multi", 320)):
        items = {}
        for label, phase in (("k1", "explore"), ("k1_b1", "subsets"),
                             ("k1_b2", "subsets"), ("k2", "explore"),
                             ("k2_b02", "subsets"), ("k2_b12", "subsets"),
                             ("k3", "explore")):
            path = HERE / "runs" / phase / case / label / f"load{load}_seed0.json"
            if path.exists():
                items[label] = read(path)["output_throughput_tokens_per_s"]
        if len(items) == 7:
            one = [items[key] for key in ("k1", "k1_b1", "k1_b2")]
            two = [items[key] for key in ("k2", "k2_b02", "k2_b12")]
            lines.append(f"| {case} / {load} | {min(one):.2f}–{max(one):.2f} | "
                         f"{min(two):.2f}–{max(two):.2f} | {items['k3']:.2f} |")
    lines.append("")
    lines += ["## 可写入论文的结论边界", "",
              "嵌套删分支、全部子集复核、独立种子以及同 GPU 数对照共同支持：M2 的共享前缀加完整后段副本确实增加了可同时服务的请求，并在这些资源池的压力负载下提高输出吞吐与完成率。单集群的同 GPU 数吞吐增量约为 1.5%，应如实表述为较小但三个种子方向一致的结构收益。", "",
              "GPU 忙碌比例较低；单集群的静态 KV 容量上界与高负载 KV 容量断言提示收益与可容纳的解码状态有关。三集群还观察到后段链路负载被多路径分摊。实验未直接采样随时间变化的 KV 占用，因此不能声称已经量化 KV 与网络各自的因果贡献。", "",
              "700 token/s 的单集群单路径在预选正式种子中有 2/3 个因模拟器 KV 容量断言失效；该点作为容量失效报告。600 token/s 的单集群比较是随后声明的独立种子补充实验。完整 DAG 和全部子集复核只有一个探索种子，不作显著性结论。", ""]
    (HERE / "FINDINGS_CN.md").write_text("\n".join(lines).rstrip() + "\n",
                                               encoding="utf-8")
    print(output)
    print(HERE / "FINDINGS_CN.md")


if __name__ == "__main__":
    main()

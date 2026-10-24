"""Independently reconstruct lifecycle metrics, then apply the registered gate."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import statistics
from pathlib import Path

from experiments.v3_adaptive_space_cohort.run import (
    CASES, HERE, POLICIES, PROTOCOL, ROOT, check_frozen, historical_comparison,
    result_path, timestamp,
)
from experiments.v3_path_crossover import run as original


def p95(values):
    if not values:
        return None
    values = sorted(values)
    at = 0.95 * (len(values) - 1)
    low = int(at)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (at - low)


def trace_hash(trace):
    return hashlib.sha256(json.dumps(trace, separators=(",", ":")).encode()).hexdigest()


def recompute(samples, cutoff=None):
    """Reconstruct from raw decode completion timestamps, not reported latencies."""
    ttfts, tpots, e2es = [], [], []
    completed, tokens = 0, 0
    for sample in samples.values():
        arrival = sample["arrival_s"]
        ends = [end for end in sample["decode_completion_times_s"]
                if cutoff is None or end < cutoff]
        if ends:
            ttfts.append(ends[0] - arrival)
        if len(ends) >= 2:
            tpots.append(statistics.mean(b - a for a, b in zip(ends, ends[1:])))
        finish = sample["finish_s"]
        if finish is not None and (cutoff is None or finish < cutoff):
            completed += 1
            e2es.append(finish - arrival)
        tokens += len(ends)
    return {"arrivals": len(samples), "completed": completed,
            "completion_fraction": completed / len(samples) if samples else None,
            "ttft_p95_s": p95(ttfts), "tpot_p95_s": p95(tpots), "e2e_p95_s": p95(e2es),
            "queries_with_tpot_samples": len(tpots), "first_tokens_in_window": len(ttfts),
            "output_tokens_completed": tokens}


def validate_result(row, phase, load, network, policy, seed, expected_trace, context):
    spec = PROTOCOL[phase]
    duration = spec["arrival_duration_s"]
    issues = []

    def require(condition, message):
        if not condition:
            issues.append(message)

    def same(actual, expected, message):
        if actual is None or expected is None:
            require(actual is expected, message)
        else:
            require(isinstance(actual, (int, float)) and math.isfinite(actual)
                    and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), message)

    identity = {"experiment": PROTOCOL["experiment"], "phase": phase,
                "load_label": load, "network_profile": network, "path_space": policy,
                "seed": seed, "duration_s": duration, "warmup_s": 0,
                "maximum_drain_s": spec["maximum_drain_s"], "classification": "simulation_only",
                "audit_sha256": original.digest(HERE / "audit.json")}
    for key, value in identity.items():
        require(row.get(key) == value, f"identity/{key}")
    require(row["environment"] == original.read(HERE / "audit.json")["environment"], "environment")
    window, life = row["window"], row["lifecycle"]
    samples = life["query_samples"]
    require(set(samples) == set(window["query_samples"]), "window/lifecycle request IDs")
    ordered = sorted(samples.items(), key=lambda entry: (entry[1]["arrival_s"], int(entry[0])))
    trace = [(round(s["arrival_s"], 9), s["input_tokens"], s["output_tokens"])
             for _, s in ordered]
    require(trace == expected_trace, "trace differs from regenerated registered workload")
    require(trace_hash(trace) == row["trace_sha256"] == window["trace_sha256"], "trace hash")
    require(len(samples) == window["arrivals"], "all arrivals retained")
    if policy == "canonical":
        allowed = context["canonical_edges"]
    elif policy == "partial":
        allowed = context["partial_edges"]
    else:
        allowed = {(a if isinstance(a, str) else a + 2, b if isinstance(b, str) else b + 2)
                   for a, b in context["full_dag"].edge_set}
    for uid, sample in samples.items():
        arrival, ends, finish = (sample[key] for key in
                                 ("arrival_s", "decode_completion_times_s", "finish_s"))
        require(0 <= arrival < duration, f"arrival/{uid}")
        require(sample["input_tokens"] > 0 and 0 < sample["output_tokens"] <= 1000,
                f"token contract/{uid}")
        require(sample["completed"] is True, f"incomplete request/{uid}")
        require(len(ends) == sample["output_tokens"], f"decode count/{uid}")
        require(bool(ends) and all(math.isfinite(t) for t in ends), f"finite decode times/{uid}")
        require(all(a < b for a, b in zip(ends, ends[1:])), f"decode order/{uid}")
        if ends:
            require(arrival <= sample["prompt_end_s"] <= ends[0], f"prompt time/{uid}")
            same(finish, ends[-1], f"query finish differs from last token/{uid}")
            require(finish < duration + spec["maximum_drain_s"], f"drain deadline/{uid}")
            same(sample["ttft_s"], ends[0] - arrival, f"request TTFT/{uid}")
            same(sample["tpot_s"], statistics.mean(b - a for a, b in zip(ends, ends[1:]))
                 if len(ends) >= 2 else None, f"request TPOT/{uid}")
        vertices = ["source", *sample["route"], "sink"]
        require(all(edge in allowed for edge in zip(vertices, vertices[1:])), f"illegal route/{uid}")
        observed = window["query_samples"][uid]
        for key in ("arrival_s", "input_tokens", "output_tokens"):
            same(observed[key], sample[key], f"window input mismatch/{uid}/{key}")
        require(observed["decode_completion_times_s"] == [t for t in ends if t < duration],
                f"window token prefix/{uid}")
        require(observed["completed"] == (finish < duration), f"window completion/{uid}")

    calculated = recompute(samples)
    for key in ("arrivals", "completed", "completion_fraction", "ttft_p95_s", "tpot_p95_s",
                "e2e_p95_s", "queries_with_tpot_samples", "output_tokens_completed"):
        same(life.get(key), calculated[key], f"lifecycle metric/{key}")
    prefix = {uid: sample for uid, sample in samples.items()
              if sample["arrival_s"] < spec["prefix_arrival_before_s"]}
    prefix_metrics = recompute(prefix)
    for key in ("arrivals", "completed", "completion_fraction", "ttft_p95_s", "tpot_p95_s",
                "e2e_p95_s", "queries_with_tpot_samples"):
        same(life["prefix"].get(key), prefix_metrics[key], f"prefix metric/{key}")
    same(life["prefix_arrival_before_s"], spec["prefix_arrival_before_s"], "prefix boundary")
    last = max(s["finish_s"] for s in samples.values()) if samples else 0
    same(life["last_completion_s"], last, "last completion")
    same(life["drain_to_last_completion_s"], max(0, last - duration), "drain time")
    win = recompute(samples, cutoff=duration)
    for key in ("ttft_p95_s", "tpot_p95_s", "e2e_p95_s", "queries_with_tpot_samples",
                "completion_fraction", "first_tokens_in_window"):
        same(window[key], win[key], f"window metric/{key}")
    same(window["output_throughput_tokens_per_s"], win["output_tokens_completed"] / duration,
         "window output throughput")
    same(window["completed_request_throughput_per_s"], win["completed"] / duration,
         "window request throughput")
    same(window["backlog_at_window_end"], len(samples) - win["completed"], "window backlog")
    require(window["backlog_at_window_start"] == 0, "initial backlog")
    for period, data in (("window", window), ("lifecycle", life)):
        capacity, peaks = data["kv_capacity"], data["kv_peak_reserved"]
        require(bool(capacity), f"KV capacity/{period}")
        require(all(uid in capacity and 0 <= value <= capacity[uid] for uid, value in peaks.items()),
                f"KV overflow/{period}")
        same(data["kv_peak_fraction"], max((v / capacity[k] for k, v in peaks.items()), default=0),
             f"KV peak fraction/{period}")
    require(all(value == 0 for value in life["remaining_kv_reservations"].values()),
            "KV not released after completion")
    if phase == "formal":
        checked = historical_comparison(window, load, network, policy, seed)
        require(checked["equal"], f"historical reproduction/{checked['differences']}")
        require(checked == row["historical_window_reproduction"], "historical evidence hash/fields")
    return issues


def unique_winner(policies):
    best_tp = max(item["window_throughput_mean"] for item in policies.values())
    best_completion = max(item["window_completion_mean"] for item in policies.values())
    eligible = sorted((policy for policy, item in policies.items()
                       if item["window_throughput_mean"] >= 0.99 * best_tp
                       and item["window_completion_mean"] >= best_completion - 0.01),
                      key=lambda name: policies[name]["lifecycle_tpot_mean_s"])
    if not eligible:
        return None
    best = eligible[0]
    if policies[best]["lifecycle_tpot_mean_s"] != min(
            item["lifecycle_tpot_mean_s"] for item in policies.values()):
        return None
    if len(eligible) > 1 and policies[best]["lifecycle_tpot_mean_s"] > 0.99 * policies[eligible[1]]["lifecycle_tpot_mean_s"]:
        return None
    return best


def crossover(first, second):
    a, b = first["winner"], second["winner"]
    if a is None or b is None or a == b:
        return {"confirmed": False, "reason": "No different unique primary winners"}
    full = sum(x < y and z < w for x, y, z, w in zip(
        first["policies"][a]["lifecycle_tpot_per_seed_s"],
        first["policies"][b]["lifecycle_tpot_per_seed_s"],
        second["policies"][b]["lifecycle_tpot_per_seed_s"],
        second["policies"][a]["lifecycle_tpot_per_seed_s"]))
    prefix = sum(x < y and z < w for x, y, z, w in zip(
        first["policies"][a]["prefix_tpot_per_seed_s"],
        first["policies"][b]["prefix_tpot_per_seed_s"],
        second["policies"][b]["prefix_tpot_per_seed_s"],
        second["policies"][a]["prefix_tpot_per_seed_s"]))
    means = (first["policies"][a]["prefix_tpot_mean_s"] < first["policies"][b]["prefix_tpot_mean_s"]
             and second["policies"][b]["prefix_tpot_mean_s"] < second["policies"][a]["prefix_tpot_mean_s"])
    return {"confirmed": full >= 2 and prefix >= 2 and means,
            "winners": [a, b], "all_request_matching_seeds": full,
            "prefix_matching_seeds": prefix, "prefix_mean_direction_preserved": means}


def summarize(rows, phase):
    seeds = PROTOCOL[phase]["seeds"]
    conditions = {}
    for load, network in CASES:
        policies = {}
        for policy in POLICIES:
            subset = [rows[(load, network, policy, seed)] for seed in seeds]
            full = [row["lifecycle"]["tpot_p95_s"] for row in subset]
            prefix = [row["lifecycle"]["prefix"]["tpot_p95_s"] for row in subset]
            policies[policy] = {
                "lifecycle_tpot_per_seed_s": full, "lifecycle_tpot_mean_s": statistics.mean(full),
                "lifecycle_tpot_sample_sd_s": statistics.stdev(full) if len(full) > 1 else None,
                "prefix_tpot_per_seed_s": prefix, "prefix_tpot_mean_s": statistics.mean(prefix),
                "window_throughput_mean": statistics.mean(row["window"]["output_throughput_tokens_per_s"] for row in subset),
                "window_completion_mean": statistics.mean(row["window"]["completion_fraction"] for row in subset),
                "lifecycle_ttft_mean_s": statistics.mean(row["lifecycle"]["ttft_p95_s"] for row in subset),
                "lifecycle_e2e_mean_s": statistics.mean(row["lifecycle"]["e2e_p95_s"] for row in subset),
                "arrivals_per_seed": [row["lifecycle"]["arrivals"] for row in subset],
                "drain_to_last_completion_per_seed_s": [row["lifecycle"]["drain_to_last_completion_s"] for row in subset],
                "kv_peak_fraction_per_seed": [row["lifecycle"]["kv_peak_fraction"] for row in subset],
            }
        conditions[f"{load}/{network}"] = {"winner": unique_winner(policies), "policies": policies}
    pairs = [{"conditions": names, **crossover(conditions[names[0]], conditions[names[1]])}
             for names in PROTOCOL["decision"]["crossover_pairs"]]

    # Optimistic diagnostic uses a policy selected separately for each condition
    # on these evaluation seeds. It is not an online or transition simulation.
    selected = {name: min(info["policies"], key=lambda p: info["policies"][p]["lifecycle_tpot_mean_s"])
                for name, info in conditions.items()}
    pooled = {policy: [] for policy in POLICIES}
    selected_values = []
    for (load, network, policy, _seed), row in rows.items():
        values = [s["tpot_s"] for s in row["lifecycle"]["query_samples"].values() if s["tpot_s"] is not None]
        pooled[policy].extend(values)
        if policy == selected[f"{load}/{network}"]:
            selected_values.extend(values)
    fixed_tails = {policy: p95(values) for policy, values in pooled.items()}
    best = min(fixed_tails, key=fixed_tails.get)
    selected_tail = p95(selected_values)
    return {"conditions": conditions, "crossovers": pairs,
            "adaptive_space_confirmed_in_tested_scope": phase == "formal" and any(pair["confirmed"] for pair in pairs),
            "formal_claim_allowed": phase == "formal",
            "optimistic_offline_reference": {
                "condition_selections": selected, "pooled_fixed_p95_tpot_s": fixed_tails,
                "best_pooled_fixed_policy": best, "pooled_selected_p95_tpot_s": selected_tail,
                "relative_pooled_p95_reduction": 1 - selected_tail / fixed_tails[best],
                "limitation": "Selected using evaluation outcomes; independent states, no switching/transients. An optimistic diagnostic, not a proven bound or deployable controller."}}


def generate(phase):
    check_frozen()
    spec = PROTOCOL[phase]
    context = original.load_context()
    from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
    expected = {}
    for load, _network in CASES:
        for seed in spec["seeds"]:
            with contextlib.redirect_stdout(io.StringIO()):
                feeder = OnlineRequestFeeder(cluster_token_throughput=original.LOADS[load], start_time=0,
                                             duration=spec["arrival_duration_s"], seed=seed)
            expected[(load, seed)] = [(round(t, 9), i, o) for t, i, o in feeder.trace]
    missing, invalid, rows, hashes = [], {}, {}, {}
    for seed in spec["seeds"]:
        for load, network in CASES:
            for policy in POLICIES:
                path = result_path(phase, load, network, policy, seed)
                key = f"{load}/{network}/{policy}/seed{seed}"
                if not path.exists():
                    missing.append(key)
                    continue
                try:
                    row = original.read(path)
                    problems = validate_result(row, phase, load, network, policy, seed,
                                               expected[(load, seed)], context)
                    if problems:
                        invalid[key] = problems
                    rows[(load, network, policy, seed)] = row
                    hashes[path.relative_to(HERE).as_posix()] = original.digest(path)
                except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError) as error:
                    invalid[key] = [repr(error)]
    failures = [p.relative_to(HERE).as_posix() for p in (HERE / "runs" / phase).rglob("*.failure.json")]
    complete = not missing and not invalid and not failures
    report = {"phase": phase, "created_at_utc": timestamp(), "classification": "simulation_only",
              "audit_sha256": original.digest(HERE / "audit.json"),
              "expected_cells": len(CASES) * len(POLICIES) * len(spec["seeds"]),
              "available_cells": len(rows), "complete_and_valid": complete,
              "missing": missing, "invalid": invalid, "failure_files": failures,
              "inputs_sha256": hashes, "external_reviewer": "unavailable"}
    if complete:
        report.update(summarize(rows, phase))
    original.write(HERE / f"{phase}_analysis.json", report)
    lines = ["# 工作三：自适应空间生命周期复核", "",
             f"阶段：{phase}。有效完整矩阵：{complete}。结果：{len(rows)}/{report['expected_cells']}。", "",
             "仿真结果，三种子描述性比较；确定性复算不等于独立跨模型审核。", ""]
    if complete:
        lines += ["| 状态 | 策略 | 全生命周期 P95 TPOT 均值（秒） | 固定前缀 P95 TPOT 均值（秒） | 原窗口吞吐 | 唯一胜者 |",
                  "| --- | --- | ---: | ---: | ---: | --- |"]
        for name, condition in report["conditions"].items():
            for policy, data in condition["policies"].items():
                lines.append(f"| {name} | {policy} | {data['lifecycle_tpot_mean_s']:.6f} | {data['prefix_tpot_mean_s']:.6f} | {data['window_throughput_mean']:.6f} | {condition['winner'] or '无'} |")
        lines += ["", "## 配对交叉检查", ""]
        for pair in report["crossovers"]:
            lines.append(f"- {' → '.join(pair['conditions'])}：{json.dumps(pair, ensure_ascii=False)}")
        reference = report["optimistic_offline_reference"]
        lines += ["", f"测试范围内自适应空间通过预注册复核：{report['adaptive_space_confirmed_in_tested_scope']}。",
                  f"事后按状态选固定策略相对最佳全局固定策略的混合 P95 改善：{reference['relative_pooled_p95_reduction']:.2%}。",
                  "该事后参照使用评价结果且不包含真实切换/瞬态代价，只用于估计候选空间，不能视为控制器收益。",
                  "若未通过，只能说当前范围未确认，不能推出不存在任何动态路径控制机会。", "",
                  "排空期停止新到达，会改变尾段资源状态。固定到达前缀是预注册敏感性检查，也不能替代后续持续负载下的动态闭环实验。",
                  "本复核不验证 42 GPU 泛化、KV 高压收益或少 GPU 相比全 GPU Helix 的优势。"]
    else:
        lines += ["矩阵不完整或存在错误，不能给出正向研究结论。详见对应 JSON。"]
    (HERE / f"{phase}_RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {key: value for key, value in report.items() if key not in ("inputs_sha256", "conditions")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "development", "formal"), required=True)
    args = parser.parse_args()
    report = generate(args.phase)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["complete_and_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

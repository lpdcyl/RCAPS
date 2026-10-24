"""Recompute endpoint, work and control evidence before applying the gate."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from statistics import mean

from experiments.v3_adaptive_space_cohort.report import recompute
from experiments.v3_path_crossover import run as original


def execution_metrics(events, horizon):
    total = window = 0.0
    batches = tokens = single = prompts = 0
    per_gpu = {}
    for start, duration, uid, layer, decodes, prompt in events:
        total += duration
        window += max(0.0, min(start + duration, horizon) - max(0.0, start))
        per_gpu[str(uid)] = per_gpu.get(str(uid), 0.0) + duration
        if decodes:
            batches += 1
            tokens += decodes
            single += decodes == 1
        prompts += prompt
    return {"gpu_seconds_lifecycle": total, "gpu_seconds_window": window,
            "decode_layer_executions": batches, "decode_request_layer_executions": tokens,
            "prompt_request_layer_executions": prompts,
            "mean_decode_batch": tokens / batches if batches else None,
            "single_decode_batch_fraction": single / batches if batches else None,
            "gpu_seconds_per_gpu": per_gpu}


def trace_hash(trace):
    payload = [(round(t, 9), p, o) for t, p, o in trace]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def validate(row, events, expected_trace, context):
    issues = []

    def require(condition, message):
        if not condition:
            issues.append(message)

    def same(a, b, label):
        if a is None or b is None:
            require(a is b, label)
        else:
            require(isinstance(a, (int, float)) and math.isfinite(a) and
                    math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), label)

    samples = row["lifecycle"]["query_samples"]
    window = row["window"]
    ordered = sorted(samples.items(), key=lambda pair: (pair[1]["arrival_s"], int(pair[0])))
    recovered = [[round(s["arrival_s"], 9), s["input_tokens"], s["output_tokens"]]
                 for _, s in ordered]
    expected = [[round(t, 9), p, o] for t, p, o in expected_trace]
    require(recovered == expected, "regenerated arrival trace")
    require(row["trace"] == [list(item) for item in expected_trace], "stored trace")
    require(trace_hash(expected_trace) == row["trace_sha256"] == window["trace_sha256"], "trace hash")
    require(set(samples) == set(window["query_samples"]), "window cohort IDs")
    full_edges = frozenset((a if isinstance(a, str) else a+2,
                            b if isinstance(b, str) else b+2) for a,b in context["full_dag"].edge_set)
    allowed = (context["canonical_edges"] if row["policy"] == "canonical" else
               context["partial_edges"] if row["policy"] == "partial" else full_edges)
    for uid, sample in samples.items():
        ends, finish, arrival = (sample[k] for k in ("decode_completion_times_s", "finish_s", "arrival_s"))
        require(sample["completed"] is True, f"completed/{uid}")
        require(len(ends) == sample["output_tokens"] and len(ends) > 0, f"decode count/{uid}")
        require(0 < sample["output_tokens"] <= 1000 and sample["input_tokens"] > 0, f"length contract/{uid}")
        require(all(math.isfinite(t) for t in ends) and all(a < b for a,b in zip(ends,ends[1:])), f"time order/{uid}")
        require(0 <= arrival < row["duration_s"], f"arrival/{uid}")
        require(arrival <= sample["prompt_end_s"] <= ends[0] <= finish, f"prompt timing/{uid}")
        same(finish, ends[-1], f"finish/{uid}")
        same(sample["ttft_s"], ends[0]-arrival, f"TTFT/{uid}")
        same(sample["tpot_s"], mean(b-a for a,b in zip(ends,ends[1:])) if len(ends)>1 else None, f"TPOT/{uid}")
        vertices = ["source", *sample["route"], "sink"]
        require(all(edge in allowed for edge in zip(vertices, vertices[1:])), f"route legality/{uid}")
        boundary = 0
        for _, node, layers in sample["route_stages"][:-1]:
            span = context["full_dag"].spans[node-2]
            require(span[0] <= boundary < span[1], f"route boundary/{uid}")
            require(layers == list(range(boundary, span[1])), f"route layers/{uid}")
            boundary = span[1]
        require(boundary == context["full_dag"].layers, f"full layer coverage/{uid}")
        observed = window["query_samples"][uid]
        require(observed["decode_completion_times_s"] == [t for t in ends if t < row["duration_s"]], f"window token prefix/{uid}")
        require(observed["completed"] == (finish < row["duration_s"]), f"window completion/{uid}")
    life_recomputed, win_recomputed = recompute(samples), recompute(samples, row["duration_s"])
    for key in ("arrivals", "completed", "completion_fraction", "ttft_p95_s", "tpot_p95_s", "e2e_p95_s", "queries_with_tpot_samples", "output_tokens_completed"):
        same(row["lifecycle"][key], life_recomputed[key], f"lifecycle/{key}")
    for key in ("ttft_p95_s", "tpot_p95_s", "e2e_p95_s", "completion_fraction", "queries_with_tpot_samples"):
        same(window[key], win_recomputed[key], f"window/{key}")
    same(window["output_throughput_tokens_per_s"], win_recomputed["output_tokens_completed"]/row["duration_s"], "window output throughput")
    same(row["decode_route_checks"], life_recomputed["output_tokens_completed"], "every decode route checked")
    same(row["route_count"], len(samples), "probes did not inflate route count")
    same(row["kv_admission"]["admitted"], len(samples), "admission count")
    if "statistics_contract" in row:
        require(row["statistics_contract"]["calls"]>0 and row["statistics_contract"]["violations"]==0,
                "pure layer statistics return contract")
    for uid, peak in row["kv_peak_reserved"].items():
        require(0 <= peak <= row["kv_capacity"][uid], f"KV overflow/{uid}")
    require(all(v == 0 for v in row["remaining_kv"].values()), "KV reservations released")
    require(all(math.isfinite(d) and d > 0 and t >= -1e-8 and n >= 0 and p >= 0 and n+p>0
                for t,d,u,l,n,p in events), "execution event contract")
    work = execution_metrics(events, row["duration_s"])
    require(work == row["execution"], "execution metrics recomputed")
    same(work["decode_request_layer_executions"], life_recomputed["output_tokens_completed"]*context["full_dag"].layers, "decode layer conservation")
    same(work["prompt_request_layer_executions"], len(samples)*context["full_dag"].layers, "prompt layer conservation")
    if row["policy"] == "route_control":
        require(len(row["control_events"]) == len(samples), "control decisions per admission")
        seen = set()
        for event in row["control_events"]:
            uid = str(event["query_uid"])
            require(uid not in seen and uid in samples, "control request identity")
            seen.add(uid)
            chosen = event["expanded"] if event["selected_expanded"] else event["baseline"]
            require(chosen == samples[uid]["route_stages"], f"chosen route/{uid}")
            if event["capacity_fallback"]:
                continue
            same(event["cost_baseline_s"], sum(event["terms_baseline"].values()), f"cost baseline/{uid}")
            same(event["cost_expanded_s"], sum(event["terms_expanded"].values()), f"cost expanded/{uid}")
            penalty = max(0,event["batch_expanded_s"]-event["batch_baseline_s"])
            same(event["batch_penalty_s"], penalty, f"penalty/{uid}")
            same(event["net_proxy_s"], event["cost_baseline_s"]-event["cost_expanded_s"]-penalty, f"net proxy/{uid}")
            if event["selected_expanded"]:
                require(event["gate_open"] and event["net_proxy_s"]>0 and event["candidates_differ"], f"gate selected/{uid}")
    return issues


def compact(row):
    life, window, work = row["lifecycle"], row["window"], row["execution"]
    return {"tpot": life["tpot_p95_s"], "ttft": life["ttft_p95_s"],
            "throughput": window["output_throughput_tokens_per_s"],
            "window_completion": window["completion_fraction"],
            "gpu_per_token": work["gpu_seconds_lifecycle"]/life["output_tokens_completed"],
            "window_gpu_per_token": work["gpu_seconds_window"]/(window["output_throughput_tokens_per_s"]*row["duration_s"]),
            "batch": work["mean_decode_batch"], "single_share": work["single_decode_batch_fraction"],
            "expanded_selected": row["control_counts"].get("expanded_selected",0),
            "different_candidates": row["control_counts"].get("different_candidates",0),
            "switches": row["control_switches"], "kv_deferred": row["kv_admission"]["deferred_checks"],
            "route_cpu_p95_us": window["scheduler_call_profile"]["_route"]["p95_us"]}


def decide(metrics, seeds):
    paired = []
    fixed = ("canonical", "partial", "full")
    for seed in seeds:
        data = metrics[str(seed)]
        candidate, legacy = data["route_control"], data["adaptive_link"]
        best = min(fixed, key=lambda p: data[p]["tpot"])
        ref = data[best]
        latency_gain = 1-candidate["tpot"]/ref["tpot"]
        latency_pass = (latency_gain > 0 and candidate["throughput"] >= 0.99*ref["throughput"]
                        and candidate["ttft"] <= 1.02*ref["ttft"]
                        and candidate["gpu_per_token"] <= 1.01*ref["gpu_per_token"]
                        and candidate["tpot"] < legacy["tpot"])
        fastest = min(data[p]["tpot"] for p in fixed)
        highest = max(data[p]["throughput"] for p in fixed)
        eligible = [p for p in fixed if data[p]["tpot"] <= 1.02*fastest and data[p]["throughput"] >= 0.99*highest]
        efficient = min(eligible, key=lambda p: data[p]["gpu_per_token"]) if eligible else None
        efficiency_gain = (1-candidate["gpu_per_token"]/data[efficient]["gpu_per_token"]
                           if efficient else None)
        efficiency_pass = (efficient is not None and candidate["tpot"] <= 1.02*fastest
            and candidate["throughput"] >= 0.99*highest and efficiency_gain > 0
            and candidate["gpu_per_token"] < legacy["gpu_per_token"])
        action = candidate["expanded_selected"] > 0
        paired.append({"seed":seed, "best_latency_fixed":best, "latency_gain":latency_gain,
                       "latency_guardrails_pass":latency_pass, "best_eligible_efficiency_fixed":efficient,
                       "efficiency_gain":efficiency_gain, "efficiency_guardrails_pass":efficiency_pass,
                       "actual_control_action":action})
    latency = all(p["latency_guardrails_pass"] and p["actual_control_action"] for p in paired) and mean(p["latency_gain"] for p in paired)>=0.03
    efficiency = (all(p["efficiency_guardrails_pass"] and p["actual_control_action"] for p in paired)
                  and mean(p["efficiency_gain"] for p in paired)>=0.10)
    return {"paired":paired, "latency_branch_pass":latency, "efficiency_branch_pass":efficiency,
            "performance_gate_pass":latency or efficiency,
            "formal_authorized_by_this_report":False,
            "next":("Assess mechanism and overhead before registering formal protocol" if latency or efficiency
                    else "STOP current candidate; preserve negative evidence; no expanded sweep or formal matrix")}


def generate(revision, phase="development"):
    from work3_control.run import HERE, ROOT, PROTOCOL, POLICIES, check_frozen, trace_for
    check_frozen(revision)
    context = original.load_context()
    seeds = [PROTOCOL["smoke_seed"]] if phase=="smoke" else PROTOCOL["development_seeds"]
    metrics, validation, rows = {}, [], []
    for seed in seeds:
        metrics[str(seed)] = {}
        expected = trace_for(seed, PROTOCOL["stage_duration_s"][phase])
        for policy in POLICIES:
            path = HERE/"runs"/revision/phase/f"{policy}_seed{seed}.json"
            row = original.read(path)
            with gzip.open(ROOT/row["execution_source"],"rt",encoding="utf-8") as stream:
                events = json.load(stream)
            problems = validate(row, events, expected, context)
            if original.digest(ROOT/row["execution_source"]) != row["execution_sha256"]:
                problems.append("execution artifact hash")
            if row["audit_sha256"] != original.digest(HERE/"audits"/f"{revision}.json"):
                problems.append("audit identity")
            validation.append({"policy":policy,"seed":seed,"issues":problems,
                               "source":str(path.relative_to(ROOT)),"sha256":original.digest(path)})
            if problems:
                original.write(HERE/"runs"/revision/f"{phase}_validation.json",validation)
                raise ValueError(f"Integrity failure {policy}/{seed}: {problems[:8]}")
            metrics[str(seed)][policy] = compact(row)
            rows.append(row)
    decision = decide(metrics,seeds) if phase=="development" else {"smoke_valid":True}
    result = {"revision":revision,"phase":phase,"classification":"simulation_only",
              "metrics":metrics,"validation":validation,"decision":decision,
              "independent_review":"Unavailable; deterministic checks only"}
    folder = HERE/"runs"/revision
    original.write(folder/f"{phase}_analysis.json",result)
    lines=["# 工作三完整路径门控："+("开发结果" if phase=="development" else "烟测"),"",
           "环境：显式激活 gllm；每格独立解释器；离散事件仿真。历史冻结源码未修改。","",
           "指标采用全部到达请求完整生命周期；吞吐仅使用到达窗口输出 token。GPU 秒/token 为全部实际执行工作量/实际输出，不是实体 GPU 测量。","",
           "| 种子 | 方法 | P95 TPOT s | P95 TTFT s | 窗口输出 token/s | GPU 秒/token | 平均 Decode 批 | 新增选路 |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for seed in seeds:
        for policy,item in metrics[str(seed)].items():
            lines.append(f"| {seed} | {policy} | {item['tpot']:.6f} | {item['ttft']:.6f} | {item['throughput']:.3f} | {item['gpu_per_token']:.6f} | {item['batch']:.3f} | {item['expanded_selected']} |")
    lines += ["","## 预定判定","", "```json",json.dumps(decision,ensure_ascii=False,indent=2),"```","",
              "性能门槛通过也不自动等于正式闭环；还需机制、消融、开销与正式 0/1/2。门槛未通过时停止当前候选，不代表所有动态控制均不可能。","",
              f"完整性：{len(validation)}/{len(validation)} 个结果通过逐请求事件、执行工作量、路径覆盖、KV、轨迹与哈希复算。"]
    (folder/f"{phase}_RESULTS_CN.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"validated":len(validation),"decision":decision,"report":str((folder/f"{phase}_RESULTS_CN.md").relative_to(ROOT))}

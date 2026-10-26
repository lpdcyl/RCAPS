"""Verified V4 paper tables/figures; incomplete triples never become means."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "gpu_seconds_per_output_token", "completion_fraction", "backlog_at_window_end")
BATCHES = ("v4_formal", "v4_external", "v4_recovery", "v4_recovery2")
LABELS = {"v3": "V3", "spatial": "V3+S", "temporal": "V3+T", "v4": "V4",
          "helix": "Helix", "swarm": "Swarm", "separate": "SP",
          "canonical4": "Canonical+T", "all4": "Sparse+all-link T",
          "chunk1": "1 MiB", "chunk2": "2 MiB", "chunk8": "8 MiB",
          "static": "V4 static routing", "single_boundary": "V4 single-boundary"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def collect():
    rows, provenance, states = {}, [], {}
    audit = read(HERE / "history_audit.json")
    for key, item in audit["jobs"].items():
        if item["reuse_decision"] != "accepted_default_execution_equivalence":
            continue
        path = ROOT / item["source"]
        assert digest(path) == item["sha256"], path
        row = read(path)
        sc, load, seed, method = key.split("/")
        k = (sc, int(load), "v3" if method == "rcaps_v3" else method, int(seed[4:]))
        if "gpu_busy_fraction" in row:
            row["gpu_seconds_per_output_token"] = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
        row["_source"] = item["source"]
        row["_evidence"] = "audited_historical"
        rows[k] = row
        provenance.append({"key": list(k), "source": item["source"], "sha256": item["sha256"], "kind": "audited_historical"})
    for directory in BATCHES:
        folder = ROOT / "experiments" / directory
        if not (folder / "index.json").exists():
            if directory.startswith("v4_recovery"):
                continue
            states[directory] = {"queue_status": "not_started"}
            continue
        index = read(folder / "index.json")
        assert digest(folder / "manifest.json") == index["manifest_sha256"]
        if directory.startswith("v4_recovery"):
            recovery = read(folder / "manifest.json")
            original = ROOT / "experiments/v4_formal"
            assert digest(original / "manifest.json") == recovery["core_manifest_sha256"]
            assert digest(original / "index.json") == recovery["original_index_sha256"]
            if "predecessor_index" in recovery:
                assert digest(ROOT / recovery["predecessor_index"]) == recovery["predecessor_index_sha256"]
            for category in ("sources_sha256", "original_failure_files_sha256"):
                for name, expected in recovery[category].items():
                    assert digest(ROOT / name) == expected, name
            original_jobs = read(original / "index.json")["jobs"]
            allowed = {j["key"] for j in recovery["jobs"]}
            assert set(index["jobs"]) <= allowed
            assert all(original_jobs.get(k,{}).get("status") != "completed" for k in allowed)
        states[directory] = {"queue_status": index["queue_status"], "selected_windows": index["selected_windows"],
                             "completed": sum(j["status"] == "completed" for j in index["jobs"].values()),
                             "failed": {k: v for k, v in index["jobs"].items() if v["status"] == "failed"},
                             "running": [k for k, v in index["jobs"].items() if v["status"] == "running"],
                             "unstarted": index["selected_windows"] - len(index["jobs"])}
        for key, item in index["jobs"].items():
            if item["status"] != "completed":
                continue
            path = folder / "runs" / key / "result.json"
            assert digest(path) == item["result_sha256"], path
            row = read(path)
            if directory.startswith("v4_recovery"):
                assert row["recovery_manifest_sha256"] == digest(folder / "manifest.json")
                assert row["manifest_sha256"] == recovery["core_manifest_sha256"]
                assert row["attempt_number"] == (2 if key in recovery["retry_keys"] else 1)
            if len(row["query_samples"]) != row["arrivals"]:
                raise RuntimeError(f"Missing query samples: {path}")
            for field in ("gpu_busy_fraction", "link_occupied_fraction"):
                if any(not math.isfinite(x) or x < -1e-9 or x > 1+1e-7 for x in row.get(field, {}).values()):
                    raise RuntimeError(f"Accounting outside physical bounds: {path}, {field}")
            for label, counts in row.get("phase_link_profile", {}).get("gpu", {}).items():
                if abs(counts["busy_s"]/1800-row["gpu_busy_fraction"][label]) > 1e-9:
                    raise RuntimeError(f"Independent GPU accounting differs: {path}, {label}")
                if abs(sum(counts.get(f"{phase}_busy_s",0) for phase in ("prompt","decode","mixed"))-counts["busy_s"]) > 1e-7:
                    raise RuntimeError(f"GPU phase accounting does not sum: {path}, {label}")
            job = row["job"]
            cell = job.get("cell", job.get("method"))
            cell = "v3" if cell == "rcaps_v3" else cell
            k = (job["scenario"], job["load"], cell, job["seed"])
            row["_source"] = path.relative_to(ROOT).as_posix()
            if directory.startswith("v4_recovery"):
                assert k not in rows or rows[k]["_evidence"] == "audited_historical", "Duplicate successful formal cell"
            row["_evidence"] = ("authorized_second_attempt" if directory.startswith("v4_recovery") and row["attempt_number"] == 2
                                else "authorized_continuation" if directory.startswith("v4_recovery") else "fresh_formal")
            rows[k] = row
            provenance.append({"key": list(k), "source": row["_source"], "sha256": item["result_sha256"], "kind": row["_evidence"]})
    return rows, provenance, states


def campaign_complete(states):
    main = states.get("v4_formal",{})
    external = states.get("v4_external",{})
    recoveries = [states[k] for k in BATCHES if k.startswith("v4_recovery") and k in states]
    current = recoveries[-1] if recoveries else main
    return (main.get("completed",0)+sum(s.get("completed",0) for s in recoveries) == 93
            and external.get("completed",0) == 27
            and current.get("queue_status") == "completed"
            and external.get("queue_status") == "completed")


def campaign_halted(states):
    recoveries = [states[k] for k in BATCHES if k.startswith("v4_recovery") and k in states]
    current = recoveries[-1] if recoveries else states.get("v4_formal",{})
    return any(s.get("queue_status") in {"halted","halting_after_failure"}
               for s in (current,states.get("v4_external",{})))


def group(rows, sc, load, cell):
    selected = [rows.get((sc, load, cell, seed)) for seed in (0, 1, 2)]
    if any(r is None for r in selected):
        return None
    return {metric: {"values": [r.get(metric) for r in selected],
                     "mean": mean(r[metric] for r in selected),
                     "sd": stdev(r[metric] for r in selected)}
            for metric in METRICS if all(r.get(metric) is not None for r in selected)}


def paired(rows, sc, load, left, right):
    pairs = []
    for seed in (0, 1, 2):
        a, b = rows.get((sc, load, left, seed)), rows.get((sc, load, right, seed))
        if a is None or b is None:
            continue
        assert a["trace_sha256"] == b["trace_sha256"], (sc, load, left, right, seed)
        assert set(a["query_samples"]) == set(b["query_samples"])
        for uid in a["query_samples"]:
            x, y = a["query_samples"][uid], b["query_samples"][uid]
            assert x["input_tokens"] == y["input_tokens"] and x["output_tokens"] == y["output_tokens"]
            assert abs(x["arrival_s"] - y["arrival_s"]) < 1e-7
        common = [uid for uid, x in a["query_samples"].items() if x["completed"]
                  and b["query_samples"][uid]["completed"] and x["tpot_s"] is not None
                  and b["query_samples"][uid]["tpot_s"] is not None]
        common_values = [float(np.percentile([r["query_samples"][u]["tpot_s"] for u in common], 95))
                         for r in (a, b)] if common else None
        pairs.append({"seed": seed, "relative": {m: b[m]/a[m]-1 for m in METRICS
                                                   if a.get(m) and b.get(m) is not None},
                      "common_completed": {"count": len(common), "tpot_p95_s": common_values,
                                            "relative": common_values[1]/common_values[0]-1 if common_values and common_values[0] else None}})
    return {"scenario": sc, "load": load, "left": left, "right": right, "seeds": pairs,
            "complete": len(pairs) == 3,
            "mean_paired_relative": ({m: mean(p["relative"][m] for p in pairs)
                                       for m in METRICS if all(m in p["relative"] for p in pairs)}
                                      if len(pairs) == 3 else None)}


def mechanism(row):
    profile = row.get("phase_link_profile", {})
    gpu = profile.get("gpu", {})
    links = profile.get("links", {})
    weighted = tokens = single = executions = 0
    for item in gpu.values():
        for size, count in item["decode_batch_histogram"].items():
            n = int(size)
            weighted += n*n*count
            tokens += n*count
            executions += count
            if n == 1: single += count
    return {"actual_paths": len(row["route_counts"]),
            "token_weighted_decode_batch": weighted/tokens if tokens else None,
            "singleton_execution_fraction": single/executions if executions else None,
            "decode_layer_token_executions": tokens,
            "prompt_only_busy_s": sum(x.get("prompt_busy_s", 0) for x in gpu.values()),
            "decode_only_busy_s": sum(x.get("decode_busy_s", 0) for x in gpu.values()),
            "mixed_busy_s": sum(x.get("mixed_busy_s", 0) for x in gpu.values()),
            "decode_network_wait_s": sum(x.get("decode_wait_s", 0) for x in links.values()),
            "decode_wait_overlapping_prompt_same_link_s": sum(x.get("decode_wait_prompt_same_link_s", 0) for x in links.values()),
            "paused_chunks": profile.get("chunking", {}).get("paused_chunks", 0),
            "network_note": "Overlap is not all causal delay; NIC overlap counters cannot be summed."}


def plots(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "pdf.fonttype": 42, "ps.fonttype": 42})
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    colors = {"v4": "#0072B2", "v3": "#009E73", "helix": "#D55E00"}
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.5), constrained_layout=True)
    specs = [("output_throughput_tokens_per_s", "Output throughput (tokens/s)"),
             ("tpot_p95_s", "P95 request-mean TPOT (s)"),
             ("ttft_p95_s", "P95 TTFT (s)"), ("completion_fraction", "Completion fraction")]
    for r, (sc, loads) in enumerate((("single", [100,200,350,500,700,900]), ("multi", [50,100,160,240,320,400]))):
        for c, (metric, label) in enumerate(specs):
            ax = axes[r,c]
            for cell in ("helix", "v3", "v4"):
                gs = [group(rows,sc,load,cell) for load in loads]
                ys = [g[metric]["mean"] if g else np.nan for g in gs]
                errors = [g[metric]["sd"] if g else np.nan for g in gs]
                ax.errorbar(loads,ys,yerr=errors,marker="o",markersize=4,capsize=2,label=LABELS[cell],color=colors[cell])
            ax.set_xlabel("Offered input + target output (tokens/s)")
            ax.set_ylabel(label)
            ax.set_title("C1 single cluster" if sc == "single" else "C1 three clusters")
            ax.grid(alpha=.2)
            if r == 0 and c == 0: ax.legend()
    fig.suptitle("Three seeds (0/1/2): mean and sample SD; incomplete triples omitted")
    for ext in ("png", "pdf"): fig.savefig(folder / f"v4_load_curves.{ext}",dpi=180)
    plt.close(fig)
    if all(group(rows,"multi",320,c) for c in ("v3","spatial","temporal","v4")):
        fig, axes = plt.subplots(1,2,figsize=(8,3.2),constrained_layout=True)
        cells = ("v3","spatial","temporal","v4")
        for ax, metric, label in zip(axes,("tpot_p95_s","gpu_seconds_per_output_token"),("P95 TPOT (s)","GPU seconds / output token")):
            gs = [group(rows,"multi",320,c)[metric] for c in cells]
            ax.bar(range(4),[g["mean"] for g in gs],yerr=[g["sd"] for g in gs],capsize=3,color=["#888888","#009E73","#E69F00","#0072B2"])
            for i,g in enumerate(gs): ax.scatter([i-.08,i,i+.08],g["values"],color="black",s=13,zorder=3)
            ax.set_xticks(range(4),[LABELS[c] for c in cells]); ax.set_ylabel(label)
        fig.suptitle("C1 three clusters, load 320; individual seeds and mean ± SD")
        for ext in ("png","pdf"): fig.savefig(folder / f"v4_factorial_320.{ext}",dpi=180)
        plt.close(fig)
        raw = [[rows["multi",320,c,s] for s in (0,1,2)] for c in cells]
        if all(r.get("phase_link_profile",{}).get("schema") == "v4_chunk_aware_v1" for triple in raw for r in triple):
            stats = [[mechanism(r) for r in triple] for triple in raw]
            plot_values = [
                ([[m["actual_paths"] for m in triple] for triple in stats], "Actual paths"),
                ([[m["token_weighted_decode_batch"] for m in triple] for triple in stats], "Token-weighted Decode batch"),
                ([[m["singleton_execution_fraction"] for m in triple] for triple in stats], "Singleton execution fraction"),
                ([[m["decode_network_wait_s"]/(r["output_throughput_tokens_per_s"]*1800)
                   for m,r in zip(ms,rs)] for ms,rs in zip(stats,raw)], "Decode network wait / output token (s)")]
            fig,axes = plt.subplots(1,4,figsize=(14,3.5),constrained_layout=True)
            for ax,(values,label) in zip(axes,plot_values):
                ax.bar(range(4),[mean(v) for v in values],yerr=[stdev(v) for v in values],capsize=3,
                       color=["#888888","#009E73","#E69F00","#0072B2"])
                for i,v in enumerate(values): ax.scatter([i-.08,i,i+.08],v,color="black",s=12,zorder=3)
                ax.set_xticks(range(4),[LABELS[c] for c in cells]); ax.set_ylabel(label)
            fig.suptitle("Mechanism observations at load 320; no attribution of all waiting to overlap")
            for ext in ("png","pdf"): fig.savefig(folder / f"v4_mechanism_320.{ext}",dpi=180)
            plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--require-complete", action="store_true")
    p.add_argument("--plots", action="store_true")
    args = p.parse_args()
    rows, provenance, states = collect()
    complete = campaign_complete(states)
    if args.require_complete and not complete:
        raise RuntimeError(f"Formal batches incomplete: {states}")
    effects = []
    for sc, loads in (("single", (100,200,350,500,700,900)), ("multi", (50,100,160,240,320,400))):
        for load in loads:
            effects.append(paired(rows,sc,load,"v3","v4"))
    for load in (320,160):
        for a,b in (("v3","spatial"),("v3","temporal"),("spatial","v4"),("temporal","v4"),("v3","v4")):
            effects.append(paired(rows,"multi",load,a,b))
    for sc,load in (("single",700),("multi",320)):
        for cell in ("static","single_boundary"):
            effects.append(paired(rows,sc,load,cell,"v4"))
    for cell in ("canonical4","all4","chunk1","chunk2","chunk8"):
        effects.append(paired(rows,"multi",320,cell,"v4"))
    for sc,load in (("single",350),("multi",160)):
        for cell in ("v3","helix","swarm","separate"):
            effects.append(paired(rows,sc,load,cell,"v4"))
    for sc,load in (("C2",160),("C3",400)):
        effects.append(paired(rows,sc,load,"v3","v4"))
    interactions = []
    for load in (320,160):
        for seed in (0,1,2):
            rs = [rows.get(("multi",load,c,seed)) for c in ("v3","spatial","temporal","v4")]
            if all(rs):
                a,b,c,d = [r["tpot_p95_s"] for r in rs]
                interactions.append({"load":load,"seed":seed,"tpot_log_interaction":math.log(d/b)-math.log(c/a)})
    data = {"generated_at":datetime.now(timezone.utc).isoformat(), "analysis_script_sha256":digest(Path(__file__)),
            "all_two_batches_complete":complete,"batch_states":states,"provenance":provenance,
            "paired_effects":effects,"interactions":interactions,
            "mechanism":[{"scenario":k[0],"load":k[1],"cell":k[2],"seed":k[3],**mechanism(r)}
                         for k,r in sorted(rows.items()) if r.get("phase_link_profile",{}).get("schema")=="v4_chunk_aware_v1"]}
    write(HERE / "analysis.json",data)
    halted = campaign_halted(states)
    status = "本次 93+27 个窗口均已有成功结果；尝试失败另列。" if complete else ("因异常中止；失败保留。" if halted else "执行中。")
    lines = ["# V4 正式实验结果", "", "状态：" + status + "只对齐全的 0/1/2 三种子组给均值。", "",
             "主协议：1800 秒、零预热、不排空。TPOT 为请求平均 token 间隔的 P95；GPU 秒/token 为忙碌工作量，不等于能耗。",
             "历史负载曲线 71 个成功窗口已审核复用，三集群负载 400 的 Helix seed 0 失败保留，不计零值、不生成该点三种子均值。", "",
             "## 执行状态", "", "| 批次 | 完成 | 失败 | 未启动 | 总窗口 | 状态 |", "|---|---:|---:|---:|---:|---|"]
    for name,state in states.items(): lines.append(f"| {name} | {state.get('completed',0)} | {len(state.get('failed',{}))} | {state.get('unstarted',0)} | {state.get('selected_windows','—')} | {state['queue_status']} |")
    for name,state in states.items():
        for key,item in state.get("failed",{}).items():
            lines += ["",f"保留失败尝试：`{name}/{key}`，退出码 `{item.get('exit_code')}`；失败不计零值。仅有明确授权的独立成功尝试才能补齐该种子。"]
    if "v4_recovery" in states:
        lines += ["", "用户明确授权的恢复批次单独登记；此前中止队列保持 halted，不覆盖失败。恢复结果来源和尝试身份单列。最终 120 格齐全不等于 120 次首次运行全部成功。", "",
                  "恢复登记见 [恢复批次](../v4_recovery/README.md)，此前系统诊断见 [中止审计](EXECUTION_AUDIT_CN.md)。"]
    if "v4_recovery2" in states:
        lines += ["", "第二次恢复授权见 [恢复批次二](../v4_recovery2/README.md)：C2/V4/seed1 的第二尝试及 7 格续跑。全部补齐须报告 122 次尝试、120 个成功窗口、2 次保留失败。"]
    if complete:
        lines += ["", "去重后已补齐 120/120 格，累计 122 次尝试、2 次保留失败。上表的未启动数属于各历史批次快照，不能相加作为当前剩余量。", "",
                  "完整结论、配对效应与剩余论文缺口见 [正式完成报告](FINAL_RESULTS_CN.md)。"]
    if halted:
        lines += ["", "异常诊断、恢复前提和证据缺口见 [中止审计与阶段结论](EXECUTION_AUDIT_CN.md)。"]
    tables = [("共同负载五方法", [(sc,load,c) for sc,load in (("single",350),("multi",160)) for c in ("v4","v3","helix","swarm","separate")]),
              ("空间 × 时间正式消融",[("multi",load,c) for load in (320,160) for c in ("v3","spatial","temporal","v4")]),
              ("机制、参数与组件",[("multi",320,c) for c in ("canonical4","all4","chunk1","chunk2","v4","chunk8")]+[(sc,load,c) for sc,load in (("single",700),("multi",320)) for c in ("v4","static","single_boundary")]),
              ("资源池泛化",[(sc,load,c) for sc,load in (("C2",160),("C3",400)) for c in ("v3","v4")])]
    for title, configs in tables:
        lines += ["",f"## {title}","","均值 ± 样本标准差；缺失三种子时显示待完成。","", "| 拓扑 | 负载 | 方法 | TPOT s | TTFT s | 输出 token/s | GPU s/token | 完成率 |","|---|---:|---|---:|---:|---:|---:|---:|"]
        for sc,load,c in configs:
            g = group(rows,sc,load,c)
            values = []
            for m in METRICS[:5]:
                v = g.get(m) if g else None
                values.append(f"{v['mean']:.5g} ± {v['sd']:.3g}" if v else "待完成")
            lines.append(f"| {sc} | {load} | {LABELS.get(c,c)} | " + " | ".join(values) + " |")
    lines += ["","## 解释边界","", "- 两种子或单种子结果不替代正式三种子均值；交互项用于描述，不能直接证明显著协同。",
              "- 历史偶发 TypeError 根因仍未确定。新运行成功与历史异常解释是不同问题；失败审计不删除。",
              "- 网络占用重叠不是全部等待的因果归属，发送/接收 NIC 重叠不得相加。GPU mixed 批次工作单列。",
              "- 更广的带宽、画像、工作负载、窗口和真实系统验证不因本批完成而自动成立。", "",
              "原始来源及文件哈希见 `analysis.json`，完整逐种子指标见 `individual.csv`。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    with (HERE / "individual.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=["scenario","load","cell","seed",*METRICS,"source","evidence"])
        w.writeheader()
        for k,r in sorted(rows.items()): w.writerow(dict(scenario=k[0],load=k[1],cell=k[2],seed=k[3],**{m:r.get(m) for m in METRICS},source=r["_source"],evidence=r["_evidence"]))
    if args.plots: plots(rows)
    print(json.dumps({"complete":complete,"states":states},ensure_ascii=False))


if __name__ == "__main__": main()

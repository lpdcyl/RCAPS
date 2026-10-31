"""Audit and report E2a held-out five-seed evaluation."""
from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from .run import HERE, LOADS, ROOT, check, label, read, sha, write

T4 = 2.7764451051977987
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")
BASELINES = ("HH", "HHplus", "V4")


def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def paired_ci(values):
    if len(values) != 5:
        raise RuntimeError("Five seeds required for paired CI")
    center = mean(values)
    half = T4 * stdev(values) / math.sqrt(5)
    return center, center - half, center + half


def fmt_ci(values):
    center, low, high = paired_ci(values)
    return f"{center:.2f}% [{low:.2f}%, {high:.2f}%]"


def main():
    manifest_path = HERE / "evaluation/manifest.json"
    index_path = HERE / "evaluation/index.json"
    manifest = read(manifest_path)
    check(manifest)
    index = read(index_path)
    selection_path = HERE / "selection.json"
    selection = read(selection_path)
    if (index["status"] != "terminal" or
            index["manifest_sha256"] != sha(manifest_path) or
            manifest["selection_sha256"] != sha(selection_path)):
        raise RuntimeError("Evaluation provenance mismatch")
    jobs = {job["key"]: job for job in manifest["jobs"]}
    if len(jobs) != 20 or set(index["jobs"]) != set(jobs):
        raise RuntimeError("Evaluation job set mismatch")
    historical = {}
    for row in load_csv(ROOT / "experiments/v5_core_supplement/individual.csv"):
        if row["cell"] in BASELINES:
            historical[(row["scenario"], int(row["load"]), row["cell"], int(row["seed"]))] = row
    results = {}
    individual = []
    errors = Counter()
    for key, job in jobs.items():
        entry = index["jobs"][key]
        case, load, seed = job["scenario"], job["load"], job["seed"]
        if job["params"] != selection[f"{case}/{load}"]["params"]:
            raise RuntimeError("Evaluation does not use held-out selection: " + key)
        if entry["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal evaluation job: " + key)
        source = ROOT / entry["source"]
        if not source.exists() or sha(source) != entry["artifact_sha256"]:
            raise RuntimeError("Evaluation artifact hash mismatch: " + key)
        row = read(source)
        if row["job"] != job:
            raise RuntimeError("Evaluation identity mismatch: " + key)
        if entry["status"] == "failed":
            error = row.get("error", row.get("classification", "unknown"))
            errors[error] += 1
            individual.append(dict(scenario=case, load=load, cell="Helix-tuned",
                                   seed=seed, status="failed", source=entry["source"],
                                   error=error, artifact_sha256=entry["artifact_sha256"]))
            continue
        if (row["status"] != "completed" or row["manifest_sha256"] != sha(manifest_path)
                or row["evaluation_protocol"] != "fixed_window_no_tail_drain"
                or row["duration_s"] != 1800 or row["warmup_s"] != 0
                or len(row["query_samples"]) != row["arrivals"]):
            raise RuntimeError("Evaluation protocol or samples mismatch: " + key)
        expected_gpu = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
        if not math.isclose(row["gpu_seconds_per_output_token"], expected_gpu, rel_tol=1e-12):
            raise RuntimeError("GPU accounting mismatch: " + key)
        for cell in BASELINES:
            old = historical[(case, load, cell, seed)]
            if row["trace_sha256"] != old["trace_sha256"]:
                raise RuntimeError("Unpaired request trace: " + key + " " + cell)
            old_source = ROOT / old["source"]
            if not old_source.exists():
                raise RuntimeError("Historical source missing: " + old["source"])
            old_result = read(old_source)
            for metric in METRICS:
                if not math.isclose(float(old[metric]), old_result[metric], rel_tol=1e-12):
                    raise RuntimeError("Historical CSV metric mismatch: " + cell + " " + key)
            if cell != "V4" and (
                row["solution_sha256"] != old["solution_sha256"] or
                row["sim_cluster_sha256"] != old["sim_cluster_sha256"]):
                raise RuntimeError("Helix deployment mismatch: " + key + " " + cell)
        results[(case, load, seed)] = row
        individual.append(dict(scenario=case, load=load, cell="Helix-tuned", seed=seed,
            status="completed", source=entry["source"], error="",
            artifact_sha256=entry["artifact_sha256"],
            trace_sha256=row["trace_sha256"], solution_sha256=row["solution_sha256"],
            sim_cluster_sha256=row["sim_cluster_sha256"],
            **{metric: row[metric] for metric in METRICS}))
    columns = ("scenario", "load", "cell", "seed", "status", "source", "error",
               "artifact_sha256", "trace_sha256", "solution_sha256",
               "sim_cluster_sha256", *METRICS)
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(individual)
    lines = [
        "# E2a Helix 调优结果", "",
        "70B 画像驱动 CPU 仿真；同轨迹、同 Helix 部署，1800 s 固定窗口、零预热、不排空。",
        "仅用 seed5/6 选择配置，seed0–4 完全留作正式评估。原调优批次 95/96 成功；",
        "1 个 Windows native access violation 原件保留，独立重放 1/1 成功。不能把重放写成原批成功。", "",
        "| 拓扑/负载 | 选中开关与 KV 参数 | 正式成功 | Helix-tuned P95 TPOT s | P95 TTFT s | 吞吐 token/s | 完成率 | GPU s/token | 相对 Helix-tuned 的 RCAPS TPOT 降幅 (配对 95% CI) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    comparison = {}
    complete = 0
    for case, load in LOADS:
        group = [results.get((case, load, seed)) for seed in range(5)]
        choice = selection[f"{case}/{load}"]
        if any(row is None for row in group):
            lines.append(f"| {case}/{load} | {choice['candidate']} | {sum(row is not None for row in group)}/5 | — | — | — | — | — | — |")
            continue
        complete += 1
        means = {metric: mean(row[metric] for row in group) for metric in METRICS}
        base = {cell: [historical[(case, load, cell, seed)] for seed in range(5)]
                for cell in BASELINES}
        reductions = {}
        for cell in BASELINES:
            vals = []
            for seed in range(5):
                benchmark = float(base[cell][seed]["tpot_p95_s"])
                tuned = group[seed]["tpot_p95_s"]
                vals.append(100 * (benchmark - tuned) / benchmark)
            reductions[f"tuned_vs_{cell}"] = dict(zip(("mean", "low", "high"), paired_ci(vals)))
        rcaps_vals = [100 * (group[seed]["tpot_p95_s"] -
                              float(base["V4"][seed]["tpot_p95_s"])) /
                      group[seed]["tpot_p95_s"] for seed in range(5)]
        reductions["RCAPS_vs_tuned"] = dict(zip(("mean", "low", "high"), paired_ci(rcaps_vals)))
        comparison[f"{case}/{load}"] = dict(choice=choice["candidate"],
            params=choice["params"], success=5, means=means, paired_reductions_pct=reductions)
        lines.append(f"| {case}/{load} | {choice['candidate']} | 5/5 | "
            f"{means['tpot_p95_s']:.3f} | {means['ttft_p95_s']:.3f} | "
            f"{means['output_throughput_tokens_per_s']:.2f} | "
            f"{100*means['completion_fraction']:.2f}% | "
            f"{means['gpu_seconds_per_output_token']:.4f} | {fmt_ci(rcaps_vals)} |")
    lines += ["", "## 相对历史 Helix 基线的逐种子配对变化", "",
              "正值表示 Helix-tuned 的 P95 TPOT 更低。仅完整 5/5 组给出区间。", "",
              "| 拓扑/负载 | 相对 Helix | 相对 Helix+ |",
              "|---|---:|---:|"]
    for case, load in LOADS:
        item = comparison.get(f"{case}/{load}")
        if not item:
            continue
        values = []
        for cell in ("HH", "HHplus"):
            stats = item["paired_reductions_pct"][f"tuned_vs_{cell}"]
            values.append(f"{stats['mean']:.2f}% [{stats['low']:.2f}%, {stats['high']:.2f}%]")
        lines.append(f"| {case}/{load} | {values[0]} | {values[1]} |")
    lines += ["", "## 调优网格和失败归属", "",
        "完整 12 候选 × 4 负载的 seed5/6 均值、完成率门槛与选择来源见 selection.json；",
        "该网格不使用正式 seed0–4。调优唯一原失败键及独立重放状态见",
        "tuning/index.json 与 failure_replay/index.json。MILP 加宽预算诊断单列，",
        "本表只调优在线执行和 KV 参数，不能称已重求得更优 Helix 放置。", "",
        "## 论文可用表述", "",
        "在同一 70B 画像驱动模拟器与 Helix 放置下，我们以独立种子 5、6 调优执行开关和 KV 预估参数，",
        "并以未参与选择的种子 0–4 进行五次配对评估。",
        "调优候选的 96 次原始窗口中 95 次成功；唯一 Windows 原生崩溃在保留原记录后独立重放成功。",
        "正式评估的各负载 P95 TPOT、资源成本及相对完整 RCAPS 的配对区间见上表。",
        "这些结果仅支持本模拟器与已部署 Helix 放置下的比较，不代表真实 GPU 集群验证。", ""]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    write(HERE / "comparison.json", comparison)
    audit = dict(passed=complete == 4 and not errors, registered_windows=20,
        completed=len(results), failed=sum(errors.values()), failure_reasons=dict(errors),
        complete_five_seed_groups=complete,
        tuning_original_completed=95, tuning_original_failed=1,
        tuning_replay_completed=selection["_audit"]["recovered_by_independent_replay"],
        evaluation_manifest_sha256=sha(manifest_path), evaluation_index_sha256=sha(index_path),
        selection_sha256=sha(selection_path), individual_sha256=sha(HERE / "individual.csv"),
        results_sha256=sha(HERE / "RESULTS_CN.md"),
        comparison_sha256=sha(HERE / "comparison.json"),
        report_script_sha256=sha(Path(__file__)))
    write(HERE / "FINAL_AUDIT.json", audit)
    print(audit)
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

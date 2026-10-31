"""Publish only corrected single and original valid multi E2a held-out results."""
from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from statistics import mean, stdev

from .run import HERE, LOADS, ROOT, read, sha, write

T4 = 2.7764451051977987
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")
BASELINES = ("HH", "HHplus", "V4")


def csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def ci(values):
    if len(values) != 5:
        raise RuntimeError("Paired CI requires five successful seeds")
    center = mean(values)
    half = T4 * stdev(values) / math.sqrt(5)
    return dict(mean=center, low=center-half, high=center+half)


def fmt(stats):
    return f"{stats['mean']:.2f}% [{stats['low']:.2f}%, {stats['high']:.2f}%]"


def source_block(folder, cases):
    manifest_path = folder / "evaluation/manifest.json"
    index_path = folder / "evaluation/index.json"
    selection_path = folder / "selection.json"
    manifest, index, selection = (read(path) for path in
                                  (manifest_path, index_path, selection_path))
    if (index["status"] != "terminal" or
            index["manifest_sha256"] != sha(manifest_path) or
            manifest["selection_sha256"] != sha(selection_path)):
        raise RuntimeError("Unverified evaluation block: " + str(folder))
    jobs = {job["key"]: job for job in manifest["jobs"]}
    if set(index["jobs"]) != set(jobs):
        raise RuntimeError("Evaluation job keys mismatch: " + str(folder))
    selected = {key: job for key, job in jobs.items() if job["scenario"] in cases}
    expected = 10 * len(cases)
    if len(selected) != expected:
        raise RuntimeError(f"Expected {expected} usable jobs from {folder}, got {len(selected)}")
    return manifest_path, index_path, selection_path, manifest, index, selection, selected


def main():
    from baselines.helix import layout
    from benchmarks.layout import scenario
    corrected = HERE / "single_correction"
    blocks = {
        "single": source_block(corrected, {"single"}),
        "multi": source_block(HERE, {"multi"}),
    }
    historical = {}
    for row in csv_rows(ROOT / "experiments/v5_core_supplement/individual.csv"):
        if row["cell"] in BASELINES:
            historical[(row["scenario"], int(row["load"]), row["cell"], int(row["seed"]))] = row
    expected_historical = 4 * 5 * len(BASELINES)
    if len(historical) < expected_historical:
        raise RuntimeError("Historical five-seed baselines incomplete")
    results, output_rows, failures = {}, [], Counter()
    for case in ("single", "multi"):
        (manifest_path, index_path, selection_path, manifest,
         index, selection, jobs) = blocks[case]
        solution, cluster = layout(case, ROOT)
        expected_deployment = (sha(solution), sha(cluster))
        physical = scenario(case)[0]
        manifest_sources = manifest["sources_sha256"]
        for path in (solution, cluster, physical):
            name = path.relative_to(ROOT).as_posix()
            if manifest_sources.get(name) != sha(path):
                raise RuntimeError("Deployment input absent or changed in manifest: " + name)
        for key, job in jobs.items():
            load, seed = job["load"], job["seed"]
            if job["params"] != selection[f"{case}/{load}"]["params"]:
                raise RuntimeError("Held-out selection mismatch: " + key)
            entry = index["jobs"][key]
            if entry["status"] not in ("completed", "failed"):
                raise RuntimeError("Nonterminal job: " + key)
            source = ROOT / entry["source"]
            if not source.exists() or sha(source) != entry["artifact_sha256"]:
                raise RuntimeError("Source artifact mismatch: " + key)
            row = read(source)
            if row["job"] != job:
                raise RuntimeError("Job identity mismatch: " + key)
            if entry["status"] == "failed":
                error = row.get("error", row.get("classification", "unknown"))
                failures[error] += 1
                output_rows.append(dict(scenario=case, load=load, cell="Helix-tuned",
                                        seed=seed, status="failed", source=entry["source"],
                                        error=error, artifact_sha256=entry["artifact_sha256"]))
                continue
            if (row["status"] != "completed" or
                    row["manifest_sha256"] != sha(manifest_path) or
                    row["evaluation_protocol"] != "fixed_window_no_tail_drain" or
                    row["duration_s"] != 1800 or row["warmup_s"] != 0 or
                    len(row["query_samples"]) != row["arrivals"] or
                    (row["solution_sha256"], row["sim_cluster_sha256"]) != expected_deployment or
                    row["physical_cluster_sha256"] != sha(physical)):
                raise RuntimeError("Protocol or deployment mismatch: " + key)
            work = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
            if not math.isclose(row["gpu_seconds_per_output_token"], work, rel_tol=1e-12):
                raise RuntimeError("GPU accounting mismatch: " + key)
            for cell in BASELINES:
                old = historical[(case, load, cell, seed)]
                if row["trace_sha256"] != old["trace_sha256"]:
                    raise RuntimeError("Unpaired request trace: " + key + " " + cell)
                if cell in ("HH", "HHplus") and (
                    row["solution_sha256"] != old["solution_sha256"] or
                    row["sim_cluster_sha256"] != old["sim_cluster_sha256"]):
                    raise RuntimeError("Helix deployment differs from baseline: " + key)
                old_source = ROOT / old["source"]
                if not old_source.exists():
                    raise RuntimeError("Missing historical source: " + old["source"])
                old_result = read(old_source)
                for metric in METRICS:
                    if not math.isclose(float(old[metric]), old_result[metric], rel_tol=1e-12):
                        raise RuntimeError("Historical metric differs from source: " + key + " " + cell)
            results[(case, load, seed)] = row
            output_rows.append(dict(scenario=case, load=load, cell="Helix-tuned",
                seed=seed, status="completed", source=entry["source"], error="",
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
        writer.writerows(output_rows)
    lines = [
        "# E2a：经部署纠错的 Helix 调优结果", "",
        "70B 画像驱动 CPU 仿真；1800 s 固定窗口、零预热、不排空。",
        "单集群使用 single_correction 的官方 Helix 部署重新调优和评估；",
        "三集群沿用部署哈希一致的原 E2a 调优和评估。",
        "原错误部署的单集群窗口仅作诊断，不进入下表或论文配对计算。", "",
        "| 拓扑/负载 | seed5/6 选中配置 | 正式成功 | tuned P95 TPOT s | P95 TTFT s | 吞吐 token/s | 完成率 | GPU s/token | RCAPS 相对 tuned 的 P95 TPOT 降幅，配对 95% CI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    comparisons, full_groups = {}, 0
    for case, load in LOADS:
        selection = blocks[case][5]
        choice = selection[f"{case}/{load}"]
        group = [results.get((case, load, seed)) for seed in range(5)]
        if any(value is None for value in group):
            lines.append(f"| {case}/{load} | {choice['candidate']} | {sum(x is not None for x in group)}/5 | — | — | — | — | — | — |")
            continue
        full_groups += 1
        means = {metric: mean(row[metric] for row in group) for metric in METRICS}
        changes = {}
        for cell in BASELINES:
            baseline = [float(historical[(case, load, cell, seed)]["tpot_p95_s"])
                        for seed in range(5)]
            tuned = [group[seed]["tpot_p95_s"] for seed in range(5)]
            changes[f"tuned_vs_{cell}"] = ci(
                [100 * (baseline[s] - tuned[s]) / baseline[s] for s in range(5)])
            if cell == "V4":
                changes["RCAPS_vs_tuned"] = ci(
                    [100 * (tuned[s] - baseline[s]) / tuned[s] for s in range(5)])
        comparisons[f"{case}/{load}"] = dict(candidate=choice["candidate"],
            params=choice["params"], success=5, means=means, paired_pct=changes)
        lines.append(f"| {case}/{load} | {choice['candidate']} | 5/5 | "
            f"{means['tpot_p95_s']:.3f} | {means['ttft_p95_s']:.3f} | "
            f"{means['output_throughput_tokens_per_s']:.2f} | "
            f"{100*means['completion_fraction']:.2f}% | "
            f"{means['gpu_seconds_per_output_token']:.4f} | "
            f"{fmt(changes['RCAPS_vs_tuned'])} |")
    lines += ["", "## 相对原 Helix 和 Helix+ 的配对变化", "",
        "正值表示 Helix-tuned 的 P95 TPOT 降低。只对五种子完整组计算 df=4 双侧 t 区间。", "",
        "| 拓扑/负载 | 相对 Helix | 相对 Helix+ |",
        "|---|---:|---:|"]
    for case, load in LOADS:
        item = comparisons.get(f"{case}/{load}")
        if item:
            lines.append(f"| {case}/{load} | {fmt(item['paired_pct']['tuned_vs_HH'])} | "
                         f"{fmt(item['paired_pct']['tuned_vs_HHplus'])} |")
    lines += ["", "## 完整调优网格与异常记录", "",
        "四个负载各 12 个候选的 seed5/6 成功数、完成率门槛、均值及选中项，",
        "分别见 selection.json（multi）与 single_correction/selection.json（single）。",
        "原 E2a tuning 95/96 成功，唯一 Windows native access violation 在独立目录重放成功；",
        "纠错单集群批次单列。原单集群部署错误详见 DEPLOYMENT_MISMATCH_AUDIT_CN.md。",
        "MILP 加宽求解预算诊断尚未纳入本表；本表仅考察在线执行开关与 KV 参数。", "",
        "## 论文可用表述", "",
        "我们仅以独立种子 5、6 调优 Helix 的执行开关与在线 KV 预估参数，",
        "并在未参与选择的种子 0–4 上进行同轨迹五种子评估。",
        "单集群结果使用与历史 Helix 基线哈希一致的部署纠错重跑，",
        "三集群结果使用原部署哈希一致的批次。",
        "各负载的 P95 TPOT、完成率和 GPU 秒/token 以及完整 RCAPS 对调优 Helix 的配对变化见上表。",
        "该证据仅来自画像驱动模拟器，并非真实 GPU 集群测量。", ""]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")
    write(HERE / "comparison.json", comparisons)
    audit = dict(passed=full_groups == 4 and not failures,
        registered_evaluation_windows=20, completed=len(results), failed=sum(failures.values()),
        failure_reasons=dict(failures), complete_five_seed_groups=full_groups,
        excluded_wrong_layout_single_tuning_windows=48,
        excluded_wrong_layout_single_evaluation_windows=10,
        valid_original_multi_evaluation_windows=10,
        corrected_single_evaluation_windows=10,
        original_tuning_failed=1, original_tuning_replay_completed=1,
        sources={case: dict(manifest_sha256=sha(blocks[case][0]),
                            index_sha256=sha(blocks[case][1]),
                            selection_sha256=sha(blocks[case][2]))
                 for case in ("single", "multi")},
        individual_sha256=sha(HERE / "individual.csv"),
        comparison_sha256=sha(HERE / "comparison.json"),
        results_sha256=sha(HERE / "RESULTS_CN.md"),
        report_script_sha256=sha(Path(__file__)))
    write(HERE / "FINAL_AUDIT.json", audit)
    print(audit)
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

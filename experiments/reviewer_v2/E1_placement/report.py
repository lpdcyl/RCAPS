"""Auditable E1 results with strict five-seed paired summaries."""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
T4 = 2.7764451051977987
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def ci(values):
    if len(values) != 5:
        raise RuntimeError("Cannot give five-seed CI with incomplete group")
    return mean(values), T4 * stdev(values) / math.sqrt(5)

def main():
    from experiments.reviewer_v2.E1_placement.run import check, paths
    manifest_path = HERE / "formal/manifest.json"
    manifest = read(manifest_path)
    check(manifest)
    index_path = HERE / "formal/index.json"
    index = read(index_path)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Formal E1 campaign not terminal")
    if set(index["jobs"]) != {job["key"] for job in manifest["jobs"]}:
        raise RuntimeError("Wrong E1 job keys")
    historical = {}
    for r in load_csv(ROOT / "experiments/v5_core_supplement/individual.csv"):
        if r["cell"] in ("V4", "HR"):
            historical[(r["scenario"], int(r["load"]), r["cell"], int(r["seed"]))] = r
    rows = []
    results = {}
    failures = Counter()
    for job in manifest["jobs"]:
        key = job["key"]
        entry = index["jobs"][key]
        scenario, load, variant, seed = job["scenario"], job["load"], job["variant"], job["seed"]
        base = historical[(scenario, load, "V4", seed)]
        if entry["status"] != "completed":
            source = ROOT / entry["source"]
            if sha(source) != entry["artifact_sha256"]:
                raise RuntimeError("Failure hash mismatch: " + key)
            reason = read(source).get("error", read(source).get("classification", "unknown"))
            failures[reason] += 1
            rows.append(dict(scenario=scenario, load=load, cell=variant, seed=seed,
                             status="failed", source=entry["source"], artifact_sha256=entry["artifact_sha256"],
                             error=reason))
            continue
        source = ROOT / entry["source"]
        if sha(source) != entry["artifact_sha256"]:
            raise RuntimeError("Result hash mismatch: " + key)
        r = read(source)
        solution, cluster, _, placement = paths(job)
        if (r["job"] != job or r["trace_sha256"] != base["trace_sha256"] or
            r["solution_sha256"] != sha(solution) or r["sim_cluster_sha256"] != sha(cluster) or
            r["manifest_sha256"] != sha(manifest_path)):
            raise RuntimeError("Job, trace, or deployment mismatch: " + key)
        expected_work = sum(r["gpu_busy_fraction"].values()) / r["output_throughput_tokens_per_s"]
        if not math.isclose(expected_work, r["gpu_seconds_per_output_token"], rel_tol=1e-10):
            raise RuntimeError("GPU accounting mismatch: " + key)
        results[(scenario, load, variant, seed)] = r
        rows.append(dict(scenario=scenario, load=load, cell=variant, seed=seed, status="completed",
            source=entry["source"], artifact_sha256=entry["artifact_sha256"], error="",
            trace_sha256=r["trace_sha256"], solution_sha256=r["solution_sha256"],
            sim_cluster_sha256=r["sim_cluster_sha256"],
            **{name: r[name] for name in METRICS}))
    columns = ["scenario", "load", "cell", "seed", "status", "source", "artifact_sha256", "error",
               "trace_sha256", "solution_sha256", "sim_cluster_sha256", *METRICS]
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# E1 放置替代方案结构消融", "", "70B 画像驱动 CPU 仿真；1800 s 固定窗口、零预热、不排空。", "",
             "R-pipelines 在两个拓扑均因容量 152 < 160 模型层副本需求而结构不可行；不计作运行失败。",
             "R-uniform 的最大可行同宽度为 1，是预先披露的单链退化方案。", "",
             "| 拓扑/负载 | 变体 | 成功 | P95 TPOT s | P95 TTFT s | 吞吐 token/s | 完成率 | GPU s/token | 配对相对 R-default TPOT 变化 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    full_groups = 0
    gpu_full_groups = 0
    for scenario, load in (("single", 350), ("single", 700), ("multi", 160), ("multi", 320)):
        for variant in ("R-default", "HR", "R-noshare", "R-uniform", "R-greedy", "R-random"):
            if variant in ("R-default", "HR"):
                cell = "V4" if variant == "R-default" else "HR"
                group = [historical[(scenario, load, cell, seed)] for seed in range(5)]
            else:
                group = [results[(scenario, load, variant, seed)] for seed in range(5)
                         if (scenario, load, variant, seed) in results]
            if len(group) != 5 or any(any(str(r.get(m, "")) == "" for m in METRICS
                                          if m != "gpu_seconds_per_output_token") for r in group):
                lines.append(f"| {scenario}/{load} | {variant} | {len(group)}/5 | — | — | — | — | — | — |")
                continue
            full_groups += 1
            values = {name: mean(float(r[name]) for r in group) for name in METRICS
                      if name != "gpu_seconds_per_output_token"}
            gpu_values = [float(r["gpu_seconds_per_output_token"]) for r in group
                          if str(r.get("gpu_seconds_per_output_token", "")) != ""]
            if len(gpu_values) == 5:
                gpu_full_groups += 1
            gpu_text = (f"{mean(gpu_values):.4f}" if len(gpu_values) == 5
                        else f"— ({len(gpu_values)}/5 有画像)")
            paired = [100 * (float(group[seed]["tpot_p95_s"]) /
                float(historical[(scenario, load, "V4", seed)]["tpot_p95_s"]) - 1) for seed in range(5)]
            delta, half = ci(paired)
            lines.append(f"| {scenario}/{load} | {variant} | 5/5 | {values['tpot_p95_s']:.4f} | "
                f"{values['ttft_p95_s']:.4f} | {values['output_throughput_tokens_per_s']:.2f} | "
                f"{values['completion_fraction']:.3f} | {gpu_text} | "
                f"{delta:+.2f}% ± {half:.2f}pp |")
    lines += ["", "配对区间为 seed0–4 的逐种子 TPOT 相对差的 t(4) 95% CI；失败组只列成功数，不将失败填零。",
              "历史 HR 的部分 GPU 画像缺失，仅标明可用种子数，不由 TPOT 推算 GPU 工作量。", "",
              "## 论文可用表述", "", "在同一执行器和四个共同负载点下，E1 比较了共享放置、Helix 放置与四种可执行的替代放置。",
              "R-uniform 因设备总容量限制退化为单链；独立多流水线 R-pipelines 需要至少 160 层容量，而本实验仅有 152 层，故其设计在该资源池不可行。",
              "R-noshare 的多入口方案经真实模拟器路径验证，不能把单入口代理当作无共享前段。",
              "每项在线结果必须与失败数、配对区间及 GPU 工作量并列解释，不把静态目标分数当成响应时间。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    audit = dict(passed=(len(rows) == 80 and full_groups == 24 and not failures),
        registered_windows=len(manifest["jobs"]), completed=len(results), failed=sum(failures.values()),
        failure_reasons=dict(failures), complete_five_seed_groups=full_groups,
        complete_gpu_profile_groups=gpu_full_groups,
        manifest_sha256=sha(manifest_path), index_sha256=sha(index_path),
        individual_sha256=sha(HERE / "individual.csv"), results_sha256=sha(HERE / "RESULTS_CN.md"),
        report_script_sha256=sha(__file__))
    (HERE / "FINAL_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"E1: {len(results)}/80 completed, {full_groups}/24 full groups, passed={audit['passed']}")

if __name__ == "__main__":
    main()

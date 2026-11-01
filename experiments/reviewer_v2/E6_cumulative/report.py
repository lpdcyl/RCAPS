"""Audit E6 provenance, stage isolation, and complete five-seed comparisons."""
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ROOT, read, sha, write
from .run import HERE, OLD, STAGES, CONDITIONS

METRICS = ("tpot_p95_s", "ttft_p95_s", "gpu_seconds_per_output_token", "completion_fraction")
ORDER = ("H0", "P1", "R2", "S3", "Q4", "T5")
T4 = 2.7764451051977996


def inspect():
    path = HERE / "formal/manifest.json"
    manifest, index = read(path), read(HERE / "formal/index.json")
    if index["status"] != "terminal" or sha(path) != index["manifest_sha256"]:
        raise RuntimeError("E6 formal not terminal or manifest mismatch")
    if manifest["stages"] != STAGES or manifest["old_stages"] != OLD:
        raise RuntimeError("Stage definition changed")
    if len(manifest["jobs"]) != 60 or len(index["jobs"]) != 60:
        raise RuntimeError("Expected 60 new formal jobs")
    if sha(HERE / "smoke/manifest.json") != read(HERE / "smoke/index.json")["manifest_sha256"]:
        raise RuntimeError("Smoke manifest mismatch")
    if any(v["status"] != "completed" for v in read(HERE / "smoke/index.json")["jobs"].values()):
        raise RuntimeError("Smoke incomplete")
    for name, digest in manifest["source_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen source changed: " + name)
    core = ROOT / "experiments/v5_core_supplement"
    for name, rel in (("manifest_sha256", "formal/manifest.json"),
                      ("index_sha256", "formal/index.json"),
                      ("individual_sha256", "individual.csv")):
        if sha(core / rel) != manifest["old_registry"][name]:
            raise RuntimeError("Core registry changed: " + rel)
    records, failures = {}, []
    for job in manifest["jobs"]:
        key = job["key"]
        state = index["jobs"][key]
        artifact = ROOT / state["source"]
        if sha(artifact) != state["artifact_sha256"]:
            raise RuntimeError("Artifact SHA mismatch: " + key)
        row = read(artifact)
        if row["job"] != job or row["status"] != state["status"]:
            raise RuntimeError("Job metadata mismatch: " + key)
        identity = (job["scenario"], job["load"], job["seed"], job["stage"])
        if state["status"] == "completed":
            if artifact.name != "result.json" or row["manifest_sha256"] != sha(path):
                raise RuntimeError("Result identity mismatch: " + key)
            if len(row["query_samples"]) != row["arrivals"]:
                raise RuntimeError("Request sample mismatch: " + key)
            if row["admission"]["mode"] != STAGES[job["stage"]]["admission"] or row["admission"]["routing_state"] != STAGES[job["stage"]]["routing_state"]:
                raise RuntimeError("Stage intervention mismatch: " + key)
            if STAGES[job["stage"]]["chunk_bytes"] == 0 and row["phase_link_profile"].get("paused_chunks", 0):
                raise RuntimeError("Chunking unexpectedly active: " + key)
            records[identity] = dict(row=row, source=state["source"], sha=state["artifact_sha256"], origin="new")
        elif state["status"] == "failed":
            failures.append(dict(job=job, error=row.get("error", row.get("classification")), source=state["source"], sha=state["artifact_sha256"]))
        else:
            raise RuntimeError("Nonterminal job: " + key)
    for scenario, load in CONDITIONS:
        for seed in range(5):
            for stage, cell in OLD.items():
                key = f"{scenario}/load{load}/{cell}/seed{seed}"
                reference = manifest["old_rows"][key]
                source = ROOT / reference["source"]
                if sha(source) != reference["sha256"]:
                    raise RuntimeError("Old source changed: " + key)
                row = read(source)
                for name in ("trace_sha256", "solution_sha256", "sim_cluster_sha256"):
                    # Historical V4 rows store solution/sim_cluster paths, while the
                    # frozen E6 registry stores their prechecked file digests.
                    actual = row.get(name)
                    if actual is None and name in ("solution_sha256", "sim_cluster_sha256"):
                        actual = sha(Path(row[name.removesuffix("_sha256")]))
                        row[name] = actual
                    if actual != reference[name]:
                        raise RuntimeError("Old provenance mismatch: " + key + ": " + name)
                records[(scenario, load, seed, stage)] = dict(row=row, source=reference["source"], sha=reference["sha256"], origin="old")
    for (scenario, load, seed, stage), item in records.items():
        anchor = records[(scenario, load, seed, "T5")]["row"]
        for name in ("trace_sha256",):
            if item["row"][name] != anchor[name]:
                raise RuntimeError(f"Mismatched same-seed trace: {scenario}/{load}/{seed}/{stage}")
        if stage != "H0" and any(item["row"][name] != anchor[name] for name in ("solution_sha256", "sim_cluster_sha256")):
            raise RuntimeError(f"Mismatched RCAPS deployment: {scenario}/{load}/{seed}/{stage}")
        for metric in METRICS:
            value = item["row"].get(metric)
            if not isinstance(value, (float, int)) or not math.isfinite(value):
                raise RuntimeError(f"Missing metric {metric}: {scenario}/{load}/{seed}/{stage}")
    return manifest, index, records, failures


def main():
    manifest, index, records, failures = inspect()
    lines = ["# E6 机制逐项叠加结果", "",
             "70B 画像驱动 CPU 仿真；四负载、seed0–4，1800 s 零预热、不排空。H0/P1/T5 为经 SHA 核验的旧核心实验，新做 R2/S3/Q4。",
             "H0→P1 只换部署；P1→R2 换 MaxFlow 为 RCAPS DAG；R2→S3 加稀疏准入；S3→Q4 加会话持续代价；Q4→T5 加慢链路 4 MiB Prompt 传输分块。", "",
             "| 场景/负载 | 阶段 | 成功 | P95 TPOT s | P95 TTFT s | GPU 秒/token | 完成率 |",
             "|---|---|---:|---:|---:|---:|---:|"]
    paired = []
    for scenario, load in CONDITIONS:
        for stage in ORDER:
            rows = [records[(scenario, load, seed, stage)]["row"]
                    for seed in range(5) if (scenario, load, seed, stage) in records]
            if len(rows) == 5:
                fmt = [f"{mean(x[metric] for x in rows):.4f}" for metric in METRICS]
            else:
                fmt = ["—"] * 4
            lines.append(f"| {scenario}/{load} | {stage} | {len(rows)}/5 | " + " | ".join(fmt) + " |")
        for left, right in zip(ORDER, ORDER[1:]):
            common = [seed for seed in range(5) if (scenario, load, seed, left) in records and (scenario, load, seed, right) in records]
            for metric in METRICS:
                if len(common) != 5:
                    paired.append(dict(scenario=scenario, load=load, from_stage=left, to_stage=right, metric=metric, matched_seeds=len(common), mean_difference=None, ci95=None))
                    continue
                d = [records[(scenario, load, seed, right)]["row"][metric] - records[(scenario, load, seed, left)]["row"][metric] for seed in common]
                mid = mean(d)
                half = T4 * stdev(d) / math.sqrt(5)
                paired.append(dict(scenario=scenario, load=load, from_stage=left, to_stage=right, metric=metric, matched_seeds=5, mean_difference=mid, ci95=[mid-half, mid+half]))
    lines += ["", "## 逐步配对差异", "", "右阶段减左阶段；延迟和 GPU 秒/token 负值为下降，完成率正值为上升。仅 5/5 配对给 df=4 双侧 t 95% CI。", "",
              "| 负载 | 对比 | 指标 | 配对均差 | 95% CI |", "|---|---|---|---:|---:|"]
    for row in paired:
        interval = row["ci95"]
        lines.append(f"| {row['scenario']}/{row['load']} | {row['from_stage']}→{row['to_stage']} | {row['metric']} | " +
            (f"{row['mean_difference']:+.5f} | [{interval[0]:+.5f}, {interval[1]:+.5f}] |" if interval else "— | — |"))
    lines += ["", "## 解释边界", "",
              "本表是预先固定顺序下的条件增量。P1→R2 是完整路由器迁移，不可称纯会话项；S3→Q4 才仅改变会话持续代价。顺序相关差异不证明普遍超加性协同。",
              f"新增原批成功 {len(records)-60}/60、失败 {len(failures)}/60；失败原件保留，不能当成数值零。",
              "E4 WSL2 网络微基准及其他协议不能混进本固定窗口表。"]
    report = HERE / "RESULTS_CN.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "paired.json", paired)
    audit = {"passed": True, "registered_new": 60, "completed_new": len(records)-60,
             "failed_new": len(failures), "reused_verified": 60,
             "complete_six_stage_groups": sum(all((scenario, load, seed, stage) in records for seed in range(5) for stage in ORDER) for scenario, load in CONDITIONS),
             "manifest_sha256": sha(HERE / "formal/manifest.json"), "index_sha256": sha(HERE / "formal/index.json"),
             "report_sha256": sha(report), "paired_sha256": sha(HERE / "paired.json"),
             "failures": failures, "scope": "Provenance and metric completeness, not a claim that all stages improve"}
    write(HERE / "FINAL_AUDIT.json", audit)
    print({k: v for k, v in audit.items() if k != "failures"})


if __name__ == "__main__":
    main()

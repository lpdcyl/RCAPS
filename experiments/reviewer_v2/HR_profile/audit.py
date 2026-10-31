"""One-time integrity audit for the independent HR profiling supplement."""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
T4 = 2.7764451051977987

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    from experiments.v5_core_supplement.run import paths
    from experiments.reviewer_v2.HR_profile.run import check
    manifest_path = HERE / "formal/manifest.json"
    manifest = read(manifest_path)
    check(manifest)
    index_path = HERE / "formal/index.json"
    index = read(index_path)
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Formal batch not terminal or manifest mismatch")
    if set(index["jobs"]) != {job["key"] for job in manifest["jobs"]}:
        raise RuntimeError("Wrong job set")
    with (ROOT / "experiments/v5_core_supplement/individual.csv").open(newline="", encoding="utf-8-sig") as stream:
        old = {(r["scenario"], int(r["load"]), int(r["seed"])): r for r in csv.DictReader(stream)
               if r["cell"] == "HR" and (r["scenario"], int(r["load"]))
               in (("single", 700), ("multi", 320))}
    if len(old) != 10:
        raise RuntimeError(f"Expected ten historical HR rows, got {len(old)}")
    rows = []
    failed = []
    for job in manifest["jobs"]:
        key = job["key"]
        entry = index["jobs"][key]
        if entry["status"] != "completed":
            failed.append(key)
            continue
        source = ROOT / entry["source"]
        if sha(source) != entry["artifact_sha256"]:
            raise RuntimeError("Result hash mismatch: " + key)
        row = read(source)
        older = old[(job["scenario"], job["load"], job["seed"])]
        solution, cluster, _ = paths(job["scenario"], "HR")
        if (row["job"] != job or row["manifest_sha256"] != sha(manifest_path)
                or row["trace_sha256"] != older["trace_sha256"]
                or row["solution_sha256"] != sha(solution)
                or row["solution_sha256"] != older["solution_sha256"]
                or row["sim_cluster_sha256"] != sha(cluster)
                or row["sim_cluster_sha256"] != older["sim_cluster_sha256"]):
            raise RuntimeError("Job/trace/deployment mismatch: " + key)
        if row["output_throughput_tokens_per_s"] <= 0 or not row["gpu_busy_fraction"]:
            raise RuntimeError("Missing measured resource data: " + key)
        work = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
        if not math.isfinite(work) or not math.isclose(work, row["gpu_seconds_per_output_token"], rel_tol=1e-10):
            raise RuntimeError("GPU accounting mismatch: " + key)
        rows.append(dict(scenario=job["scenario"], load=job["load"], cell="HR", seed=job["seed"],
            status="completed", tpot_p95_s=row["tpot_p95_s"], gpu_seconds_per_output_token=work,
            trace_sha256=row["trace_sha256"], solution_sha256=row["solution_sha256"],
            sim_cluster_sha256=row["sim_cluster_sha256"], historical_tpot_p95_s=older["tpot_p95_s"],
            historical_tpot_delta_s=row["tpot_p95_s"] - float(older["tpot_p95_s"]),
            source=entry["source"], artifact_sha256=entry["artifact_sha256"]))
    if rows:
        with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[row["scenario"]].append(row)
    lines = ["# E3a HR 被动资源画像补测", "", "旧 HR 证据未改；新十窗口独立于原 V5 核心交叉实验。", "",
             "| 条件 | 成功数 | 新 P95 TPOT 均值 s | GPU 秒/token 均值 | 新减旧 P95 TPOT 均值 s |",
             "|---|---:|---:|---:|---:|"]
    for scenario, load in (("single", 700), ("multi", 320)):
        group = groups[scenario]
        lines.append(f"| {scenario}/{load} | {len(group)}/5 | " +
            (f"{mean(float(r['tpot_p95_s']) for r in group):.5f} | " +
             f"{mean(float(r['gpu_seconds_per_output_token']) for r in group):.5f} | " +
             f"{mean(float(r['historical_tpot_delta_s']) for r in group):+.5f} |" if len(group) == 5
             else "不足五种子，不报告均值 | - | - |"))
    lines += ["", "资源指标由同一窗口的 GPU 忙碌分数之和除以输出 token 吞吐；差异为配对同种子的新旧 P95 TPOT。",
              "若环境/实现造成差异，本补测只用于 E3a HR 点，不替换原 V5 延迟主结果。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    passed = not failed and len(rows) == 10 and all(len(groups[s]) == 5 for s in ("single", "multi"))
    write(HERE / "FINAL_AUDIT.json", dict(passed=passed, completed=len(rows), failed=len(failed),
          failed_keys=failed, historical_rows=len(old), manifest_sha256=sha(manifest_path),
          index_sha256=sha(index_path), audit_script_sha256=sha(__file__),
          individual_sha256=sha(HERE / "individual.csv") if rows else None,
          results_sha256=sha(HERE / "RESULTS_CN.md")))
    print(f"HR profile audit: {len(rows)}/10 complete, passed={passed}")

if __name__ == "__main__":
    main()

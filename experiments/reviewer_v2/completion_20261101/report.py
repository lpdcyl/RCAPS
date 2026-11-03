"""Audit the independent completion campaigns without rewriting their sources."""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ROOT, read, sha, write

from .run import E5A, E6, HERE, check, milp_paths

T4 = 2.7764451051977987
METRICS = ("tpot_p95_s", "ttft_p95_s", "completion_fraction",
           "output_throughput_tokens_per_s", "gpu_seconds_per_output_token")


def group_key(campaign, job):
    if campaign == "e5a":
        return f"load{job['load']}", job["method"]
    if campaign == "e6":
        return f"{job['scenario']}/load{job['load']}", job["stage"]
    return f"{job['scenario']}/load{job['load']}", job["layout"]


def expected_deployment(campaign, job):
    if campaign == "e5a":
        from experiments.reviewer_v2.E5_scale_kv.run import PHYSICAL, paths

        solution, cluster = paths(job["method"])
        return sha(solution), sha(cluster), sha(PHYSICAL)
    if campaign == "e6":
        from benchmarks.layout import scenario
        from experiments.v5_core_supplement.run import paths

        name = job["scenario"]
        solution, cluster, _ = paths(name, "RR")
        return sha(solution), sha(cluster), sha(scenario(name)[0])
    physical, _, solution, cluster = milp_paths(job)
    return sha(solution), sha(cluster), sha(physical)


def paired(values):
    delta = [right - left for left, right in values]
    center = mean(delta)
    half = T4 * stdev(delta) / math.sqrt(5)
    return {"n": 5, "mean_difference": center,
            "ci95_low": center - half, "ci95_high": center + half}


def audit(campaign, phase):
    base = HERE / campaign / phase
    manifest_path, index_path = base / "manifest.json", base / "index.json"
    manifest, index = read(manifest_path), read(index_path)
    historical_rows = (read(E6 / "formal/manifest.json")["old_rows"]
                       if campaign == "e6" and phase == "formal" else {})
    if index["status"] != "terminal" or index["manifest_sha256"] != sha(manifest_path):
        raise RuntimeError("Campaign is not terminal with its frozen manifest")
    check(campaign, manifest)
    jobs = {job["key"]: job for job in manifest["jobs"]}
    if len(jobs) != len(manifest["jobs"]) or set(jobs) != set(index["jobs"]):
        raise RuntimeError("Registered jobs and index keys differ")
    if phase == "formal":
        expected = {"e5a": 60, "e6": 60, "milp": 50}[campaign]
        if len(jobs) != expected:
            raise RuntimeError(f"Expected {expected} formal jobs, got {len(jobs)}")
    rows, results, traces = [], {}, defaultdict(set)
    counts = Counter()
    for key, job in jobs.items():
        state = index["jobs"][key]
        if state["status"] not in ("completed", "failed"):
            raise RuntimeError("Nonterminal job: " + key)
        source = ROOT / state["source"]
        if not source.is_file() or sha(source) != state["artifact_sha256"]:
            raise RuntimeError("Missing or changed artifact: " + key)
        artifact = read(source)
        if artifact.get("classification") == "controller_interrupted":
            if artifact.get("key") != key or state["status"] != "failed":
                raise RuntimeError("Interrupted job identity mismatch: " + key)
            recovered = list(base.glob("recovery_*/amendment.json"))
            if not any(key in {item["key"] for item in read(path)["interrupted"]}
                       for path in recovered):
                raise RuntimeError("Missing reboot amendment for: " + key)
        elif artifact.get("job") != job:
            raise RuntimeError("Artifact job identity mismatch: " + key)
        counts[state["status"]] += 1
        line = {"key": key, "status": state["status"], "source": state["source"],
                "artifact_sha256": state["artifact_sha256"],
                "error": artifact.get("error", artifact.get("classification", ""))}
        if state["status"] == "completed":
            if (artifact.get("status") != "completed"
                    or artifact.get("manifest_sha256") != sha(manifest_path)
                    or artifact.get("duration_s") != job["duration_s"]
                    or artifact.get("seed") != job["seed"]
                    or artifact.get("warmup_s") != 0
                    or artifact.get("evaluation_protocol") != "fixed_window_no_tail_drain"
                    or len(artifact.get("query_samples", {})) != artifact.get("arrivals")):
                raise RuntimeError("Protocol or query samples mismatch: " + key)
            solution, cluster, physical = expected_deployment(campaign, job)
            actual = (artifact["solution_sha256"], artifact["sim_cluster_sha256"],
                      artifact.get("physical_sha256", artifact.get("physical_cluster_sha256")))
            if actual != (solution, cluster, physical):
                raise RuntimeError("Deployment mismatch: " + key)
            if campaign == "e6" and phase == "formal":
                for cell in ("HHplus", "RHplus", "V4"):
                    old_key = (f"{job['scenario']}/load{job['load']}/{cell}"
                               f"/seed{job['seed']}")
                    old = historical_rows[old_key]
                    if old["trace_sha256"] != artifact["trace_sha256"]:
                        raise RuntimeError("Historical request trace mismatch: " + key)
                    if cell in ("RHplus", "V4") and (
                            old["solution_sha256"] != solution
                            or old["sim_cluster_sha256"] != cluster):
                        raise RuntimeError("Historical RCAPS deployment mismatch: " + key)
            throughput = artifact["output_throughput_tokens_per_s"]
            if throughput <= 0 or not math.isclose(
                    artifact["gpu_seconds_per_output_token"],
                    sum(artifact["gpu_busy_fraction"].values()) / throughput,
                    rel_tol=1e-12):
                raise RuntimeError("GPU accounting mismatch: " + key)
            group, method = group_key(campaign, job)
            traces[(group, job["seed"])].add(artifact["trace_sha256"])
            results[(group, method, job["seed"])] = artifact
            line.update(group=group, method=method, seed=job["seed"],
                        trace_sha256=artifact["trace_sha256"],
                        solution_sha256=solution, sim_cluster_sha256=cluster,
                        **{metric: artifact[metric] for metric in METRICS})
        rows.append(line)
    if any(len(values) != 1 for values in traces.values()):
        raise RuntimeError("Same-seed request traces differ across methods")
    groups = defaultdict(dict)
    for job in jobs.values():
        group, method = group_key(campaign, job)
        groups[(group, method)][job["seed"]] = results.get((group, method, job["seed"]))
    complete = {key for key, seeds in groups.items()
                if phase == "formal" and set(seeds) == set(range(5))
                and all(seeds.values())}
    comparisons = {}
    for group in sorted({key[0] for key in groups}):
        if campaign == "e5a":
            pairs = (("Helix", "RCAPS"), ("Helix+", "RCAPS-KV"))
        elif campaign == "e6":
            pairs = (("R2", "S3"), ("S3", "Q4"))
        else:
            pairs = (("official", "120"), ("official", "480"), ("120", "480"))
        for left, right in pairs:
            if (group, left) not in complete or (group, right) not in complete:
                continue
            comparisons[f"{group}/{left}->{right}"] = {
                metric: paired([(results[(group, left, seed)][metric],
                                 results[(group, right, seed)][metric])
                                for seed in range(5)])
                for metric in METRICS}
    if phase == "formal":
        path = HERE / campaign / "individual.csv"
        columns = ("key", "status", "source", "artifact_sha256", "error",
                   "group", "method", "seed", "trace_sha256", "solution_sha256",
                   "sim_cluster_sha256", *METRICS)
        with path.open("x", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        write(HERE / campaign / "paired.json", comparisons)
        lines = [f"# {campaign.upper()} 独立补全批次", "",
                 f"正式成功 {counts['completed']}/{len(jobs)}；失败 {counts['failed']}/{len(jobs)}。",
                 f"完整五种子组 {len(complete)}/{len(groups)}；配对比较 {len(comparisons)} 组。", "",
                 "失败与旧正式批及旧重放分列；本批仅为画像驱动 CPU 仿真。", "",
                 "| 条件 | 成功 | P95 TPOT s | P95 TTFT s | GPU s/token | 完成率 |", 
                 "|---|---:|---:|---:|---:|---:|"]
        for group, method in sorted(groups):
            successes = [value for value in groups[(group, method)].values() if value]
            if (group, method) in complete:
                values = [mean(value[metric] for value in successes) for metric in
                          ("tpot_p95_s", "ttft_p95_s", "gpu_seconds_per_output_token",
                           "completion_fraction")]
                cells = " | ".join(f"{value:.4f}" for value in values)
            else:
                cells = " | ".join(["—"] * 4)
            lines.append(f"| {group}/{method} | {len(successes)}/5 | {cells} |")
        (HERE / campaign / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    audit_data = {"passed": True, "campaign": campaign, "phase": phase,
                  "registered": len(jobs), "completed": counts["completed"],
                  "failed": counts["failed"], "complete_five_seed_groups": len(complete),
                  "paired_groups": len(comparisons),
                  "manifest_sha256": sha(manifest_path), "index_sha256": sha(index_path),
                  "report_script_sha256": sha(Path(__file__))}
    if phase == "formal":
        audit_data.update(individual_sha256=sha(HERE / campaign / "individual.csv"),
                          paired_sha256=sha(HERE / campaign / "paired.json"),
                          results_sha256=sha(HERE / campaign / "RESULTS_CN.md"))
    write(HERE / campaign / ("FINAL_AUDIT.json" if phase == "formal" else "SMOKE_AUDIT.json"),
          audit_data)
    return audit_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", choices=("e5a", "e6", "milp"))
    parser.add_argument("phase", choices=("smoke", "formal"), default="formal", nargs="?")
    args = parser.parse_args()
    print(audit(args.campaign, args.phase))


if __name__ == "__main__":
    main()

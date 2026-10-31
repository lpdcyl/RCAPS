"""Reconcile preserved V4 failures with independent seed 3/4 replays."""
import argparse
import csv
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v4_paper_seed45 import run as base

HERE = Path(__file__).resolve().parent
REPLAY = HERE / "retry_env"
OUT = HERE / "five_seed_reconciled"
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")
T4 = 2.7764451051977987


def check_artifact(path, digest):
    if base.sha(base.ROOT / path) != digest:
        raise RuntimeError(f"Source hash mismatch: {path}")
    return base.read(base.ROOT / path)


def reconcile():
    manifest = base.check_manifest()
    initial = base.read(base.INDEX)
    replay_manifest = base.read(REPLAY / "manifest.json")
    replay = base.read(REPLAY / "index.json")
    audit = base.read(REPLAY / "FINAL_AUDIT.json")
    if initial["status"] != "terminal" or replay["status"] != "terminal":
        raise RuntimeError("Original or replay batch is not terminal")
    if not audit["passed"] or audit["replays"] != len(manifest["jobs"]):
        raise RuntimeError("Replay audit incomplete")
    if replay_manifest["original_manifest_sha256"] != base.sha(base.MANIFEST) or replay_manifest["original_index_sha256"] != base.sha(base.INDEX):
        raise RuntimeError("Original source changed after replay registration")
    if replay["manifest_sha256"] != base.sha(REPLAY / "manifest.json"):
        raise RuntimeError("Replay manifest hash mismatch")
    refs = {(x["group"], x["scenario"], x["load"], x["cell"], x["seed"]): x for x in manifest["base_seed_references"]}
    groups, individual, failures = defaultdict(list), [], []
    for job in manifest["jobs"]:
        ident = (job["group"], job["scenario"], job["load"], job["cell"])
        if ident not in groups:
            for seed in base.OLD_SEEDS:
                ref = refs[(*ident, seed)]
                data = check_artifact(ref["path"], ref["sha256"])
                groups[ident].append((seed, "completed", data, ref["path"], ref["sha256"], "historical"))
        initial_entry = initial["jobs"][job["key"]]
        if initial_entry["status"] != "failed":
            raise RuntimeError(f"Unexpected original status: {job['key']}")
        check_artifact(initial_entry["source"], initial_entry["artifact_sha256"])
        entry = replay["jobs"][job["key"]]
        data = check_artifact(entry["source"], entry["artifact_sha256"])
        groups[ident].append((job["seed"], entry["status"], data, entry["source"],
                              entry["artifact_sha256"], "independent_replay"))
        if entry["status"] != "completed":
            failures.append({"key": job["key"], "error": data.get("error"),
                             "classification": data.get("classification"), "source": entry["source"]})
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# V4 第 7 节五种子补齐：原失败与独立重放合并视图", "",
             "复用历史种子 0–2。种子 3、4 的首次正式尝试全部失败，其原件仍保留；下表仅使用独立重放中的有效结果。",
             "新结果不替换原批 index.json 或 failure.json。均值 ± 样本标准差及 t(4) 95% CI 仅给完整五种子组。", "",
             "| 配置 | 成功 | P95 TPOT s (均值 ± SD; 95% CI) | P95 TTFT s (均值 ± SD; 95% CI) | token/s | 完成率 | GPU s/token |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for ident, rows in groups.items():
        good = [x for x in rows if x[1] == "completed"]
        full = len(good) == 5 and {x[0] for x in good} == set(range(5))
        formatted = []
        for metric in METRICS:
            if not full:
                formatted.append("不汇总")
                continue
            values = [float(x[2][metric]) for x in good]
            avg, sd = mean(values), stdev(values)
            formatted.append(f"{avg:.4f} ± {sd:.4f}; [{avg-T4*sd/math.sqrt(5):.4f}, {avg+T4*sd/math.sqrt(5):.4f}]")
        lines.append(f"| {'/'.join(map(str, ident))} | {len(good)}/5 | " + " | ".join(formatted) + " |")
        for seed, status, data, path, digest, attempt in rows:
            individual.append({"group": ident[0], "scenario": ident[1], "load": ident[2],
                "cell": ident[3], "seed": seed, "status": status, "attempt": attempt,
                **{metric: data.get(metric) if status == "completed" else None for metric in METRICS},
                "trace_sha256": data.get("trace_sha256") if status == "completed" else None,
                "source": path, "sha256": digest, "error": data.get("error") if status != "completed" else None})
    lines += ["", "## 原批与重放状态", "",
              f"原批：失败 {len(manifest['jobs'])}/{len(manifest['jobs'])}；独立重放：{sum(x['status']=='completed' for x in replay['jobs'].values())}/{len(manifest['jobs'])} 成功。",
              "不足五种子的配置仅列成功数，不将失败填零；任何残留失败见 failures.json。"]
    with (OUT / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(individual[0]))
        writer.writeheader()
        writer.writerows(individual)
    (OUT / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    base.write(OUT / "failures.json", failures)
    base.write(OUT / "FINAL_AUDIT.json", {"passed": True, "groups": len(groups),
        "five_seed_groups": sum(len([x for x in v if x[1] == "completed"]) == 5 for v in groups.values()),
        "historical_rows": sum(x["attempt"] == "historical" for x in individual),
        "replay_rows": sum(x["attempt"] == "independent_replay" for x in individual),
        "replay_failures": len(failures), "original_manifest_sha256": base.sha(base.MANIFEST),
        "original_index_sha256": base.sha(base.INDEX), "replay_manifest_sha256": base.sha(REPLAY / "manifest.json"),
        "replay_index_sha256": base.sha(REPLAY / "index.json"), "individual_sha256": base.sha(OUT / "individual.csv"),
        "results_sha256": base.sha(OUT / "RESULTS_CN.md")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.wait:
        while not (REPLAY / "FINAL_AUDIT.json").exists():
            time.sleep(30)
        reconcile()
    elif args.run:
        reconcile()
    else:
        parser.error("choose --wait or --run")

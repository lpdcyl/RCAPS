"""Pre-registered P1-5 traffic generalization on frozen 70B placements.

Run with the Windows gllm interpreter. Each worker is an isolated Python
process; formal results never overwrite earlier V5 results or failed runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import (
    ENV, ROOT, check, now, paths, read, relative, sha, write,
)

HERE = Path(__file__).resolve().parent / "generalization"
LOADS = {"single": 700, "multi": 320}
CONDITIONS = ("prompt2", "prompt4", "gamma_cv2", "gamma_cv4", "output_half", "output2")
CELLS = ("HH", "HHplus", "V4")
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s", "completion_fraction")


def traffic(scenario: str, seed: int, duration: int, condition: str):
    from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

    original = OnlineRequestFeeder(LOADS[scenario], 0, duration, seed).trace
    base = [(float(t), int(prompt), int(output)) for t, prompt, output in original]
    if condition.startswith("prompt"):
        scale = int(condition.removeprefix("prompt"))
        factor = sum(scale * p + o for _, p, o in base) / sum(p + o for _, p, o in base)
        changed = [(t * factor, p * scale, o) for t, p, o in base]
    elif condition.startswith("output"):
        scale = 0.5 if condition == "output_half" else 2
        factor = sum(p + max(1, round(o * scale)) for _, p, o in base) / sum(p + o for _, p, o in base)
        changed = [(t * factor, p, max(1, round(o * scale))) for t, p, o in base]
    else:
        cv = 2 if condition == "gamma_cv2" else 4
        rng = random.Random(1949 + seed)
        mean_gap = duration / len(base)
        current = 0.0
        changed = []
        for _, p, o in base:
            current += rng.gammavariate(1 / cv**2, mean_gap * cv**2)
            changed.append((current, p, o))
    return [(t, p, o) for t, p, o in changed if t < duration]


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    condition, scenario, cell = job["condition"], job["scenario"], job["cell"]
    trace = traffic(scenario, job["seed"], job["duration"], condition)
    assert trace and all(t >= 0 and p > 0 and o > 0 for t, p, o in trace)
    solution, cluster, physical = paths(scenario, cell)
    factory = None
    delegate = None
    if cell == "HHplus":
        factory = HelixPlus
    elif cell == "V4":
        state = read(solution.parent / "placement.json")["state"]
        factory = lambda sim: AdmissionScheduler(sim, state=state, admission="sparse", routing_state="live")
        delegate = MechanismProbe(PromptTransferChunkHook(4_194_304, scope="slow"))
    row = run(scenario, "helix" if cell == "HH" else "queue_dag", LOADS[scenario],
              job["duration"], 0, job["seed"], solution, cluster,
              physical_cluster=physical, scheduler_factory=factory,
              compact=True, record_query_samples=True, profile_resources=True,
              phase_link_probe=SetupProbe(delegate=delegate), trace_override=trace)
    if cell == "V4":
        row.update(row["phase_link_profile"]["corrected_network_accounting"])
        row["network_accounting"] = "v4_chunk_aware_v1"
    row.update(condition=condition, cell=cell, traffic_count=len(trace),
               solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
               gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) /
               row["output_throughput_tokens_per_s"])
    assert len(row["query_samples"]) == row["arrivals"] == len(trace)
    return row


def register(phase, workers):
    target = HERE / phase / "manifest.json"
    if target.exists():
        manifest = read(target)
        check(manifest)
        assert manifest["sources_sha256"][relative(Path(__file__))] == sha(Path(__file__))
        return manifest
    if phase == "formal":
        smoke = read(HERE / "smoke/index.json")
        assert smoke["status"] == "terminal"
        expected_failures = {f"{scenario}/prompt2/{cell}/seed100"
                             for scenario in LOADS for cell in ("HH", "HHplus")}
        assert {key for key, entry in smoke["jobs"].items()
                if entry["status"] == "failed"} == expected_failures
        for key in expected_failures:
            entry = smoke["jobs"][key]
            artifact = ROOT / entry["source"]
            assert sha(artifact) == entry["artifact_sha256"]
            assert "No next level node meets scheduling requirement" in read(artifact)["error"]
    duration = 60 if phase == "smoke" else 1800
    seeds = (100,) if phase == "smoke" else tuple(range(5))
    conditions = ("prompt2", "gamma_cv4", "output2") if phase == "smoke" else CONDITIONS
    jobs = [dict(key=f"{scenario}/{condition}/{cell}/seed{seed}", scenario=scenario,
                 load=load, condition=condition, cell=cell, seed=seed, duration=duration)
            for seed in seeds for scenario, load in LOADS.items()
            for condition in conditions for cell in CELLS]
    sources = dict(read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")["sources_sha256"])
    sources[relative(Path(__file__))] = sha(Path(__file__))
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
                    sources_sha256=sources, worker_limit=workers, timeout_wall_s=14400,
                    loads=LOADS, conditions=conditions, seeds=seeds, duration_s=duration,
                    protocol="1800s fixed-window, zero warmup, no drain; 60s smoke",
                    comparison="Identical generated traffic for HH, HHplus and V4 within a condition/seed/topology",
                    prompt_output_scaling="Stretch arrival timestamps by total-token-size ratio to keep offered token/s comparable; truncate at window",
                    gamma="Shape=1/CV^2, scale=mean interarrival*CV^2, independent seeded RNG; preserve ordered length sequence",
                    failure_policy="One attempt per key; preserve failure and never impute missing metric",
                    environment=dict(executable=sys.executable, env=ENV))
    write(target, manifest)
    return manifest


def worker(phase, key):
    manifest = read(HERE / phase / "manifest.json")
    job = next(j for j in manifest["jobs"] if j["key"] == key)
    directory = HERE / phase / "runs" / key
    started = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job)
        check(manifest)
        row.update(status="completed", job=job, manifest_sha256=sha(HERE / phase / "manifest.json"),
                   elapsed_wall_s=time.perf_counter() - started, finished_at=now())
        write(directory / "result.json", row)
    except BaseException as error:
        write(directory / "failure.json", dict(status="failed", job=job, error=repr(error),
              traceback=traceback.format_exc(), manifest_sha256=sha(HERE / phase / "manifest.json"),
              elapsed_wall_s=time.perf_counter() - started, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase, workers):
    manifest = register(phase, workers)
    directory = HERE / phase
    index_path = directory / "index.json"
    if index_path.exists():
        index = read(index_path)
        assert index["manifest_sha256"] == sha(directory / "manifest.json")
        assert not any(v["status"] == "running" for v in index["jobs"].values())
    else:
        index = dict(status="running", controller_pid=os.getpid(), registered_at=now(),
                     manifest_sha256=sha(directory / "manifest.json"),
                     jobs={j["key"]: {"status": "pending"} for j in manifest["jobs"]})
    pending = [j for j in manifest["jobs"] if index["jobs"][j["key"]]["status"] == "pending"]
    active = {}
    write(index_path, index)
    while pending or active:
        while pending and len(active) < manifest["worker_limit"]:
            job = pending.pop(0)
            run_dir = directory / "runs" / job["key"]
            run_dir.mkdir(parents=True, exist_ok=False)
            log = (run_dir / "worker.log").open("x", encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                                        "experiments.v6_completion.generalization", "--phase", phase,
                                        "--worker", job["key"]], cwd=ROOT, env=dict(os.environ, **ENV),
                                       stdout=log, stderr=log)
            active[job["key"]] = (process, log, time.monotonic())
            index["jobs"][job["key"]] = dict(status="running", pid=process.pid, started_at=now())
            write(index_path, index)
        for key, (process, log, started) in list(active.items()):
            code = process.poll()
            timeout = code is None and time.monotonic() - started > manifest["timeout_wall_s"]
            if timeout:
                process.kill()
                code = process.wait()
            if code is None:
                continue
            log.close()
            del active[key]
            run_dir = directory / "runs" / key
            passed = code == 0 and (run_dir / "result.json").exists()
            artifact = run_dir / ("result.json" if passed else "failure.json")
            if not artifact.exists():
                write(artifact, dict(status="failed", classification="timeout" if timeout else "abnormal_exit",
                                     exit_code=code, finished_at=now()))
            index["jobs"][key].update(status="completed" if passed else "failed", exit_code=code,
                                      source=relative(artifact), artifact_sha256=sha(artifact), finished_at=now())
            write(index_path, index)
            print("END", key, index["jobs"][key]["status"], flush=True)
        if active:
            time.sleep(2)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)
    if phase == "formal":
        report()


def report():
    directory = HERE / "formal"
    manifest, index = read(directory / "manifest.json"), read(directory / "index.json")
    assert index["status"] == "terminal"
    rows, groups = [], defaultdict(dict)
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        assert entry["status"] in ("completed", "failed")
        artifact = ROOT / entry["source"]
        assert sha(artifact) == entry["artifact_sha256"]
        outcome = read(artifact)
        row = {**{k: job[k] for k in ("scenario", "load", "condition", "cell", "seed")},
               "status": entry["status"], "source": entry["source"],
               "artifact_sha256": entry["artifact_sha256"],
               "error": outcome.get("error", ""), "trace_sha256": outcome.get("trace_sha256", ""),
               **{k: outcome.get(k) for k in METRICS}}
        rows.append(row)
        if entry["status"] == "completed":
            assert len(outcome["query_samples"]) == outcome["arrivals"]
            groups[(job["scenario"], job["condition"], job["seed"])][job["cell"]] = outcome
    for members in groups.values():
        assert len({item["trace_sha256"] for item in members.values()}) == 1
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 负载分布泛化（P1-5）", "",
             "70B、固定 1800 s 窗口、五种子；RCAPS、Helix 与 Helix+ 在每个条件下共享同一请求轨迹。",
             "长 Prompt 与输出长度条件按总 token 数比例拉伸请求到达时刻，以维持预期 offered token/s；Gamma 条件保持长度序列和平均请求间隔。",
             "所有指标均来自 CPU 离散事件模拟；失败保留，不填零。", "",
             "| 拓扑 | 条件 | 方法 | 成功 | P95 TPOT(s) | P95 TTFT(s) | 输出 token/s | 完成率 |",
             "|---|---|---|---:|---:|---:|---:|---:|"]
    for scenario in LOADS:
        for condition in CONDITIONS:
            for cell in CELLS:
                subset = [r for r in rows if (r["scenario"], r["condition"], r["cell"]) ==
                          (scenario, condition, cell) and r["status"] == "completed"]
                vals = [f"{mean(r[k] for r in subset):.4f} ± {stdev(r[k] for r in subset):.4f}"
                        if len(subset) == 5 else "未汇总" for k in METRICS]
                lines.append(f"| {scenario} | {condition} | {cell} | {len(subset)}/5 | " + " | ".join(vals) + " |")
    lines += ["", "| 拓扑 | 条件 | 对照 | 配对种子 | TPOT 降幅均值 [95% CI] |",
              "|---|---|---|---:|---:|"]
    for scenario in LOADS:
        for condition in CONDITIONS:
            for base in ("HH", "HHplus"):
                paired = [groups[(scenario, condition, seed)] for seed in range(5)]
                if all(base in x and "V4" in x for x in paired):
                    reductions = [100 * (1 - x["V4"]["tpot_p95_s"] / x[base]["tpot_p95_s"])
                                  for x in paired]
                    m, half = mean(reductions), 2.776445 * stdev(reductions) / math.sqrt(5)
                    value = f"{m:.2f}% [{m-half:.2f}%, {m+half:.2f}%]"
                else:
                    value = "存在失败，未计算五种子 CI"
                lines.append(f"| {scenario} | {condition} | {base} | " +
                             f"{sum(base in x and 'V4' in x for x in paired)}/5 | {value} |")
    lines += ["", "论文可用表述：在预先登记的长 Prompt、突发到达和输出长度变化下，"
              "RCAPS 相对两个基线的效果按条件、负载和失败率分别报告。"
              "只有两边均完成五个配对种子的条件才给出完整组统计和配对 95% CI；"
              "不能将一种扰动的结论推广为所有工作负载均稳健。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, registered_windows=len(rows),
          counts=dict(Counter(r["status"] for r in rows)),
          manifest_sha256=sha(directory / "manifest.json"),
          individual_sha256=sha(HERE / "individual.csv"),
          results_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(args.phase, args.worker)
    else:
        queue(args.phase, args.workers)


if __name__ == "__main__":
    main()

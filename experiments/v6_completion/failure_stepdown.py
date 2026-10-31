"""Registered lower-token boundary runs; original failed windows remain untouched."""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, paths, read, relative, sha, write
from experiments.v6_completion.campaign_queue import queue, worker
from experiments.v6_completion.failure_replay import category

HERE = Path(__file__).resolve().parent / "failure_stepdown"
MODULE = "experiments.v6_completion.failure_stepdown"
MODES = (
    ("70b_single_prompt2_rate350", "single", 2, 350),
    ("70b_multi_prompt2_rate160", "multi", 2, 160),
    ("70b_single_prompt3_rate350", "single", 3, 350),
    ("70b_multi_prompt3_rate160", "multi", 3, 160),
    ("30b_multi_rate630", "multi", 0, 630),
)
CELLS = ("HH", "HHplus", "V4")
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")


def trace70(scenario: str, prompt_scale: int, seed: int, duration: int):
    from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

    original_rate = 700 if scenario == "single" else 320
    base = OnlineRequestFeeder(original_rate, 0, duration, seed).trace
    factor = sum(prompt_scale * p + o for _, p, o in base) / sum(p + o for _, p, o in base)
    # Original long-prompt protocol preserves offered token/s. Double interarrival
    # time here to halve that rate while retaining each request's long prompt.
    return [(float(t * factor * 2), int(p * prompt_scale), int(o))
            for t, p, o in base if t * factor * 2 < duration]


def evaluate70(job: dict):
    from benchmarks.fixed_window import run
    from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    scenario, cell = job["scenario"], job["cell"]
    trace = trace70(scenario, job["prompt_scale"], job["seed"], job["duration"])
    assert trace and all(t >= 0 and p > 0 and o > 0 for t, p, o in trace)
    solution, cluster, physical = paths(scenario, cell)
    factory, delegate = None, None
    if cell == "HHplus":
        factory = HelixPlus
    elif cell == "V4":
        state = read(solution.parent / "placement.json")["state"]
        factory = lambda sim: AdmissionScheduler(sim, state=state, admission="sparse",
                                                  routing_state="live")
        delegate = MechanismProbe(PromptTransferChunkHook(4_194_304, scope="slow"))
    row = run(scenario, "helix" if cell == "HH" else "queue_dag",
              job["target_rate"], job["duration"], 0, job["seed"], solution, cluster,
              physical_cluster=physical, scheduler_factory=factory, compact=True,
              record_query_samples=True, profile_resources=True,
              phase_link_probe=SetupProbe(delegate=delegate), trace_override=trace)
    if cell == "V4":
        row.update(row["phase_link_profile"]["corrected_network_accounting"])
        row["network_accounting"] = "v4_chunk_aware_v1"
    row.update(cell=cell, condition=job["mode"], prompt_scale=job["prompt_scale"],
               trace_tokens_per_s=sum(p + o for _, p, o in trace) / job["duration"],
               solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
               gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) /
               row["output_throughput_tokens_per_s"])
    assert row["arrivals"] == len(trace)
    return row


def evaluate(job: dict):
    if job["model"] == "70B":
        return evaluate70(job)
    from experiments.v5_model30b.run import evaluate as rcaps30
    from experiments.v5_model30b_pools.run import evaluate as pooled30

    method = rcaps30 if job["cell"] == "V4" else pooled30
    row = method("multi", job["target_rate"], job["seed"], job["cell"], job["duration"])
    row.update(condition=job["mode"])
    return row


def register(phase: str, workers: int):
    assert phase in ("smoke", "formal")
    destination = HERE / phase / "manifest.json"
    if destination.exists():
        manifest = read(destination)
        check(manifest)
        return manifest

    original70 = read(ROOT / "experiments/v6_completion/generalization/formal/index.json")
    original30 = read(ROOT / "experiments/v5_model30b/formal/index.json")
    assert original70["status"] == original30["status"] == "terminal"
    assert all(original70["jobs"][f"{s}/{condition}/{cell}/seed{seed}"]["status"] == "failed"
               for s in ("single", "multi") for condition in ("prompt2", "prompt4")
               for cell in CELLS for seed in range(5))
    assert all(original30["jobs"][f"multi/load840/V4/seed{seed}"]["status"] == "failed"
               for seed in range(5))

    sources = {}
    for campaign in ("v5_core_supplement", "v5_model30b_pools", "v5_model30b"):
        original = read(ROOT / "experiments" / campaign / "formal/manifest.json")
        for path, digest in original["sources_sha256"].items():
            assert path not in sources or sources[path] == digest
            sources[path] = digest
    for path in (Path(__file__),
                 ROOT / "experiments/v6_completion/generalization.py",
                 ROOT / "experiments/v6_completion/campaign_queue.py",
                 ROOT / "experiments/v6_completion/failure_replay.py"):
        sources[relative(path)] = sha(path)
    check({"sources_sha256": sources})
    duration, seeds = (60, (100,)) if phase == "smoke" else (1800, tuple(range(5)))
    jobs = [dict(key=f"{mode}/{cell}/seed{seed}", mode=mode, model="30B" if scale == 0 else "70B",
                 scenario=scenario, prompt_scale=scale, target_rate=rate, cell=cell,
                 seed=seed, duration=duration)
            for mode, scenario, scale, rate in MODES for seed in seeds for cell in CELLS]
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs, worker_limit=workers,
                    timeout_wall_s=14400, sources_sha256=sources,
                    original70_index_sha256=sha(ROOT / "experiments/v6_completion/generalization/formal/index.json"),
                    original30_index_sha256=sha(ROOT / "experiments/v5_model30b/formal/index.json"),
                    protocol="60s smoke or 1800s formal, zero warmup, no drain, seeds 0..4",
                    decision="Fixed lower-token grid before observing these follow-up outcomes",
                    conditions={mode: dict(model="30B" if scale == 0 else "70B", scenario=scenario,
                                           prompt_scale=scale, target_offered_tokens_per_s=rate)
                                for mode, scenario, scale, rate in MODES},
                    failure_policy="One attempt per key; keep original failures and follow-up failures; no imputation",
                    environment=dict(executable=__import__("sys").executable, env=ENV))
    write(destination, manifest)
    return manifest


def report():
    folder = HERE / "formal"
    manifest, index = read(folder / "manifest.json"), read(folder / "index.json")
    assert index["status"] == "terminal"
    check(manifest)
    rows = []
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        artifact = ROOT / entry["source"]
        assert sha(artifact) == entry["artifact_sha256"]
        result = read(artifact)
        assert result["status"] == entry["status"]
        rows.append(dict(job=job, status=entry["status"], cause=category(result),
                         result=result, source=entry["source"], sha256=entry["artifact_sha256"]))
    successful = defaultdict(dict)
    for item in rows:
        if item["status"] == "completed":
            job = item["job"]
            successful[(job["mode"], job["seed"])][job["cell"]] = item["result"]
    for methods in successful.values():
        assert len({row["trace_sha256"] for row in methods.values()}) == 1
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=("mode", "cell", "seed", "status", "cause",
                                                  *METRICS, "trace_sha256", "source", "sha256"))
        writer.writeheader()
        for item in rows:
            job, result = item["job"], item["result"]
            writer.writerow(dict(mode=job["mode"], cell=job["cell"], seed=job["seed"],
                                 status=item["status"], cause=item["cause"],
                                 **{key: result.get(key) for key in METRICS},
                                 trace_sha256=result.get("trace_sha256"),
                                 source=item["source"], sha256=item["sha256"]))
    lines = ["# 降 token 边界补测", "",
             "原失败条件保持不变；下表是事先登记的不同负载/Prompt 长度条件，不能替代原失败。",
             "每个方法五种子，1800 s 固定窗口、零预热、不排空。失败不填零。", "",
             "| 条件 | 方法 | 成功 | P95 TPOT s | P95 TTFT s | 输出 token/s | 完成率 | GPU 秒/token |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for mode, _, _, _ in MODES:
        for cell in CELLS:
            subset = [item["result"] for item in rows
                      if item["job"]["mode"] == mode and item["job"]["cell"] == cell
                      and item["status"] == "completed"]
            values = []
            for metric in METRICS:
                if len(subset) == 5:
                    column = [row[metric] for row in subset]
                    values.append(f"{mean(column):.4f} ± {stdev(column):.4f}")
                else:
                    values.append("未汇总")
            lines.append(f"| {mode} | {cell} | {len(subset)}/5 | " + " | ".join(values) + " |")
    lines += ["", "## 失败原因", ""]
    for (mode, cell, cause), count in sorted(Counter(
            (item["job"]["mode"], item["job"]["cell"], item["cause"])
            for item in rows if item["status"] == "failed").items()):
        lines.append(f"- {mode}/{cell}: {cause} × {count}")
    lines += ["", "结果仅为模拟器条件边界。完成与否本身是结果；没有五种子成功组时不计算配对 CI。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, windows=len(rows),
          counts=dict(Counter(item["status"] for item in rows)),
          manifest_sha256=sha(folder / "manifest.json"),
          individual_sha256=sha(HERE / "individual.csv"),
          results_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, evaluate)
    else:
        queue(HERE, MODULE, args.phase, args.workers, register, report)


if __name__ == "__main__":
    main()

"""P1-3 live-session pricing variants on the frozen RCAPS V4 placement.

No production scheduler or existing formal artifact is modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, paths, read, relative, sha, write

HERE = Path(__file__).resolve().parent / "session_cost"
LOADS = {"single": 700, "multi": 320}
VARIANTS = ("batch", "marginal", "cycle", "no_session", "k1", "k1_5", "k3", "k4")
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")


def scheduler_for(variant):
    from rcaps.v3.queue_cost import SingleTokenQueueCostScheduler, WorkloadQueueDagScheduler
    from rcaps.v4.admission import AdmissionScheduler
    from simulator.event_simulator.request import RequestPhase

    if variant == "no_session":
        return AdmissionScheduler, "no_session"
    if variant == "batch":
        class Batch(AdmissionScheduler):
            def _decode_token_service(self, node, first, end, active_sessions):
                return WorkloadQueueDagScheduler._decode_token_service(
                    self, node, first, end, active_sessions)
        return Batch, "live"
    if variant == "cycle":
        class Cycle(AdmissionScheduler):
            def _decode_token_service(self, node, first, end, active_sessions):
                resident = sorted(node.in_vram_model_layers)
                return AdmissionScheduler._decode_token_service(
                    self, node, resident[0], resident[-1] + 1, active_sessions)
        return Cycle, "live"
    if variant == "marginal":
        class Marginal(AdmissionScheduler):
            def _decode_token_service(self, node, first, end, active_sessions):
                if active_sessions <= 0:
                    return 0.0
                limit = max(1, node.inference_settings.decode_max_tokens)
                current = min(active_sessions, limit)
                added = min(active_sessions + 1, limit)
                if added == current:
                    # Beyond the profiled batch ceiling, retain its last
                    # measured increment instead of assigning zero cost.
                    current, added = max(1, limit - 1), limit
                delta = sum(self._layer_service(node, layer, RequestPhase.Increment, added) -
                            self._layer_service(node, layer, RequestPhase.Increment, current)
                            for layer in range(first, end))
                return max(0.0, delta) / active_sessions
        return Marginal, "live"
    multiplier = {"k1": 1., "k1_5": 1.5, "k3": 3., "k4": 4.}[variant]
    class Kappa(AdmissionScheduler):
        def _decode_token_service(self, node, first, end, active_sessions):
            return multiplier * SingleTokenQueueCostScheduler._decode_token_service(
                self, node, first, end, active_sessions)
    return Kappa, "live"


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v5_core_supplement.adapters import SetupProbe
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    solution, cluster, physical = paths(job["scenario"], "V4")
    state = read(solution.parent / "placement.json")["state"]
    scheduler, routing_state = scheduler_for(job["variant"])
    factory = lambda sim: scheduler(sim, state=state, admission="sparse", routing_state=routing_state)
    row = run(job["scenario"], "queue_dag", job["load"], job["duration"], 0,
              job["seed"], solution, cluster, physical_cluster=physical,
              scheduler_factory=factory, compact=True, record_query_samples=True,
              profile_resources=True,
              phase_link_probe=SetupProbe(delegate=MechanismProbe(
                  PromptTransferChunkHook(4_194_304, scope="slow"))))
    row.update(row["phase_link_profile"]["corrected_network_accounting"])
    row.update(variant=job["variant"], cell="V4_" + job["variant"],
               solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
               network_accounting="v4_chunk_aware_v1",
               gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) /
               row["output_throughput_tokens_per_s"])
    assert len(row["query_samples"]) == row["arrivals"]
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
        for scenario in LOADS:
            assert any(key.startswith(scenario + "/") and entry["status"] == "completed"
                       for key, entry in smoke["jobs"].items())
    duration = 60 if phase == "smoke" else 1800
    seeds = (100,) if phase == "smoke" else tuple(range(5))
    variants = ("batch", "marginal", "no_session", "k1", "k4") if phase == "smoke" else VARIANTS
    jobs = [dict(key=f"{scenario}/{variant}/seed{seed}", scenario=scenario, load=load,
                 variant=variant, seed=seed, duration=duration)
            for scenario, load in LOADS.items() for variant in variants for seed in seeds]
    sources = dict(read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")["sources_sha256"])
    sources[relative(Path(__file__))] = sha(Path(__file__))
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs, sources_sha256=sources,
                    worker_limit=workers, timeout_wall_s=14400, loads=LOADS,
                    variants=variants, seeds=seeds, duration_s=duration,
                    protocol="fixed_window_no_tail_drain", placement="frozen RCAPS V4",
                    kappa={"k1": 1, "k1_5": 1.5, "default": 2, "k3": 3, "k4": 4},
                    marginal="Increment g(m+1)-g(m) of per-layer decode batch profile; routings original sessions*service interface receives delta/m; beyond profile batch ceiling use last observed increment",
                    failure_policy="One attempt per predeclared key; preserve actual failure without imputation",
                    environment=dict(executable=sys.executable, env=ENV))
    write(target, manifest)
    return manifest


def worker(phase, key):
    manifest = read(HERE / phase / "manifest.json")
    job = next(j for j in manifest["jobs"] if j["key"] == key)
    directory = HERE / phase / "runs" / key
    start = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job)
        check(manifest)
        row.update(status="completed", job=job, manifest_sha256=sha(HERE / phase / "manifest.json"),
                   elapsed_wall_s=time.perf_counter() - start, finished_at=now())
        write(directory / "result.json", row)
    except BaseException as error:
        write(directory / "failure.json", dict(status="failed", job=job, error=repr(error),
              traceback=traceback.format_exc(), manifest_sha256=sha(HERE / phase / "manifest.json"),
              elapsed_wall_s=time.perf_counter() - start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase, workers):
    manifest = register(phase, workers)
    directory = HERE / phase
    index_path = directory / "index.json"
    if index_path.exists():
        index = read(index_path)
        assert index["manifest_sha256"] == sha(directory / "manifest.json")
        assert not any(x["status"] == "running" for x in index["jobs"].values())
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
                                        "experiments.v6_completion.session_cost", "--phase", phase,
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
        rows.append({**{k: job[k] for k in ("scenario", "load", "variant", "seed")},
                     "status": entry["status"], "source": entry["source"],
                     "artifact_sha256": entry["artifact_sha256"], "error": outcome.get("error", ""),
                     "trace_sha256": outcome.get("trace_sha256", ""),
                     **{k: outcome.get(k) for k in METRICS}})
        if entry["status"] == "completed":
            assert len(outcome["query_samples"]) == outcome["arrivals"]
            groups[(job["scenario"], job["seed"])][job["variant"]] = outcome
    for scenario in LOADS:
        registry = read(ROOT / "experiments/v5_core_supplement/formal/index.json")
        for seed in range(5):
            for cell in ("HH", "HHplus", "V4"):
                entry = registry["jobs"][f"{scenario}/load{LOADS[scenario]}/{cell}/seed{seed}"]
                assert entry["status"] in ("completed", "reused")
                artifact = ROOT / entry["source"]
                assert sha(artifact) == entry["artifact_sha256"]
                groups[(scenario, seed)][cell] = read(artifact)
        for seed in range(5):
            group = groups[(scenario, seed)]
            assert len({r["trace_sha256"] for r in group.values()}) == 1
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 会话代价变体（P1-3）", "",
             "70B 固定窗口、V4 放置和执行规则、五种子。default/Helix/Helix+ 直接引用已审计的 V5 核心结果；新变体独立登记。",
             "边际代价为相邻 decode 批量画像的增量；超过画像上限时沿用最后观测增量。",
             "下表只在成功五种子时汇总；失败保留在 individual.csv。", "",
             "| 拓扑 | 变体 | 成功 | P95 TPOT(s) | P95 TTFT(s) | 输出 token/s | 完成率 | GPU 秒/token |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for scenario in LOADS:
        for variant in ("HH", "HHplus", "V4", *VARIANTS):
            selected = [groups[(scenario, seed)].get(variant) for seed in range(5)]
            valid = [r for r in selected if r is not None]
            vals = [f"{mean(r[k] for r in valid):.4f} ± {stdev(r[k] for r in valid):.4f}"
                    if len(valid) == 5 else "未汇总" for k in METRICS]
            lines.append(f"| {scenario} | {variant} | {len(valid)}/5 | " + " | ".join(vals) + " |")
    lines += ["", "| 拓扑 | 变体 | 配对五种子 TPOT 相对 Helix+ 降幅 [95% CI] |",
              "|---|---|---:|"]
    for scenario in LOADS:
        for variant in ("V4", *VARIANTS):
            paired = [groups[(scenario, seed)] for seed in range(5)]
            if all(variant in x for x in paired):
                values = [100 * (1 - x[variant]["tpot_p95_s"] / x["HHplus"]["tpot_p95_s"])
                          for x in paired]
                m = mean(values)
                h = 2.776445 * stdev(values) / math.sqrt(5)
                value = f"{m:.2f}% [{m-h:.2f}%, {m+h:.2f}%]"
            else:
                value = "存在失败，未汇总"
            lines.append(f"| {scenario} | {variant} | {value} |")
    lines += ["", "论文可用表述：会话代价模型会改变放置固定条件下的路由选择。"
              "各变体的尾延迟与 GPU 秒/token 应共同报告，只有完整五种子配对的条件才支持统计比较。"
              "本批尚不含跨负载 SLO goodput 容量扫描，不能声称容量结论。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, registered_windows=len(rows),
          counts=dict(Counter(r["status"] for r in rows)),
          manifest_sha256=sha(directory / "manifest.json"),
          individual_sha256=sha(HERE / "individual.csv"),
          results_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=8)
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

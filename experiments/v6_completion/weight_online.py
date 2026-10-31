"""P1-6 five-seed online evaluation of preregistered weight-search layouts."""
from __future__ import annotations

import argparse
import csv
import math
import os
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, relative, sha, write
from experiments.v6_completion.weight_search import CASES, SETTINGS, files

HERE = Path(__file__).resolve().parent / "weight_online"
LAYOUTS = ROOT / "experiments/v6_completion/weight_search/runs"
LOADS = {"C1_single": 700, "C1_multi": 320}
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v5_core_supplement.adapters import SetupProbe
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    folder = LAYOUTS / job["case"] / job["label"]
    physical, _, scenario = files(job["case"])
    state = read(folder / "placement.json")["state"]
    factory = lambda sim: AdmissionScheduler(sim, state=state, admission="sparse", routing_state="live")
    row = run(scenario, "queue_dag", job["load"], job["duration"], 0, job["seed"],
              folder / "solution.ini", folder / "simulator_cluster.ini",
              physical_cluster=physical, scheduler_factory=factory,
              compact=True, record_query_samples=True, profile_resources=True,
              phase_link_probe=SetupProbe(delegate=MechanismProbe(
                  PromptTransferChunkHook(4_194_304, scope="slow"))))
    row.update(row["phase_link_profile"]["corrected_network_accounting"])
    row.update(label=job["label"], cell="V4", case=job["case"],
               network_accounting="v4_chunk_aware_v1",
               solution_sha256=sha(folder / "solution.ini"),
               sim_cluster_sha256=sha(folder / "simulator_cluster.ini"),
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
        assert smoke["status"] == "terminal" and all(
            entry["status"] == "completed" for entry in smoke["jobs"].values())
    offline = read(ROOT / "experiments/v6_completion/weight_search/FINAL_AUDIT.json")
    assert offline["passed"] and offline["jobs"] == len(CASES) * len(SETTINGS)
    duration = 60 if phase == "smoke" else 1800
    seeds = (100,) if phase == "smoke" else tuple(range(5))
    labels = ("w0_low", "w2_high") if phase == "smoke" else SETTINGS
    jobs = [dict(key=f"{case}/{label}/seed{seed}", case=case,
                 label=label, scenario="single" if case == "C1_single" else "multi",
                 load=LOADS[case], seed=seed, duration=duration)
            for case in CASES for label in labels for seed in seeds]
    sources = dict(read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")["sources_sha256"])
    sources[relative(Path(__file__))] = sha(Path(__file__))
    sources["experiments/v6_completion/weight_search.py"] = sha(
        ROOT / "experiments/v6_completion/weight_search.py")
    sources["experiments/v6_completion/weight_search/manifest.json"] = sha(
        ROOT / "experiments/v6_completion/weight_search/manifest.json")
    sources["experiments/v6_completion/weight_search/FINAL_AUDIT.json"] = sha(
        ROOT / "experiments/v6_completion/weight_search/FINAL_AUDIT.json")
    for case in CASES:
        for label in labels:
            folder = LAYOUTS / case / label
            for name in ("solution.ini", "simulator_cluster.ini", "placement.json"):
                sources[relative(folder / name)] = sha(folder / name)
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
                    sources_sha256=sources, worker_limit=workers, timeout_wall_s=14400,
                    labels=labels, seeds=seeds, duration_s=duration,
                    protocol="fixed_window_no_tail_drain",
                    scope="Five-seed online metrics on six varied-weight placements, two high-load topologies; frozen V4 online scheduler and chunking",
                    failure_policy="One attempt per key; preserve failures without imputation",
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
        row.update(status="completed", job=job,
                   manifest_sha256=sha(HERE / phase / "manifest.json"),
                   elapsed_wall_s=time.perf_counter() - start, finished_at=now())
        write(directory / "result.json", row)
    except BaseException as error:
        write(directory / "failure.json", dict(status="failed", job=job,
              error=repr(error), traceback=traceback.format_exc(),
              manifest_sha256=sha(HERE / phase / "manifest.json"),
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
        assert not any(entry["status"] == "running" for entry in index["jobs"].values())
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
            folder = directory / "runs" / job["key"]
            folder.mkdir(parents=True, exist_ok=False)
            log = (folder / "worker.log").open("x", encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-u", "-X", "faulthandler", "-m",
                                        "experiments.v6_completion.weight_online", "--phase", phase,
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
            folder = directory / "runs" / key
            passed = code == 0 and (folder / "result.json").exists()
            artifact = folder / ("result.json" if passed else "failure.json")
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
    baseline = read(ROOT / "experiments/v5_core_supplement/formal/index.json")
    for case in CASES:
        scenario = "single" if case == "C1_single" else "multi"
        for seed in range(5):
            entry = baseline["jobs"][f"{scenario}/load{LOADS[case]}/V4/seed{seed}"]
            assert entry["status"] in ("completed", "reused")
            source = ROOT / entry["source"]
            assert sha(source) == entry["artifact_sha256"]
            groups[(case, seed)]["default"] = read(source)
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        assert entry["status"] in ("completed", "failed")
        source = ROOT / entry["source"]
        assert sha(source) == entry["artifact_sha256"]
        outcome = read(source)
        rows.append({**{k: job[k] for k in ("case", "scenario", "load", "label", "seed")},
                     "status": entry["status"], "source": entry["source"],
                     "error": outcome.get("error", ""),
                     "artifact_sha256": entry["artifact_sha256"],
                     "trace_sha256": outcome.get("trace_sha256", ""),
                     **{k: outcome.get(k) for k in METRICS}})
        if entry["status"] == "completed":
            assert len(outcome["query_samples"]) == outcome["arrivals"]
            groups[(job["case"], job["seed"])][job["label"]] = outcome
    for group in groups.values():
        assert len({r["trace_sha256"] for r in group.values()}) == 1
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 权重敏感性：在线五种子", "",
             "六种放置权重变体及其部署见 ../weight_search/RESULTS_CN.md；在线 V4 调度器和负载协议相同。",
             "默认权重基线复用已审计的核心 V5 结果。失败不填零，五种子不齐则不汇总。", "",
             "| 拓扑 | 权重变体 | 成功 | P95 TPOT(s) | P95 TTFT(s) | 输出 token/s | 完成率 | GPU 秒/token |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for case in CASES:
        for label in ("default", *SETTINGS):
            values = [groups[(case, seed)].get(label) for seed in range(5)]
            valid = [r for r in values if r is not None]
            cells = [f"{mean(r[k] for r in valid):.4f} ± {stdev(r[k] for r in valid):.4f}"
                     if len(valid) == 5 else "未汇总" for k in METRICS]
            lines.append(f"| {case} | {label} | {len(valid)}/5 | " + " | ".join(cells) + " |")
    lines += ["", "| 拓扑 | 权重变体 | 相对默认 TPOT 变化 [95% CI] |", "|---|---|---:|"]
    for case in CASES:
        for label in SETTINGS:
            values = [groups[(case, seed)] for seed in range(5)]
            if all(label in r for r in values):
                deltas = [100 * (r[label]["tpot_p95_s"] / r["default"]["tpot_p95_s"] - 1)
                          for r in values]
                m, h = mean(deltas), 2.776445 * stdev(deltas) / math.sqrt(5)
                cell = f"{m:.2f}% [{m-h:.2f}%, {m+h:.2f}%]"
            else:
                cell = "存在失败，未汇总"
            lines.append(f"| {case} | {label} | {cell} |")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, jobs=len(rows),
          counts=dict(Counter(row["status"] for row in rows)),
          manifest_sha256=sha(directory / "manifest.json"),
          individual_sha256=sha(HERE / "individual.csv"),
          report_sha256=sha(HERE / "RESULTS_CN.md")))


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

"""P1-6 paired network-bandwidth and admission/chunk-threshold sweep."""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.adapters import SetupProbe
from experiments.v5_core_supplement.run import ENV, ROOT, check, now, paths, read, sha, write
from experiments.v6_completion.campaign_queue import queue, worker

HERE = Path(__file__).resolve().parent / "bandwidth_threshold"
CONDITIONS = ((12.5, 50), (25, 50), (50, 25), (50, 50),
              (50, 100), (100, 50), (200, 50))
CELLS = ("sparse_chunk", "sparse_nochunk", "canonical_chunk", "canonical_nochunk")
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")


def condition_name(bandwidth, threshold):
    return f"B{str(bandwidth).replace('.', 'p')}_T{threshold}"


class NetworkProbe(SetupProbe):
    def __init__(self, target_mbps, delegate):
        super().__init__(delegate=delegate)
        self.target_mbps = target_mbps

    def install(self, simulator, beginning, ending):
        # The exported fixed placement uses a heterogeneous 12.5 MB/s mean
        # cross-region link. Scale only inter-compute links with WAN latency.
        ratio = self.target_mbps / 12.5
        changes = []
        for link in simulator.links.values():
            if (link.node_in_type.name == "Compute" and
                    link.node_out_type.name == "Compute" and
                    link.latency >= 0.02 and link.bandwidth < 25_000_000):
                assert link.available_bandwidth == link.bandwidth
                old = link.bandwidth
                link.bandwidth *= ratio
                link.available_bandwidth *= ratio
                changes.append(dict(uid=link.link_uid, before_Bps=old,
                                    after_Bps=link.bandwidth))
        assert changes, "No exported cross-region compute links selected"
        self.changes = changes
        super().install(simulator, beginning, ending)

    def summary(self, samples):
        result = super().summary(samples)
        result["network_intervention"] = dict(
            target_nominal_MBps=self.target_mbps, modified_links=self.changes,
            policy="scale original heterogeneous WAN links by target/12.5; keep NIC and propagation latency fixed")
        result["admission"] = self.simulator.scheduler.summary()
        return result


def evaluate(job):
    from benchmarks.fixed_window import run
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    solution, cluster, physical = paths("multi", "V4")
    state = read(solution.parent / "placement.json")["state"]
    admission = "sparse" if job["cell"].startswith("sparse") else "canonical"
    threshold = int(job["threshold_MBps"] * 1_000_000)
    factory = lambda sim: AdmissionScheduler(sim, state=state, admission=admission,
                                              threshold=threshold, routing_state="live")
    hook = (PromptTransferChunkHook(4_194_304, threshold_Bps=threshold, scope="slow")
            if job["cell"].endswith("_chunk") else None)
    probe = NetworkProbe(job["bandwidth_MBps"], MechanismProbe(hook))
    row = run("multi", "queue_dag", job["load"], job["duration"], 0,
              job["seed"], solution, cluster, physical_cluster=physical,
              scheduler_factory=factory, compact=True, record_query_samples=True,
              profile_resources=True, phase_link_probe=probe)
    profile = row["phase_link_profile"]
    row.update(profile["corrected_network_accounting"])
    row.update(condition=job["condition"], cell=job["cell"],
               network_accounting="v4_chunk_aware_v1", solution_sha256=sha(solution),
               sim_cluster_sha256=sha(cluster),
               gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) /
               row["output_throughput_tokens_per_s"],
               admission_edge_count=profile["admission"]["allowed_edge_count"],
               full_edge_count=profile["admission"]["full_edge_count"],
               canonical_edge_count=profile["admission"]["canonical_edge_count"],
               eligible_chunk_links=len(profile.get("chunking", {}).get("eligible_link_uids", [])),
               paused_chunks=profile.get("chunking", {}).get("paused_chunks", 0))
    return row


def register(phase, workers):
    path = HERE / phase / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    if phase == "formal":
        smoke = read(HERE / "smoke/index.json")
        assert smoke["status"] == "terminal"
        assert all(x["status"] == "completed" for x in smoke["jobs"].values())
    conditions = ((12.5, 50), (50, 50), (200, 50)) if phase == "smoke" else CONDITIONS
    cells = ("sparse_chunk", "canonical_nochunk") if phase == "smoke" else CELLS
    seeds = (100,) if phase == "smoke" else tuple(range(5))
    jobs = [dict(key=f"{condition_name(b, t)}/{cell}/seed{seed}",
                 condition=condition_name(b, t), bandwidth_MBps=b,
                 threshold_MBps=t, cell=cell, seed=seed, load=320,
                 duration=60 if phase == "smoke" else 1800)
            for b, t in conditions for cell in cells for seed in seeds]
    core = read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")
    sources = dict(core["sources_sha256"])
    for name in ("experiments/v6_completion/bandwidth_threshold.py",
                 "experiments/v6_completion/campaign_queue.py"):
        sources[name] = sha(ROOT / name)
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
        sources_sha256=sources, worker_limit=workers, timeout_wall_s=14400,
        conditions=conditions, cells=cells, seeds=seeds, load=320,
        physical_intervention="WAN inter-compute links with latency >=20ms and original capacity <25MB/s scaled by target/12.5; NIC and latency fixed",
        threshold_intervention="same threshold for sparse admission detours and 4MiB Prompt transfer chunks",
        design="2x2 admission sparse/canonical by transfer chunk/no-chunk within each bandwidth-threshold point",
        failure_policy="One attempt per key; preserve failures, no imputation",
        environment=dict(executable=sys.executable, env=ENV))
    write(path, manifest)
    return manifest


def report():
    folder = HERE / "formal"
    manifest, index = read(folder / "manifest.json"), read(folder / "index.json")
    assert index["status"] == "terminal"
    rows, groups = [], defaultdict(dict)
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        assert entry["status"] in ("completed", "failed")
        source = ROOT / entry["source"]
        assert sha(source) == entry["artifact_sha256"]
        outcome = read(source)
        row = dict(condition=job["condition"], bandwidth_MBps=job["bandwidth_MBps"],
                   threshold_MBps=job["threshold_MBps"], cell=job["cell"],
                   seed=job["seed"], status=entry["status"], source=entry["source"],
                   source_sha256=entry["artifact_sha256"],
                   trace_sha256=outcome.get("trace_sha256", ""),
                   admission_edge_count=outcome.get("admission_edge_count"),
                   eligible_chunk_links=outcome.get("eligible_chunk_links"),
                   paused_chunks=outcome.get("paused_chunks"),
                   error=outcome.get("error", ""),
                   **{key: outcome.get(key) for key in METRICS})
        rows.append(row)
        if entry["status"] == "completed":
            assert len(outcome["query_samples"]) == outcome["arrivals"]
            groups[job["condition"], job["seed"]][job["cell"]] = outcome
    assert all(len({x["trace_sha256"] for x in group.values()}) == 1
               for group in groups.values())
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 跨区带宽与阈值敏感性（P1-6）", "",
        "70B 三集群高负载 320 token/s，五种子；每点采用稀疏/规范准入 × 传输分块/不分块的 2×2 设计。",
        "带宽列是原导出跨区计算链路的名义均值缩放目标，保留原异质性；NIC 和传播时延固定。",
        "所有结果来自 CPU 离散事件模拟。成功数不足五时不汇总；失败不填零。", "",
        "| 带宽 MB/s | 阈值 MB/s | 处理 | 成功 | P95 TPOT(s) | P95 TTFT(s) | 完成率 | 允许边数 | 分块链路 | 暂停块数 |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for b, t in CONDITIONS:
        name = condition_name(b, t)
        for cell in CELLS:
            subset = [r for r in rows if r["condition"] == name and r["cell"] == cell
                      and r["status"] == "completed"]
            vals = [f"{mean(r[k] for r in subset):.3f}" if len(subset) == 5 else "未汇总"
                    for k in ("tpot_p95_s", "ttft_p95_s", "completion_fraction",
                              "admission_edge_count", "eligible_chunk_links", "paused_chunks")]
            lines.append(f"| {b} | {t} | {cell} | {len(subset)}/5 | " + " | ".join(vals) + " |")
    lines += ["", "每点同种子配对详见 individual.csv；可由 2×2 结构分别估计准入、分块及交互作用。",
              "只可解释模拟器中的固定放置与静态链路容量，不可外推到真实网络。"]
    (HERE / "RESULTS_CN.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, jobs=len(rows),
          counts=dict(Counter(row["status"] for row in rows)),
          manifest_sha256=sha(folder / "manifest.json"),
          csv_sha256=sha(HERE / "individual.csv"),
          report_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, evaluate)
    else:
        queue(HERE, "experiments.v6_completion.bandwidth_threshold", args.phase,
              args.workers, register, report)


if __name__ == "__main__":
    main()

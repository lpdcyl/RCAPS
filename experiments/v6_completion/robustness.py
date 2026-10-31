"""P1-1 five-seed simulator-input uncertainty experiments."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import math
import random
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from statistics import mean, stdev
import sys

from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
from experiments.v5_core_supplement.run import ENV, ROOT, check, now, paths, read, relative, sha, write
from experiments.v6_completion.campaign_queue import queue, worker

HERE = Path(__file__).resolve().parent / "robustness"
LOADS = {"single": 700, "multi": 320}
CONDITIONS = ("profile10", "profile20", "bandwidth20", "bandwidth50",
              "latency20", "activation_kv_low20", "activation_kv_high20",
              "singleton1", "boundary50ms")
CELLS = ("HH", "HHplus", "V4")
METRICS = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
           "completion_fraction", "gpu_seconds_per_output_token")


def seeded(seed, *values):
    payload = "|".join(map(str, (seed, *values))).encode()
    return random.Random(int.from_bytes(hashlib.sha256(payload).digest()[:8], "big"))


class PerturbationProbe(SetupProbe):
    def __init__(self, condition, seed, delegate):
        super().__init__(delegate=delegate)
        self.condition, self.seed = condition, seed
        self.changes = {}

    def install(self, simulator, beginning, ending):
        # The baselines and RCAPS all initialize on the nominal physical
        # placement. The intervention changes runtime resources after setup.
        super().install(simulator, beginning, ending)
        condition = self.condition
        if condition.startswith("profile"):
            bound = int(condition.removeprefix("profile")) / 100
            count = 0
            for uid, node in simulator.compute_nodes.items():
                for layer_id, layer in list(node.in_vram_model_layers.items()):
                    changed = copy.copy(layer)
                    for phase in ("prompt", "decode"):
                        field = phase + "_bs2time"
                        points = getattr(layer, field)
                        adjusted = {}
                        for batch, value in points.items():
                            rng = seeded(self.seed, uid, layer_id, phase, batch)
                            factor = math.exp(max(math.log(1 - bound), min(math.log(1 + bound),
                                               rng.gauss(0, bound / 2))))
                            adjusted[batch] = value * factor
                            count += 1
                        setattr(changed, field, adjusted)
                    node.in_vram_model_layers[layer_id] = changed
            self.changes = dict(kind="profile_lognormal_truncated", bound=bound,
                                points_changed=count, same_factor_key="seed/GPU/layer/phase/batch")
        elif condition.startswith("activation_kv"):
            scale = 0.8 if condition.endswith("low20") else 1.2
            simulator.model_manager.model_statistics.activation_size *= scale
            simulator.query_manager.param.token_activation_size *= scale
            if hasattr(simulator.scheduler, "flow_graph"):
                simulator.scheduler.flow_graph.parameters.token_activation_size *= scale
            before = {}
            for uid, node in simulator.compute_nodes.items():
                old = node.kv_cache_capacity
                new = int(old / scale)
                assert new > 0
                cache = node.kv_cache
                if cache is not None:
                    assert cache.available_capacity == cache.max_capacity == old
                    assert all(not layer for layer in cache.kv_cache.values())
                    cache.available_capacity = cache.max_capacity = new
                node.kv_cache_capacity = new
                before[str(uid)] = (old, new)
            self.changes = dict(kind="activation_and_kv_size", scale=scale,
                                kv_capacity_token_equivalent=before)
        elif condition.startswith("bandwidth") or condition.startswith("latency"):
            from simulator.event_simulator.event import EventHandler
            bound = int(condition[-2:]) / 100
            kind = "bandwidth" if condition.startswith("bandwidth") else "latency"
            links = [link for link in simulator.links.values()
                     if link.node_in_type.name == "Compute" and
                     link.node_out_type.name == "Compute" and
                     (kind == "latency" or link.bandwidth <= 50_000_000)]
            originals = {link.link_uid: (link.bandwidth, link.latency) for link in links}
            start = simulator.current_time
            factors = {}
            def apply(bucket):
                for link in links:
                    _, base_delay = originals[link.link_uid]
                    rng = seeded(self.seed, kind, link.link_uid, bucket)
                    factor = rng.uniform(1 - bound, 1 + bound)
                    if kind == "bandwidth":
                        factors[link.link_uid] = factor
                    else:
                        link.latency = base_delay * factor
            apply(0)
            if kind == "bandwidth":
                # Keep reservation capacities nominal so a precomputed Helix
                # share remains schedulable. Perturb the physical serialization
                # duration of every send, including resumed V4 Prompt chunks.
                original_put = simulator.event_queue.put
                selected = set(originals)
                def put(item, *args, **kwargs):
                    _, event = item
                    if event.event_handler == EventHandler.FinishSending:
                        uid = event.args["link_uid"]
                        if uid in selected:
                            old_end = event.event_time
                            new_end = simulator.current_time + (
                                old_end - simulator.current_time) / factors[uid]
                            assert new_end >= simulator.current_time
                            event.event_time = new_end
                            event.args["send_end_time"] = new_end
                            event.description.at_when = new_end
                            item = (new_end, event)
                    return original_put(item, *args, **kwargs)
                simulator.event_queue.put = put
            original_simulate = simulator.simulate
            next_bucket = [1]
            def simulate(*args, **kwargs):
                until = kwargs.get("until", args[0] if args else None)
                if until is not None:
                    while start + next_bucket[0] * 30 < until:
                        original_simulate(until=start + next_bucket[0] * 30)
                        apply(next_bucket[0])
                        next_bucket[0] += 1
                return original_simulate(*args, **kwargs)
            simulator.simulate = simulate
            self.changes = dict(kind=kind, bound=bound, interval_s=30,
                                affected_links=len(links), seeded_per_link_interval=True,
                                active_transfer_finish_time="booked at transmission start; not rescheduled mid-send",
                                bandwidth_semantics="physical send duration changes; scheduler reservations and route estimates remain nominal" if kind == "bandwidth" else None)
        elif condition == "singleton1":
            self.changes = dict(kind="singleton_decode_runtime", multiplier=1,
                                rcaps_kappa=1)
        elif condition == "boundary50ms":
            self.changes = dict(kind="intermediate_chunk_boundary_hold", seconds=0.05,
                                measured_hardware_cost=False)
        else:
            raise ValueError(condition)

    def summary(self, samples):
        result = super().summary(samples)
        result["perturbation"] = self.changes
        return result


@contextmanager
def singleton_runtime(condition):
    from simulator.event_simulator.model import ModelLayer
    from simulator.event_simulator.request import RequestPhase
    original = ModelLayer.get_inference_statistics
    if condition == "singleton1":
        def statistics(layer, requests):
            seconds, vram = original(layer, requests)
            decodes = sum(r.token_seq_length for r in requests if r.phase == RequestPhase.Increment)
            if decodes == 1:
                seconds -= layer.get_decode_inference_time(1)
            return seconds, vram
        ModelLayer.get_inference_statistics = statistics
    try:
        yield
    finally:
        ModelLayer.get_inference_statistics = original


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v4_core_validation.core import BoundaryCostHook
    from rcaps.v3.queue_cost import SingleTokenQueueCostScheduler
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    scenario, condition, cell = job["scenario"], job["condition"], job["cell"]
    solution, cluster, physical = paths(scenario, cell)
    factory = None
    delegate = None
    if cell == "HHplus":
        factory = HelixPlus
    elif cell == "V4":
        state = read(solution.parent / "placement.json")["state"]
        if condition == "singleton1":
            class KappaOne(AdmissionScheduler):
                def _decode_token_service(self, node, first, end, active_sessions):
                    return SingleTokenQueueCostScheduler._decode_token_service(
                        self, node, first, end, active_sessions)
            scheduler = KappaOne
        else:
            scheduler = AdmissionScheduler
        factory = lambda sim: scheduler(sim, state=state, admission="sparse", routing_state="live")
        chunk = (BoundaryCostHook(4_194_304, scope="slow", boundary_cost_s=0.05)
                 if condition == "boundary50ms" else PromptTransferChunkHook(4_194_304, scope="slow"))
        delegate = MechanismProbe(chunk)
    probe = PerturbationProbe(condition, job["seed"], delegate)
    with singleton_runtime(condition):
        row = run(scenario, "helix" if cell == "HH" else "queue_dag", job["load"],
                  job["duration"], 0, job["seed"], solution, cluster,
                  physical_cluster=physical, scheduler_factory=factory,
                  compact=True, record_query_samples=True, profile_resources=True,
                  phase_link_probe=probe)
    if cell == "V4":
        row.update(row["phase_link_profile"]["corrected_network_accounting"])
        row["network_accounting"] = "v4_chunk_aware_v1"
    row.update(condition=condition, cell=cell, solution_sha256=sha(solution),
               sim_cluster_sha256=sha(cluster),
               gpu_seconds_per_output_token=sum(row["gpu_busy_fraction"].values()) /
               row["output_throughput_tokens_per_s"])
    return row


def register(phase, workers):
    target = HERE / phase / "manifest.json"
    if target.exists():
        manifest = read(target)
        check(manifest)
        return manifest
    if phase == "formal":
        smoke = read(HERE / "smoke_v2/index.json")
        assert smoke["status"] == "terminal"
        assert all(entry["status"] == "completed" for entry in smoke["jobs"].values())
    duration = 60 if phase.startswith("smoke") else 1800
    seeds = (100,) if phase.startswith("smoke") else tuple(range(5))
    conditions = ("profile20", "bandwidth50", "latency20", "activation_kv_high20",
                  "singleton1", "boundary50ms") if phase.startswith("smoke") else CONDITIONS
    jobs = [dict(key=f"{scenario}/{condition}/{cell}/seed{seed}", scenario=scenario,
                 load=load, condition=condition, cell=cell, seed=seed, duration=duration)
            for scenario, load in LOADS.items() for condition in conditions
            for cell in CELLS for seed in seeds]
    sources = dict(read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")["sources_sha256"])
    for path in (Path(__file__), Path(__file__).parent / "campaign_queue.py",
                 ROOT / "experiments/v4_core_validation/core.py",
                 ROOT / "experiments/v4_validation/diagnostics.py"):
        sources[relative(path)] = sha(path)
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
                    sources_sha256=sources, worker_limit=workers, timeout_wall_s=14400,
                    duration_s=duration, seeds=seeds, conditions=conditions,
                    protocol="fixed_window_no_tail_drain", loads=LOADS,
                    profile_error="Truncated lognormal per seed/GPU/layer/phase/batch, within ±10% or ±20%",
                    bandwidth_error="Uniform per cross-region compute link every 30s, within ±20% or ±50%; active sends keep original booked finish",
                    latency_error="Uniform per compute link every 30s, ±20%; active sends keep original booked finish",
                    activation_kv_error="Activation bytes multiplied 0.8/1.2 and KV token-equivalent capacity divided 0.8/1.2",
                    failure_policy="One attempt per condition; preserve failures; no zero imputation",
                    engineering_amendment=("Original smoke used live link capacity changes, which caused a stale Helix MaxFlow share to assert LinkBounded. smoke_v2 and formal perturb physical send duration while retaining nominal reservation capacity; original smoke artifacts preserved."
                                           if phase != "smoke" else None),
                    environment=dict(executable=sys.executable, env=ENV))
    write(target, manifest)
    return manifest


def report():
    manifest, index = read(HERE / "formal/manifest.json"), read(HERE / "formal/index.json")
    assert index["status"] == "terminal"
    rows, groups = [], defaultdict(dict)
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        assert entry["status"] in ("completed", "failed")
        artifact = ROOT / entry["source"]
        assert sha(artifact) == entry["artifact_sha256"]
        outcome = read(artifact)
        rows.append({**{key: job[key] for key in ("scenario", "load", "condition", "cell", "seed")},
                     "status": entry["status"], "source": entry["source"],
                     "artifact_sha256": entry["artifact_sha256"],
                     "error": outcome.get("error", ""),
                     "trace_sha256": outcome.get("trace_sha256", ""),
                     **{key: outcome.get(key) for key in METRICS}})
        if entry["status"] == "completed":
            assert len(outcome["query_samples"]) == outcome["arrivals"]
            groups[(job["scenario"], job["condition"], job["seed"])][job["cell"]] = outcome
    for group in groups.values():
        assert len({r["trace_sha256"] for r in group.values()}) == 1
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 输入建模误差鲁棒性（P1-1）", "",
             "70B、两种高负载、五种子；同一条件下 RCAPS/Helix/Helix+ 共享请求轨迹与确定性扰动键。",
             "带宽/时延每 30 s 更新；已启动传输保留起始时刻定出的完成时间，不模拟传输中途的连续重调速。",
             "所有结果来自 CPU 离散事件模拟；人为块边界成本不是真机测量。失败不填零。", "",
             "| 拓扑 | 扰动 | 方法 | 成功 | P95 TPOT(s) | P95 TTFT(s) | 输出 token/s | 完成率 | GPU 秒/token |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for scenario in LOADS:
        for condition in CONDITIONS:
            for cell in CELLS:
                subset = [r for r in rows if (r["scenario"], r["condition"], r["cell"]) ==
                          (scenario, condition, cell) and r["status"] == "completed"]
                values = [f"{mean(r[k] for r in subset):.4f} ± {stdev(r[k] for r in subset):.4f}"
                          if len(subset) == 5 else "未汇总" for k in METRICS]
                lines.append(f"| {scenario} | {condition} | {cell} | {len(subset)}/5 | " +
                             " | ".join(values) + " |")
    lines += ["", "| 拓扑 | 扰动 | 基线 | 配对种子 | RCAPS TPOT 降幅 [95% CI] |",
              "|---|---|---|---:|---:|"]
    for scenario in LOADS:
        for condition in CONDITIONS:
            for base in ("HH", "HHplus"):
                paired = [groups[(scenario, condition, seed)] for seed in range(5)]
                if all(base in group and "V4" in group for group in paired):
                    deltas = [100 * (1 - group["V4"]["tpot_p95_s"] / group[base]["tpot_p95_s"])
                              for group in paired]
                    m, h = mean(deltas), 2.776445 * stdev(deltas) / math.sqrt(5)
                    value = f"{m:.2f}% [{m-h:.2f}%, {m+h:.2f}%]"
                else:
                    value = "存在失败，未汇总"
                lines.append(f"| {scenario} | {condition} | {base} | " +
                             f"{sum(base in g and 'V4' in g for g in paired)}/5 | {value} |")
    lines += ["", "论文可用表述：RCAPS 的相对收益必须逐扰动、逐拓扑与基线完整指标共同报告。"
              "只有五种子配对均成功时才发布配对置信区间；不能把某个扰动的稳定性外推为真实硬件稳健性。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, jobs=len(rows),
          counts=dict(Counter(r["status"] for r in rows)),
          manifest_sha256=sha(HERE / "formal/manifest.json"),
          individual_sha256=sha(HERE / "individual.csv"),
          report_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "smoke_v2", "formal"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, evaluate)
    else:
        queue(HERE, "experiments.v6_completion.robustness", args.phase, args.workers,
              register, report)


if __name__ == "__main__":
    main()

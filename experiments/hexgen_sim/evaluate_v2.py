"""Paired-trace HexGen evaluation with conservative KV admission.

Every global query is dispatched to exactly one independent pipeline. The
official HexGen artifact's benchmark README documents round-robin dispatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from benchmarks.fixed_window import run
from benchmarks.layout import scenario
from rcaps.v3.topology import TopologyModel
from simulator.event_simulator.utils import BASE_QUERY_UID
from .admission_scheduler_v2 import CapacitySafeScheduler
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(manifest_path: Path, offered: float, duration: int, warmup: int,
             seed: int, trace_override: list[tuple[float, int, int]] | None = None) -> dict:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    folder = manifest_path.parent
    physical = ROOT / manifest["physical_cluster"]
    if sha(physical) != manifest["physical_sha256"]:
        raise ValueError("Physical topology differs from candidate manifest")
    topology = TopologyModel(physical)
    case = "multi" if physical.resolve() == scenario("multi")[0].resolve() else "single"
    # This is only needed by the layout synthesizer; the development method
    # below loads our pipeline graph directly.
    profile = (ROOT / "artifact_evaluation/high_heterogeneity/config/machine_profiles.ini"
               if len(topology.types) == 42 else scenario(case)[1])
    if trace_override is None:
        trace = OnlineRequestFeeder(cluster_token_throughput=offered,
                                    start_time=0, duration=duration, seed=seed).trace
    else:
        trace = trace_override
    trace_hash = hashlib.sha256(json.dumps(
        [(round(t, 9), prompt, output) for t, prompt, output in trace],
        separators=(",", ":")).encode()).hexdigest()
    entries = manifest["pipelines"]
    if not entries:
        raise ValueError("Empty pipeline partition")
    assigned = [[] for _ in entries]
    for index, item in enumerate(trace):
        assigned[index % len(entries)].append((index, *item))
    if sorted(index for group in assigned for index, *_ in group) != list(range(len(trace))):
        raise AssertionError("Round-robin dispatch lost or duplicated a query")
    rows, pooled, samples, routes = [], {k: [] for k in ("e2e", "paper_prompt", "paper_decode")}, {}, {}
    admission = []
    for pipe, entry in enumerate(entries):
        solution = folder / entry["solution"]
        cluster = folder / entry["sim_cluster"]
        if sha(solution) != entry["solution_sha256"] or sha(cluster) != entry["sim_cluster_sha256"]:
            raise ValueError(f"Pipeline {pipe} artifact changed")
        chosen = assigned[pipe]
        schedulers = []
        def make_scheduler(simulator):
            scheduler = CapacitySafeScheduler(simulator)
            schedulers.append(scheduler)
            return scheduler
        result = run(case, "hexgen_development", offered, duration, warmup, seed,
                     solution, cluster, compact=True, record_query_samples=True,
                     include_distributions=True, physical_cluster=physical,
                     machine_profile=profile, machine_counts=topology.machine_counts,
                     allow_force_set=True,
                     scheduler_factory=make_scheduler,
                     trace_override=[(t, prompt, output) for _, t, prompt, output in chosen])
        scheduler = schedulers[0]
        admission.append({"pipeline": pipe,
                          "kv_budget_tokens": scheduler.kv_budget_tokens,
                          "deferred_dispatches": scheduler.deferred_dispatches,
                          "oversize_queries": sorted(scheduler.oversize_queries),
                          "max_reserved_tokens": scheduler.max_reserved_tokens})
        measured = [(local, row) for local, row in enumerate(chosen)
                    if warmup <= row[1] < duration]
        if result["arrivals"] != len(measured) or len(result["query_samples"]) != len(measured):
            raise AssertionError(f"Pipeline {pipe} omitted a query")
        for local, (global_index, t, prompt, output) in measured:
            sample = result["query_samples"][str(BASE_QUERY_UID + local)]
            if (abs(sample["arrival_s"] - (t - warmup)) > 1e-9 or sample["input_tokens"] != prompt
                    or sample["output_tokens"] != output):
                raise AssertionError("Query identity or content changed")
            samples[str(BASE_QUERY_UID + global_index)] = sample
        for key, values in result.pop("_distributions").items():
            if key in pooled:
                pooled[key].extend(values)
        for route, count in result.pop("route_counts").items():
            routes[f"pipeline_{pipe}/{route}"] = count
        result.pop("query_samples")
        rows.append(result)
    measured_total = sum(warmup <= t < duration for t, _, _ in trace)
    if len(samples) != measured_total:
        raise AssertionError("Global query set incomplete")
    values = lambda field: [row[field] for row in samples.values() if row[field] is not None]
    p95 = lambda array: float(np.percentile(array, 95)) if array else None
    complete = sum(int(row["completed"]) for row in samples.values())
    if len(pooled["e2e"]) != complete:
        raise AssertionError("Completed query count differs from pooled latency samples")
    window = duration - warmup
    return {
        "status": "development_result", "method": "hexgen_capacity_safe_v2",
        "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path),
        "physical_cluster_sha256": sha(physical), "offered_tokens_per_s": offered,
        "duration_s": duration, "warmup_s": warmup, "seed": seed,
        "trace_sha256": trace_hash, "arrivals": measured_total,
        "evaluation_protocol": "fixed_window_no_tail_drain",
        "python_version": sys.version.split()[0], "numpy_version": np.__version__,
        "output_throughput_tokens_per_s": sum(r["output_throughput_tokens_per_s"] for r in rows),
        "completed_request_throughput_per_s": complete / window,
        "completion_fraction": complete / measured_total if measured_total else None,
        "ttft_p95_s": p95(values("ttft_s")), "tpot_p95_s": p95(values("tpot_s")),
        "e2e_p95_s": p95(pooled["e2e"]),
        "paper_prompt_request_p95_s": p95(pooled["paper_prompt"]),
        "paper_decode_request_p95_s": p95(pooled["paper_decode"]),
        "backlog_at_window_end": sum(row["backlog_at_window_end"] for row in rows),
        "route_counts": routes, "pipelines": rows,
        "query_samples": dict(sorted(samples.items(), key=lambda item: int(item[0]))),
        "round_robin_counts": [len(group) for group in assigned],
        "admission": admission,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--offered", type=float, default=350)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=0)
    parser.add_argument("--seed", type=int, default=2403)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation: {args.output}")
    result = evaluate(args.manifest, args.offered, args.duration, args.warmup, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "status", "arrivals", "completion_fraction", "ttft_p95_s", "tpot_p95_s",
        "output_throughput_tokens_per_s", "trace_sha256")}, indent=2))


if __name__ == "__main__":
    main()

"""Continue paired fixed-policy windows until the complete arrival cohort finishes.

The historical experiment and all its sources stay untouched. The only
instrumentation added here captures the accumulator and per-query event times;
neither observation is read by a scheduler.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import os
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from experiments.v3_path_crossover import run as original

ROOT = original.ROOT
HERE = Path(__file__).resolve().parent
PROTOCOL = original.read(HERE / "protocol.json")
CASES = tuple((case["load"], case["network"]) for case in PROTOCOL["cases"])
POLICIES = tuple(PROTOCOL["policies"])
CORE_WINDOW_KEYS = (
    "trace_sha256", "arrivals", "output_throughput_tokens_per_s",
    "completed_request_throughput_per_s", "ttft_p95_s", "tpot_p95_s",
    "e2e_p95_s", "completion_fraction", "backlog_at_window_start",
    "backlog_at_window_end", "first_tokens_in_window", "queries_with_tpot_samples",
    "paper_prompt_request_p95_s", "paper_decode_request_p95_s",
    "paper_prompt_request_count", "paper_decode_request_count", "route_counts",
    "path_records", "kv_admission", "kv_capacity", "kv_peak_reserved",
    "kv_peak_fraction", "decode_batches", "scaled_links",
)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def environment():
    import numpy as np
    expected = Path("D:/software/miniconda/envs/gllm/python.exe")
    if os.environ.get("CONDA_DEFAULT_ENV") != "gllm":
        raise RuntimeError("Explicitly conda activate gllm before running")
    if Path(sys.executable).resolve() != expected.resolve():
        raise RuntimeError(f"Wrong Python interpreter: {sys.executable}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("Set PYTHONHASHSEED=0 before starting Python")
    return {"python": sys.version.split()[0], "numpy": np.__version__,
            "executable": sys.executable, "conda_default_env": os.environ["CONDA_DEFAULT_ENV"],
            "conda_prefix": os.environ.get("CONDA_PREFIX"), "pythonhashseed": "0"}


def source_hashes():
    files = set(original.FROZEN_SOURCES)
    files.update(("experiments/v3_path_crossover/run.py",
                  "experiments/v3_path_crossover/audit.json",
                  "experiments/v3_path_crossover/protocol.json"))
    for directory in ("simulator", "rcaps", "benchmarks", "experiments"):
        files.update(p.relative_to(ROOT).as_posix()
                     for p in (ROOT / directory).rglob("*.py")
                     if "__pycache__" not in p.parts)
    files.add((HERE / "protocol.json").relative_to(ROOT).as_posix())
    return {name: original.digest(ROOT / name) for name in sorted(files)}


def freeze():
    original.check_frozen()
    result = {"registered_at_utc": timestamp(), "environment": environment(),
              "protocol_sha256": original.digest(HERE / "protocol.json"),
              "sources_sha256": source_hashes(),
              "original_audit_sha256": original.digest(original.HERE / "audit.json")}
    path = HERE / "audit.json"
    if path.exists():
        check_frozen()
        return {"status": "already_frozen", "source": str(path)}
    original.write(path, result)
    return {"status": "frozen", "source": str(path),
            "source_count": len(result["sources_sha256"])}


def check_frozen():
    original.check_frozen()
    audit = original.read(HERE / "audit.json")
    if audit["sources_sha256"] != source_hashes():
        raise ValueError("Follow-up source snapshot changed; preserve V1 and register a new version")
    if audit["environment"] != environment():
        raise ValueError("Activated environment differs from frozen environment")
    return audit


def result_path(phase, load, network, policy, seed):
    return HERE / "runs" / phase / load / network / f"{policy}_seed{seed}.json"


def registered_job(phase, load, network, policy, seed):
    if phase not in ("smoke", "development", "formal"):
        raise ValueError(f"Unregistered phase: {phase}")
    if (load, network) not in CASES or policy not in POLICIES:
        raise ValueError("Unregistered condition or policy")
    if seed not in PROTOCOL[phase]["seeds"]:
        raise ValueError("Do not replace the registered seed")
    return PROTOCOL[phase]


def kv_snapshot(scheduler, batches):
    capacities = {str(uid): node.kv_cache.max_capacity
                  for uid, node in scheduler.simulator.compute_nodes.items()
                  if node.kv_cache is not None}
    peaks = {str(uid): value for uid, value in scheduler.peak_reserved.items()}
    executions = sum(item[0] for item in batches.values())
    tokens = sum(item[1] for item in batches.values())
    return copy.deepcopy({
        "path_records": {str(uid): {"hops": hops, "partial_hops": partial_hops}
                         for uid, (hops, partial_hops) in scheduler.route_records.items()},
        "kv_admission": scheduler.kv_admission, "kv_capacity": capacities,
        "kv_peak_reserved": peaks,
        "kv_peak_fraction": max((value / capacities[uid] for uid, value in peaks.items()), default=0),
        "remaining_kv_reservations": {str(uid): value for uid, value in scheduler._reserved.items()},
        "decode_batches": {"executions": executions, "decode_tokens": tokens,
                           "mean_batch": tokens / executions if executions else None,
                           "single_share": (sum(item[2] for item in batches.values()) / executions
                                            if executions else None)},
    })


def cohort_summary(samples):
    from benchmarks.fixed_window import p95
    complete = sum(s["completed"] for s in samples.values())
    return {
        "arrivals": len(samples), "completed": complete,
        "completion_fraction": complete / len(samples) if samples else None,
        "ttft_p95_s": p95([s["ttft_s"] for s in samples.values() if s["ttft_s"] is not None]),
        "tpot_p95_s": p95([s["tpot_s"] for s in samples.values() if s["tpot_s"] is not None]),
        "e2e_p95_s": p95([s["finish_s"] - s["arrival_s"] for s in samples.values()
                          if s["completed"]]),
        "queries_with_tpot_samples": sum(s["tpot_s"] is not None for s in samples.values()),
    }


def historical_comparison(window, load, network, policy, seed):
    path = original.HERE / "runs/formal_isolated" / load / network / f"{policy}_seed{seed}.json"
    old = original.read(path)
    differences = [key for key in CORE_WINDOW_KEYS if window.get(key) != old.get(key)]
    for uid, sample in old["query_samples"].items():
        new = window["query_samples"].get(uid, {})
        if any(new.get(key) != value for key, value in sample.items()):
            differences.append(f"query_samples/{uid}")
    if set(old["query_samples"]) != set(window["query_samples"]):
        differences.append("query_sample_ids")
    return {"source": path.relative_to(ROOT).as_posix(),
            "sha256": original.digest(path), "equal": not differences,
            "differences": differences}


def execute(phase, load, network, policy, seed):
    spec = registered_job(phase, load, network, policy, seed)
    check_frozen()
    duration = spec["arrival_duration_s"]
    output = result_path(phase, load, network, policy, seed)
    identity = {"experiment": PROTOCOL["experiment"], "phase": phase,
                "load_label": load, "network_profile": network, "path_space": policy,
                "seed": seed, "duration_s": duration, "warmup_s": 0,
                "maximum_drain_s": spec["maximum_drain_s"],
                "audit_sha256": original.digest(HERE / "audit.json")}
    failure = output.with_suffix(".failure.json")
    if failure.exists():
        raise ValueError(f"Preserved failure must be investigated, not retried silently: {failure}")
    if output.exists():
        old = original.read(output)
        if all(old.get(key) == value for key, value in identity.items()):
            return {"status": "reused", "source": str(output.relative_to(ROOT))}
        raise ValueError(f"Refusing to overwrite different result: {output}")

    from benchmarks import accumulator, fixed_window
    from experiments.v3_cluster42.kv_admission import install_completion_wakeup
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    context = original.load_context()
    original_audit = original.check_frozen()
    base = original.builder(policy, context)
    slow_ids = {item["link_uid"] for item in original_audit["scaled_links"]}
    factor = original.NETWORKS[network]
    holder, batches = {}, defaultdict(lambda: [0, 0, 0])

    class CapturingAccumulator(accumulator.WindowAccumulator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            holder["accumulator"] = self

        def _observe_query(self, query, beginning, ending, finish=None):
            super()._observe_query(query, beginning, ending, finish)
            sample = self.query_samples.get(str(query.query_uid))
            if sample is not None:
                sample["finish_s"] = finish - beginning if finish is not None else None
                sample["prompt_end_s"] = (query.inference_history[0].end_time - beginning
                                           if query.inference_history else None)
                sample["decode_completion_times_s"] = [
                    item.end_time - beginning for item in query.inference_history[1:]
                    if item.request_phase == RequestPhase.Increment and item.end_time < ending]
                sample["route"] = ([stage.node_uid for stage in query.inference_history[0].path[:-1]]
                                   if query.inference_history else [])

    def factory(simulator):
        links = []
        for link in simulator.links.values():
            if link.link_uid in slow_ids:
                nominal = link.bandwidth
                link.bandwidth *= factor
                link.available_bandwidth = link.bandwidth
                links.append({"link_uid": link.link_uid, "nominal_Bps": nominal,
                              "effective_Bps": link.bandwidth, "latency_s": link.latency})
        if len(links) != len(slow_ids):
            raise ValueError("Frozen network intervention differs")
        for node in simulator.compute_nodes.values():
            original_start = node.start_execution

            def record(requests, _start=original_start, _uid=node.node_uid):
                count = sum(req.phase == RequestPhase.Increment for req in requests)
                if count:
                    entry = batches[_uid]
                    entry[0] += 1
                    entry[1] += count
                    entry[2] += count == 1
                return _start(requests)

            node.start_execution = record
        scheduler = base(simulator)
        install_completion_wakeup(simulator, scheduler)
        holder.update(simulator=simulator, scheduler=scheduler, scaled_links=links)
        return scheduler

    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    log_path = output.with_suffix(".log")
    try:
        with log_path.open("w", encoding="utf-8") as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
                patch.object(accumulator, "WindowAccumulator", CapturingAccumulator):
            window = fixed_window.run(
                context["topology"], "queue_dag", original.LOADS[load], duration, 0, seed,
                original.DEPLOY / "solution.ini", original.DEPLOY / "simulator_cluster.ini",
                compact=True, record_query_samples=True, physical_cluster=context["physical"],
                machine_counts=TopologyModel(context["physical"]).machine_counts,
                scheduler_factory=factory)
            sim, scheduler, captured = (holder[key] for key in ("simulator", "scheduler", "accumulator"))
            window.update(kv_snapshot(scheduler, batches))
            window["scaled_links"] = holder["scaled_links"]
            # Freeze before continuation: accumulator query_samples is a live dictionary.
            window = copy.deepcopy(window)
            reproduction = (historical_comparison(window, load, network, policy, seed)
                            if phase == "formal" else None)
            if reproduction is not None and not reproduction["equal"]:
                raise ValueError(f"Historical window did not reproduce: {reproduction['differences']}")
            horizon = sim.current_time
            beginning = horizon - duration
            deadline = horizon + spec["maximum_drain_s"]
            while sim.query_manager.queries_on_the_fly and sim.current_time < deadline:
                sim.simulate(until=min(deadline, sim.current_time + 30))
                captured.collect(sim, beginning, deadline)
            if sim.query_manager.queries_on_the_fly:
                raise ValueError(f"Bounded drain incomplete: {len(sim.query_manager.queries_on_the_fly)} requests")
            samples = copy.deepcopy(captured.query_samples)
            if len(samples) != window["arrivals"] or not all(s["completed"] for s in samples.values()):
                raise ValueError("Lifecycle cohort missing arrivals or completed queries")
            if sum(s["output_tokens"] for s in samples.values()) != captured.output_count:
                raise ValueError("Output conservation failed after drain")
            prefix = {uid: sample for uid, sample in samples.items()
                      if sample["arrival_s"] < spec["prefix_arrival_before_s"]}
            last_finish = max(s["finish_s"] for s in samples.values()) if samples else 0.0
            lifecycle = {**cohort_summary(samples), **kv_snapshot(scheduler, batches),
                         "query_samples": samples,
                         "output_tokens_completed": captured.output_count,
                         "last_completion_s": last_finish,
                         "drain_to_last_completion_s": max(0.0, last_finish - duration),
                         "prefix_arrival_before_s": spec["prefix_arrival_before_s"],
                         "prefix": cohort_summary(prefix)}
            row = {**identity, "classification": "simulation_only", "environment": environment(),
                   "started_at_utc": datetime.fromtimestamp(time.time() - (time.perf_counter() - started), timezone.utc).isoformat(),
                   "finished_at_utc": timestamp(), "wall_seconds": time.perf_counter() - started,
                   "trace_sha256": window["trace_sha256"],
                   "historical_window_reproduction": reproduction,
                   "window": window, "lifecycle": lifecycle}
            original.write(output, row)
    except Exception as error:
        with log_path.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        original.write(failure, {**identity, "error": repr(error),
                                "traceback": traceback.format_exc(), "failed_at_utc": timestamp()})
        raise
    return {"status": "passed", "source": str(output.relative_to(ROOT)),
            "wall_seconds": row["wall_seconds"], "drain_s": lifecycle["drain_to_last_completion_s"]}


def drive(phase, workers):
    check_frozen()
    if workers not in (1, 2, 3):
        raise ValueError("Use 1 to 3 independent CPU workers")
    jobs = [(load, network, policy, seed) for seed in PROTOCOL[phase]["seeds"]
            for load, network in CASES for policy in POLICIES]
    index_path = HERE / f"{phase}_index.json"
    # Resume only completed, matching cells; preserved failures stop the matrix.
    failures = list((HERE / "runs" / phase).rglob("*.failure.json"))
    if failures:
        raise ValueError(f"Preserved failures: {failures}")
    index = {"phase": phase, "started_at_utc": timestamp(), "expected": len(jobs),
             "workers": workers, "jobs": {}, "complete": False}
    original.write(index_path, index)

    def launch(job):
        load, network, policy, seed = job
        args = [sys.executable, "-X", "faulthandler", "-m",
                "experiments.v3_adaptive_space_cohort.run", "--phase", phase,
                "--one", load, network, policy, str(seed)]
        process = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        output = result_path(phase, *job)
        return job, {"exit_code": process.returncode, "result_exists": output.exists(),
                     "stdout": process.stdout, "stderr": process.stderr,
                     "finished_at_utc": timestamp()}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(launch, job) for job in jobs]
        for future in as_completed(futures):
            job, outcome = future.result()
            key = "/".join(str(value) for value in job)
            index["jobs"][key] = outcome
            original.write(index_path, index)
            print(json.dumps({"done": len(index["jobs"]), "expected": len(jobs),
                              "job": key, **outcome}, ensure_ascii=False), flush=True)
    index["complete"] = len(index["jobs"]) == len(jobs) and all(
        item["exit_code"] == 0 and item["result_exists"] for item in index["jobs"].values())
    index["finished_at_utc"] = timestamp()
    original.write(index_path, index)
    if not index["complete"]:
        raise SystemExit("Matrix has failed processes; preserve all evidence and investigate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("freeze", "smoke", "development", "formal"))
    parser.add_argument("--one", nargs=4, metavar=("LOAD", "NETWORK", "POLICY", "SEED"))
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.phase == "freeze":
        print(json.dumps(freeze(), ensure_ascii=False))
    elif args.one:
        load, network, policy, seed = args.one
        print(json.dumps(execute(args.phase, load, network, policy, int(seed)), ensure_ascii=False))
    else:
        drive(args.phase, args.workers)


if __name__ == "__main__":
    main()

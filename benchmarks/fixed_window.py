"""Compare layouts at a fixed simulation horizon without draining the backlog.

The original online feeder drains all outstanding queries after its arrival
trace ends. That tail is outside the measurement window and can be enormous
under overload. This driver stops at the horizon and measures completed token
events and the visible portions of queries that arrived in the window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

import numpy as np

# The simulator imports pyplot for optional plots. Evaluation only needs its
# event engine; a noninteractive backend avoids loading Tk into long runs.
os.environ.setdefault("MPLBACKEND", "Agg")

from benchmarks.layout import MACHINES, ROOT, _NullLogger, load_graph_layout, scenario
from simulator.event_simulator.cluster_simulator import ClusterSimulator
from simulator.event_simulator.request import RequestPhase
from simulator.model_manager.model_manager import ModelName
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder


def p95(values: list[float]) -> float | None:
    return float(np.percentile(values, 95)) if values else None


def paper_p95(values: list[float]) -> float | None:
    """Match Helix artifact's sorted[int(n * 0.95)] request-latency rule."""
    return sorted(values)[int(len(values) * 0.95)] if values else None


class _NullLatencyAnalyzer:
    """Metrics below are computed directly from requests and queries."""

    def add_request(self, **_kwargs):
        return None

    def add_query(self, **_kwargs):
        return None


def run(name: str, method: str, offered: float, duration: int, warmup: int,
        seed: int, solution: Path | None = None,
        sim_cluster: Path | None = None,
        profile_resources: bool = False, scheduler_factory=None,
        checkpoint_file: Path | None = None, checkpoint_every: int = 25,
        compact: bool = False, physical_cluster: Path | None = None,
        profile_scheduler: bool = False, record_query_samples: bool = False,
        machine_counts: dict[str, int] | None = None,
        machine_profile: Path | None = None,
        trace_override: list[tuple[float, int, int]] | None = None,
        allow_force_set: bool = False,
        include_distributions: bool = False,
        phase_link_probe=None) -> dict:
    cluster, profile, helix_solution, helix_sim_cluster = scenario(name)
    cluster = physical_cluster or cluster
    profile = machine_profile or profile
    machines = machine_counts or MACHINES
    solution = solution or helix_solution
    sim_cluster = sim_cluster or helix_sim_cluster
    layout = None
    if method in ("helix", "swarm", "separate"):
        from simulator.initial_layout.layout_synthesizer import LayoutMethod, LayoutSynthesizer
        layout = LayoutSynthesizer(str(cluster), str(profile), ModelName.LLaMa70B,
                                   str(ROOT / "benchmarks/runs"),
                                   LayoutMethod.LoadExisting, machines)
        layout.synthesize({"solution_file_name": str(solution),
                           "simulator_cluster_file_name": str(sim_cluster)})
    simulator = ClusterSimulator(model_name=ModelName.LLaMa70B,
                                 machine_num_dict=machines)
    simulator.model_manager.allow_force_set = allow_force_set
    simulator.logger = _NullLogger()
    simulator.from_ini_file(config_file_name=str(sim_cluster))
    if method == "helix":
        from simulator.scheduler.base_scheduler import SchedulingMethod
        from simulator.scheduler.global_maxflow.global_maxflow_scheduler import SchedulingMode
        from simulator.scheduler.global_maxflow.kv_expectation import KVParameters
        simulator.init_scheduler(SchedulingMethod.MaxFlow, {
            "kv_param": KVParameters(expected_kv_hwm=0.9,
                                     expected_output_length_ratio=0.6),
            "scheduling_mode": SchedulingMode.Online})
    elif method == "swarm":
        from simulator.scheduler.base_scheduler import SchedulingMethod

        simulator.init_scheduler(SchedulingMethod.Swarm)
    elif method == "separate":
        from simulator.scheduler.base_scheduler import SchedulingMethod

        simulator.init_scheduler(SchedulingMethod.Naive)
    elif scheduler_factory is not None:
        simulator.set_scheduler(scheduler_factory(simulator))
    else:
        raise ValueError("A scheduler_factory is required for RCAPS simulation")
    simulator.init_query_manager()
    simulator.mark_as_ready()
    start = layout.set_layout(simulator) if layout is not None else load_graph_layout(simulator, solution)
    if layout is not None:
        simulator.update_scheduler()
    beginning, ending = start + warmup, start + duration
    if phase_link_probe is not None:
        phase_link_probe.install(simulator, beginning, ending)
    scheduler_calls: dict[str, list[int]] = {}
    if profile_scheduler:
        for operation in ("schedule_transmission", "schedule_execution",
                          "update_scheduler", "_route"):
            original = getattr(simulator.scheduler, operation, None)
            if original is None:
                continue
            samples = scheduler_calls.setdefault(operation, [])

            def timed(*args, _original=original, _samples=samples, **kwargs):
                if not beginning <= simulator.current_time < ending:
                    return _original(*args, **kwargs)
                started_ns = time.perf_counter_ns()
                try:
                    return _original(*args, **kwargs)
                finally:
                    _samples.append(time.perf_counter_ns() - started_ns)

            setattr(simulator.scheduler, operation, timed)
    checkpoint_io = None
    checkpoint = None
    next_index = 0
    if checkpoint_file is not None:
        if profile_resources or checkpoint_every <= 0:
            raise ValueError("Checkpointing requires no resource profiling and a positive interval")
        from benchmarks import checkpoint as checkpoint_io
        identity = (name, method, offered, duration, warmup, seed,
                    hashlib.sha256(solution.read_bytes()).hexdigest(),
                    hashlib.sha256(sim_cluster.read_bytes()).hexdigest())
        if checkpoint_file.exists():
            checkpoint = checkpoint_io.load(checkpoint_file)
            if checkpoint["identity"] != identity:
                raise ValueError("Checkpoint configuration does not match this run")
            simulator = checkpoint["simulator"]
            start = checkpoint["start"]
            next_index = checkpoint["next_index"]
    if trace_override is None:
        feeder = OnlineRequestFeeder(cluster_token_throughput=offered,
                                     start_time=start, duration=duration, seed=seed)
    else:
        random.seed(seed)
        feeder = SimpleNamespace(trace=[
            (start + arrival, input_tokens, output_tokens)
            for arrival, input_tokens, output_tokens in trace_override])
    trace_payload = [(round(arrival - start, 9), input_tokens, output_tokens)
                     for arrival, input_tokens, output_tokens in feeder.trace]
    trace_sha256 = hashlib.sha256(json.dumps(trace_payload,
                                            separators=(",", ":")).encode()).hexdigest()
    if checkpoint is not None and checkpoint["trace_sha256"] != trace_sha256:
        raise ValueError("Checkpoint request trace does not match this run")
    resource_profile = None
    if profile_resources:
        from benchmarks.resource_profile import ResourceProfile
        resource_profile = ResourceProfile(simulator, beginning, ending)
        resource_profile.install()
    manager = simulator.query_manager
    accumulator = None
    if compact:
        from benchmarks.accumulator import WindowAccumulator
        accumulator = (checkpoint.get("accumulator") if checkpoint is not None
                       else None) or WindowAccumulator(record_queries=record_query_samples)
        if not hasattr(accumulator, "record_queries"):
            accumulator.record_queries = False
            accumulator.query_samples = {}
        if record_query_samples and not accumulator.record_queries:
            raise ValueError("Checkpoint lacks query samples; use a fresh checkpoint")
        if not hasattr(accumulator, "paper_prompt_latencies"):
            raise ValueError("Compact checkpoint predates request-latency metrics; use a fresh checkpoint")
        if not hasattr(accumulator, "compacted_until"):
            accumulator.compacted_until = {}
        if not hasattr(accumulator, "route_latencies"):
            accumulator.route_latencies = {}
        manager.latency_analyzer = _NullLatencyAnalyzer()
        accumulator.collect(simulator, beginning, ending)
    elif checkpoint is not None and "accumulator" in checkpoint:
        raise ValueError("A compact checkpoint must be resumed with --compact")
    for index, (arrival, input_tokens, output_tokens) in enumerate(feeder.trace):
        if arrival >= ending:
            break
        if index < next_index:
            continue
        simulator.simulate(until=arrival)
        if accumulator is not None:
            accumulator.collect(simulator, beginning, ending)
        manager.issue_query(creation_time=arrival, input_seq_length=input_tokens,
                            output_seq_length=output_tokens)
        if checkpoint_io is not None and (index + 1) % checkpoint_every == 0:
            checkpoint_io.save(checkpoint_file, {
                "identity": identity, "trace_sha256": trace_sha256,
                "simulator": simulator, "start": start, "next_index": index + 1,
                **({"accumulator": accumulator} if accumulator is not None else {})})
        if (index + 1) % 100 == 0:
            print(f"progress: {name}/{method}, arrivals={index + 1}, "
                  f"sim_time={simulator.current_time:.1f}", file=sys.stderr,
                  flush=True)
    simulator.simulate(until=ending)
    if accumulator is not None:
        accumulator.collect(simulator, beginning, ending)
        accumulator.observe_active(simulator, beginning, ending)
    all_queries = [query for _, query in manager.finished_queries.values()]
    all_queries.extend(manager.queries_on_the_fly.values())
    route_counts = Counter()
    for query in all_queries:
        if query.inference_history:
            route = query.inference_history[0].path
            route_counts["-".join(str(stage.node_uid) for stage in route[:-1])] += 1
    arrivals = sum(beginning <= t < ending for t, _, _ in feeder.trace)
    observed = [query for query in all_queries
                if beginning <= query.creation_time < ending]
    first_tokens: list[float] = []
    tpots: list[float] = []
    e2es: list[float] = []
    route_latencies = defaultdict(lambda: {"ttft": [], "tpot": []})
    ttft_outliers = []
    for query in observed:
        decode_ends = [item.end_time for item in query.inference_history[1:]
                       if item.request_phase == RequestPhase.Increment and item.end_time < ending]
        route = None
        if query.inference_history:
            route = "-".join(str(stage.node_uid)
                             for stage in query.inference_history[0].path[:-1])
        if decode_ends:
            first_tokens.append(decode_ends[0] - query.creation_time)
            ttft_outliers.append({
                "query_uid": query.query_uid,
                "arrival_s": query.creation_time - start,
                "input_tokens": query.input_seq_length,
                "output_tokens": query.output_seq_length,
                "route": route, "ttft_s": first_tokens[-1]})
            if route is not None:
                route_latencies[route]["ttft"].append(first_tokens[-1])
        if len(decode_ends) >= 2:
            tpots.append(mean(b - a for a, b in zip(decode_ends, decode_ends[1:])))
            if route is not None:
                route_latencies[route]["tpot"].append(tpots[-1])
    completed = [(finish, query) for finish, query in manager.finished_queries.values()
                 if beginning <= finish < ending]
    for finish, query in completed:
        if beginning <= query.creation_time < ending:
            e2es.append(finish - query.creation_time)
    def backlog(at: float) -> int:
        finished_ids = {query.query_uid for finish, query in manager.finished_queries.values()
                        if finish <= at}
        return sum(query.creation_time <= at and query.query_uid not in finished_ids
                   for query in all_queries)
    output_count = sum(request.token_seq_length
                       for time, request in simulator.finished_requests.values()
                       if request.phase == RequestPhase.Increment and beginning <= time < ending)
    paper_prompt_latencies = [
        request.location_history[-1][1] - request.location_history[0][1]
        for time, request in simulator.finished_requests.values()
        if request.phase == RequestPhase.Initialization and beginning <= time < ending]
    paper_decode_latencies = [
        request.location_history[-1][1] - request.location_history[0][1]
        for time, request in simulator.finished_requests.values()
        if request.phase == RequestPhase.Increment and beginning <= time < ending]
    completed_count = len(completed)
    backlog_at_start, backlog_at_end = backlog(beginning), backlog(ending)
    if accumulator is not None:
        output_count = accumulator.output_count
        paper_prompt_latencies = accumulator.paper_prompt_latencies
        paper_decode_latencies = accumulator.paper_decode_latencies
        completed_count = accumulator.completed_count
        first_tokens = accumulator.first_tokens
        tpots = accumulator.tpots
        e2es = accumulator.e2es
        route_counts = accumulator.route_counts
        created_by_start = sum(t <= beginning for t, _, _ in feeder.trace)
        created_before_end = sum(t < ending for t, _, _ in feeder.trace)
        backlog_at_start = created_by_start - accumulator.finished_by_start
        backlog_at_end = created_before_end - accumulator.finished_total
    window = duration - warmup
    result = {
        "scenario": name, "method": method, "solution": str(solution),
        "sim_cluster": str(sim_cluster), "offered_tokens_per_s": offered,
        "duration_s": duration, "warmup_s": warmup, "seed": seed,
        "arrivals": arrivals, "evaluation_protocol": "fixed_window_no_tail_drain",
        "python_version": sys.version.split()[0], "numpy_version": np.__version__,
        "trace_sha256": trace_sha256,
        "output_throughput_tokens_per_s": output_count / window,
        "completed_request_throughput_per_s": completed_count / window,
        "ttft_p95_s": p95(first_tokens), "tpot_p95_s": p95(tpots),
        "e2e_p95_s": p95(e2es),
        "completion_fraction": len(e2es) / arrivals if arrivals else None,
        "backlog_at_window_start": backlog_at_start,
        "backlog_at_window_end": backlog_at_end,
        "first_tokens_in_window": len(first_tokens),
        "queries_with_tpot_samples": len(tpots),
        "paper_prompt_request_p95_s": paper_p95(paper_prompt_latencies),
        "paper_decode_request_p95_s": paper_p95(paper_decode_latencies),
        "paper_prompt_request_count": len(paper_prompt_latencies),
        "paper_decode_request_count": len(paper_decode_latencies),
        "route_counts": dict(sorted(route_counts.items())),
    }
    if physical_cluster is not None:
        result["physical_cluster"] = str(physical_cluster)
        result["physical_cluster_sha256"] = hashlib.sha256(
            physical_cluster.read_bytes()).hexdigest()
    if include_distributions:
        result["_distributions"] = {
            "ttft": first_tokens, "tpot": tpots, "e2e": e2es,
            "paper_prompt": paper_prompt_latencies,
            "paper_decode": paper_decode_latencies,
        }
    if profile_scheduler:
        result["scheduler_call_profile"] = {
            operation: {
                "calls": len(samples),
                "total_s": sum(samples) / 1e9,
                "mean_us": (sum(samples) / len(samples) / 1e3 if samples else None),
                "p50_us": (float(np.percentile(samples, 50)) / 1e3 if samples else None),
                "p95_us": (float(np.percentile(samples, 95)) / 1e3 if samples else None),
            }
            for operation, samples in scheduler_calls.items()
        }
    if accumulator is None:
        result["route_latency_p95"] = {
            route: {"ttft": p95(values["ttft"]),
                    "tpot": p95(values["tpot"])}
            for route, values in sorted(route_latencies.items())}
        result["ttft_outliers"] = sorted(
            ttft_outliers, key=lambda entry: entry["ttft_s"], reverse=True)[:10]
        result["query_samples"] = ttft_outliers
    elif record_query_samples:
        result["query_samples"] = accumulator.query_samples
    if resource_profile is not None:
        result.update(resource_profile.summary())
    if phase_link_probe is not None:
        result["phase_link_profile"] = phase_link_probe.summary(
            result.get("query_samples", {}))
    if checkpoint_file is not None:
        checkpoint_file.unlink(missing_ok=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    parser.add_argument("--method", choices=("graph", "helix"), required=True)
    parser.add_argument("--solution", type=Path)
    parser.add_argument("--sim-cluster", type=Path)
    parser.add_argument("--physical-cluster", type=Path)
    parser.add_argument("--offered", type=float, required=True)
    parser.add_argument("--duration", type=int, default=1980)
    parser.add_argument("--warmup", type=int, default=180)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--profile-resources", action="store_true")
    parser.add_argument("--profile-scheduler", action="store_true")
    parser.add_argument("--checkpoint-file", type=Path)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.scenario, args.method, args.offered, args.duration,
                 args.warmup, args.seed, args.solution, args.sim_cluster,
                 args.profile_resources, checkpoint_file=args.checkpoint_file,
                 checkpoint_every=args.checkpoint_every, compact=args.compact,
                 physical_cluster=args.physical_cluster,
                 profile_scheduler=args.profile_scheduler)
    content = json.dumps(result, indent=2)
    print(content)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

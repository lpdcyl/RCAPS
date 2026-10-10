"""Offline comparison with the official workload and KV-guided admission.

Helix uses its unmodified OfflineRequestFeeder. The graph scheduler uses the
same initial count and 0.8 high watermark, with KV demand estimated from its
own assigned paths. These are end-to-end policies, not a fixed-concurrency
comparison. Lengths come from the same Azure sampler and seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import gurobipy
import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")

from experiments.graph_pipeline.evaluate import MACHINES, ROOT, _NullLogger, load_graph_layout
from experiments.queue_dag.scheduler_final import QueueAwareDagScheduler
from simulator.event_simulator.cluster_simulator import ClusterSimulator
from simulator.event_simulator.request import RequestPhase
from simulator.event_simulator.utils import AVG_OUTPUT_LEN
from simulator.initial_layout.layout_synthesizer import LayoutMethod, LayoutSynthesizer
from simulator.model_manager.model_manager import ModelName
from simulator.scheduler.base_scheduler import SchedulingMethod
from simulator.scheduler.global_maxflow.global_maxflow_scheduler import SchedulingMode
from simulator.scheduler.global_maxflow.kv_expectation import KVParameters
from simulator.trace_generator.simulator_query_feeder import OfflineRequestFeeder


ARTIFACT = {
    "single": ROOT / "artifact_evaluation/single_cluster",
    "multi": ROOT / "artifact_evaluation/distributed_clusters",
}
FINAL = {
    "single": ROOT / "experiments/critical_graph/runs/single_final",
    "multi": ROOT / "experiments/critical_graph/runs/multi_final",
}


class ObservedOfficialFeeder(OfflineRequestFeeder):
    """Record concurrency without changing Helix's admission decisions."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.peak_inflight = self.initial_query_count

    def check_launch_new_query(self, finished_request_type: RequestPhase) -> None:
        super().check_launch_new_query(finished_request_type)
        self.peak_inflight = max(
            self.peak_inflight,
            len(self.simulator.query_manager.queries_on_the_fly))


class OfflineQueueAwareDagScheduler(QueueAwareDagScheduler):
    """Expose assigned layer intervals to the workload admission controller."""

    def __init__(self, simulator):
        super().__init__(simulator)
        self.session_stages = {}

    def _route(self, request):
        stages = super()._route(request)
        self.session_stages[request.base_query_uid] = stages[:-1]
        return stages


class GraphKVFeeder(OfflineRequestFeeder):
    """Admit when estimated KV demand on every model layer is at most 80%."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.peak_inflight = self.initial_query_count
        self.peak_expected_layer_usage = 0.0

    def expected_bottleneck_usage(self) -> float:
        simulator = self.simulator
        scheduler = simulator.scheduler
        live = simulator.query_manager.queries_on_the_fly
        capacity = [0.0] * simulator.model_manager.get_num_layers()
        demand = [0.0] * len(capacity)
        for node in simulator.compute_nodes.values():
            layers = node.in_vram_model_layers
            if layers:
                per_layer = node.kv_cache_capacity / len(layers)
                for layer in layers:
                    capacity[layer] += per_layer
        for uid, query in live.items():
            stages = scheduler.session_stages.get(uid)
            if stages is None:
                # A prompt may still be waiting at the source. Its route is
                # unknown, but every layer will eventually need its KV state.
                layers = range(len(capacity))
            else:
                layers = (layer for stage in stages
                          for layer in stage.layers_to_infer)
            expected_tokens = query.input_seq_length + AVG_OUTPUT_LEN
            for layer in layers:
                demand[layer] += expected_tokens
        return max(used / size for used, size in zip(demand, capacity))

    def check_launch_new_query(self, finished_request_type: RequestPhase) -> None:
        simulator = self.simulator
        if simulator.current_time > self.start_time + self.duration:
            return
        usage = self.expected_bottleneck_usage()
        self.peak_expected_layer_usage = max(self.peak_expected_layer_usage, usage)
        if usage <= self.feed_hwm:
            input_length, output_length = self.length_sampler.sample_length()
            simulator.query_manager.issue_query(
                creation_time=simulator.current_time + 0.1,
                input_seq_length=input_length,
                output_seq_length=output_length)
            self.peak_inflight = max(
                self.peak_inflight,
                len(simulator.query_manager.queries_on_the_fly))


class CommonKVFeeder(OfflineRequestFeeder):
    """Apply identical placement-aware layer-capacity admission to both systems.

    Every live query is charged against every layer, independent of its route or
    scheduler. Capacity is the sum of available KV slots hosting that layer.
    The rule intentionally uses no scheduler-specific admission estimate.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.peak_inflight = self.initial_query_count
        self.peak_expected_layer_usage = 0.0

    def expected_bottleneck_usage(self) -> float:
        simulator = self.simulator
        layer_count = simulator.model_manager.get_num_layers()
        capacity = [0.0] * layer_count
        for node in simulator.compute_nodes.values():
            layers = node.in_vram_model_layers
            if layers:
                per_layer = node.kv_cache_capacity / len(layers)
                for layer in layers:
                    capacity[layer] += per_layer
        live = simulator.query_manager.queries_on_the_fly.values()
        expected_tokens = sum(query.input_seq_length + AVG_OUTPUT_LEN for query in live)
        return max(expected_tokens / size for size in capacity)

    def check_launch_new_query(self, finished_request_type: RequestPhase) -> None:
        simulator = self.simulator
        if simulator.current_time > self.start_time + self.duration:
            return
        usage = self.expected_bottleneck_usage()
        self.peak_expected_layer_usage = max(self.peak_expected_layer_usage, usage)
        if usage <= self.feed_hwm:
            input_length, output_length = self.length_sampler.sample_length()
            simulator.query_manager.issue_query(
                creation_time=simulator.current_time + 0.1,
                input_seq_length=input_length,
                output_seq_length=output_length)
            self.peak_inflight = max(
                self.peak_inflight,
                len(simulator.query_manager.queries_on_the_fly))


def run(scenario: str, method: str, seed: int,
        warmup: int = 60, measurement: int = 600,
        admission: str = "native") -> dict:
    if admission not in ("native", "common"):
        raise ValueError(admission)
    base = ARTIFACT[scenario]
    config = base / "config" / ("cluster24.ini" if scenario == "single"
                                else "3cluster24.ini")
    profile = base / "config/machine_profiles.ini"
    placement = (base / "layout_llama70b/ilp" if method == "helix"
                 else FINAL[scenario])
    solution = placement / ("ilp_sol.ini" if method == "helix" else "solution.ini")
    cluster = placement / "simulator_cluster.ini"
    layout = None
    if method == "helix":
        layout = LayoutSynthesizer(str(config), str(profile), ModelName.LLaMa70B,
                                   str(base / "tmp"), LayoutMethod.LoadExisting,
                                   MACHINES)
        layout.synthesize({"solution_file_name": str(solution),
                           "simulator_cluster_file_name": str(cluster)})
    simulator = ClusterSimulator(model_name=ModelName.LLaMa70B,
                                 machine_num_dict=MACHINES)
    simulator.logger = _NullLogger()
    simulator.from_ini_file(config_file_name=str(cluster))
    if method == "helix":
        simulator.init_scheduler(SchedulingMethod.MaxFlow, {
            "kv_param": KVParameters(expected_kv_hwm=0.85,
                                     expected_output_length_ratio=1),
            "scheduling_mode": SchedulingMode.Offline})
    else:
        simulator.set_scheduler(OfflineQueueAwareDagScheduler(simulator))
    simulator.init_query_manager()
    simulator.mark_as_ready()
    start = (layout.set_layout(simulator) if method == "helix" else
             load_graph_layout(simulator, solution))
    if method == "helix":
        simulator.update_scheduler()
    feeder_type = (CommonKVFeeder if admission == "common" else
                   ObservedOfficialFeeder if method == "helix" else GraphKVFeeder)
    feeder = feeder_type(initial_query_count=20, start_time=start,
                         duration=warmup + measurement,
                         stop_at_duration=True, feed_hwm=0.8, seed=seed)
    feeder.auto_simulate(simulator=simulator)
    beginning, ending = start + warmup, start + warmup + measurement
    finished = [(time, request) for time, request in
                simulator.finished_requests.values() if beginning <= time <= ending]
    decode = [request for _, request in finished
              if request.phase == RequestPhase.Increment]
    prompt = [request for _, request in finished
              if request.phase == RequestPhase.Initialization]
    prompt_latency = sorted(request.location_history[-1][1] -
                            request.location_history[0][1] for request in prompt)
    decode_latency = sorted(request.location_history[-1][1] -
                            request.location_history[0][1] for request in decode)
    def p95(values: list[float]) -> float | None:
        return values[int(len(values) * 0.95)] if values else None
    return {
        "scenario": scenario, "method": method, "seed": seed,
        "workload": ("offline_common_kv" if admission == "common" else
                     "offline_kv_guided"), "warmup_s": warmup,
        "measurement_s": measurement,
        "admission_rule": admission,
        "decode_throughput_tokens_per_s": sum(req.token_seq_length for req in decode) / measurement,
        "paper_prompt_request_p95_s": p95(prompt_latency),
        "paper_decode_request_p95_s": p95(decode_latency),
        "prompt_request_count": len(prompt), "decode_request_count": len(decode),
        "finished_queries_total": len(simulator.query_manager.finished_queries),
        "issued_queries_total": (len(simulator.query_manager.finished_queries) +
                                 len(simulator.query_manager.queries_on_the_fly)),
        "active_queries_at_end": len(simulator.query_manager.queries_on_the_fly),
        "peak_inflight": feeder.peak_inflight,
        "peak_expected_layer_usage": (feeder.peak_expected_layer_usage
                                      if isinstance(feeder, (GraphKVFeeder, CommonKVFeeder))
                                      else None),
        "solution": str(solution), "sim_cluster": str(cluster),
        "solution_sha256": hashlib.sha256(solution.read_bytes()).hexdigest(),
        "sim_cluster_sha256": hashlib.sha256(cluster.read_bytes()).hexdigest(),
        "python_version": sys.version.split()[0], "numpy_version": np.__version__,
        "gurobi_version": ".".join(map(str, gurobipy.gurobi.version())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    parser.add_argument("--method", choices=("helix", "integrated"), required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--measurement", type=int, default=600)
    parser.add_argument("--admission", choices=("native", "common"), default="native")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmup < 0 or args.measurement <= 0:
        parser.error("--measurement must be positive; --warmup cannot be negative")
    if gurobipy.gurobi.version()[0] != 13:
        parser.error("Gurobi 13 is required")
    result = run(args.scenario, args.method, args.seed,
                 args.warmup, args.measurement, args.admission)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""Run independent layer-DAG method or the unmodified Helix baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

import numpy as np

from simulator.event_simulator.cluster_simulator import ClusterSimulator
from simulator.event_simulator.request import RequestPhase
from simulator.model_manager.model_manager import ModelName
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
from experiments.graph_pipeline.scheduler import LayerDagScheduler
from benchmarks.layout import MACHINES, ROOT, _NullLogger, load_graph_layout, scenario

def p95(values):
    return float(np.percentile(values, 95)) if values else None


def run(name, method, offered, duration, warmup, seed, solution=None, sim_cluster=None,
        queue_weight=0.03, session_weight=0.012, decode_priority=True,
        no_event_log=False):
    cluster, profile, helix_solution, helix_sim_cluster = scenario(name)
    solution = Path(solution) if solution else helix_solution
    sim_cluster = Path(sim_cluster) if sim_cluster else helix_sim_cluster
    layout = None
    if method == "helix":
        from simulator.initial_layout.layout_synthesizer import LayoutMethod, LayoutSynthesizer
        layout = LayoutSynthesizer(str(cluster), str(profile), ModelName.LLaMa70B,
                                   str(ROOT / "experiments/graph_pipeline/runs"),
                                   LayoutMethod.LoadExisting, MACHINES)
        layout.synthesize({"solution_file_name": str(solution),
                           "simulator_cluster_file_name": str(sim_cluster)})
    simulator = ClusterSimulator(model_name=ModelName.LLaMa70B, machine_num_dict=MACHINES)
    if no_event_log:
        simulator.logger = _NullLogger()
    simulator.from_ini_file(config_file_name=str(sim_cluster))
    if method == "helix":
        from simulator.scheduler.base_scheduler import SchedulingMethod
        from simulator.scheduler.global_maxflow.global_maxflow_scheduler import SchedulingMode
        from simulator.scheduler.global_maxflow.kv_expectation import KVParameters
        simulator.init_scheduler(SchedulingMethod.MaxFlow, {
            "kv_param": KVParameters(expected_kv_hwm=0.9, expected_output_length_ratio=0.6),
            "scheduling_mode": SchedulingMode.Online})
    else:
        simulator.set_scheduler(LayerDagScheduler(simulator, queue_weight, session_weight,
                                                 decode_priority))
    simulator.init_query_manager()
    simulator.mark_as_ready()
    start = layout.set_layout(simulator) if method == "helix" else load_graph_layout(simulator, solution)
    if method == "helix":
        simulator.update_scheduler()
    feeder = OnlineRequestFeeder(cluster_token_throughput=offered,
                                 start_time=start, duration=duration, seed=seed)
    feeder.auto_simulate(simulator=simulator)
    beginning, ending = start + warmup, start + duration
    window = duration - warmup
    output_tokens = sum(req.token_seq_length for t, req in simulator.finished_requests.values()
                        if req.phase == RequestPhase.Increment and beginning <= t < ending)
    completions = sum(beginning <= t < ending for t, _ in simulator.query_manager.finished_queries.values())
    first_tokens, tpots, e2es = [], [], []
    for finish, query in simulator.query_manager.finished_queries.values():
        if not beginning <= query.creation_time < ending:
            continue
        decode_ends = [entry.end_time for entry in query.inference_history[1:]
                       if entry.end_time <= ending]
        if decode_ends:
            first_tokens.append(decode_ends[0] - query.creation_time)
        if len(decode_ends) >= 2:
            tpots.append(mean(b - a for a, b in zip(decode_ends, decode_ends[1:])))
        if finish <= ending:
            e2es.append(finish - query.creation_time)
    arrivals = sum(beginning <= t < ending for t, _, _ in feeder.trace)
    finished = [query for _, query in simulator.query_manager.finished_queries.values()]
    def backlog(at):
        return sum(q.creation_time <= at < q.inference_history[-1].end_time for q in finished)
    result = {
        "scenario": name, "method": method, "solution": str(solution),
        "offered_tokens_per_s": offered, "duration_s": duration, "warmup_s": warmup,
        "seed": seed, "arrivals": arrivals,
        "completed_request_throughput_per_s": completions / window,
        "output_throughput_tokens_per_s": output_tokens / window,
        "ttft_p95_s": p95(first_tokens), "tpot_p95_s": p95(tpots),
        "e2e_p95_s": p95(e2es), "completion_fraction": len(e2es) / arrivals if arrivals else None,
        "backlog_at_window_start": backlog(beginning), "backlog_at_window_end": backlog(ending),
        "first_tokens_in_window": len(first_tokens), "queries_with_tpot_samples": len(tpots),
    }
    if method == "graph":
        from collections import Counter
        paths = Counter(tuple(stage.node_uid for stage in query.inference_history[0].path[:-1])
                        for query in finished if query.inference_history)
        result["path_counts"] = [{"nodes": list(path), "queries": count}
                                 for path, count in paths.most_common()]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["single", "multi"], required=True)
    parser.add_argument("--method", choices=["graph", "helix"], default="graph")
    parser.add_argument("--solution", type=Path)
    parser.add_argument("--sim-cluster", type=Path)
    parser.add_argument("--offered", type=float, required=True)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--warmup", type=int, default=180)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--queue-weight", type=float, default=0.03)
    parser.add_argument("--session-weight", type=float, default=0.012)
    parser.add_argument("--fifo", action="store_true")
    parser.add_argument("--no-event-log", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.scenario, args.method, args.offered, args.duration, args.warmup,
                 args.seed, args.solution, args.sim_cluster, args.queue_weight,
                 args.session_weight, not args.fifo, args.no_event_log)
    content = json.dumps(result, indent=2)
    print(content)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

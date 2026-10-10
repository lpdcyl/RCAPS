"""Search the original local neighborhood with a queue-aware resource proxy."""

from __future__ import annotations

import argparse
import copy
import json
import time
from heapq import heappop, heappush
from pathlib import Path

from rcaps.placement.partition import (boundary_moves, initial_partition, save,
                                       scenario, topology_groups)
from rcaps.placement.queue_predictor import QueuePrediction, predict
from rcaps.placement.topology import GraphMetrics, TopologyModel


HERE = Path(__file__).resolve().parent
LOADS = {"single": 700.0, "multi": 320.0}


def objective(graph: GraphMetrics, queue: QueuePrediction,
              reference: tuple[GraphMetrics, QueuePrediction]) -> float:
    base_graph, base_queue = reference
    return (0.40 * graph.ttft_s / base_graph.ttft_s +
            0.35 * graph.tpot_s / base_graph.tpot_s +
            0.25 * queue.max_queue_pressure / base_queue.max_queue_pressure)


def measure(model: TopologyModel, state: dict, load: float,
            mode: str, *, service_mode: str = "legacy") -> tuple[GraphMetrics, QueuePrediction]:
    return model.measure(state, demand_mode=mode), predict(
        model, state, load, service_mode=service_mode)


def refine_queue(model: TopologyModel, initial: dict, load: float,
                 *, max_steps: int = 16, service_mode: str = "legacy") -> tuple[dict, list[dict]]:
    state = copy.deepcopy(initial)
    mode = "ensemble" if len(topology_groups(model)) == 1 else "canonical"
    reference = measure(model, state, load, mode, service_mode=service_mode)
    current = reference
    current_score = objective(*current, reference)
    started = time.perf_counter()
    evaluations = 0
    trace = [{"step": 0, "move": "coarse partition", "score": current_score,
              "demand_mode": "queue_flow", "event_demand_mode": mode,
              "service_mode": service_mode,
              "search_mode": "full", "offered_tokens_per_s": load,
              "ttft_s": current[0].ttft_s, "tpot_s": current[0].tpot_s,
              "max_queue_pressure": current[1].max_queue_pressure,
              "predicted_top_gpu": max(current[1].gpu_queue_pressure,
                                       key=current[1].gpu_queue_pressure.get)}]
    for step in range(1, max_steps + 1):
        gains = []
        for sequence, (move, candidate) in enumerate(
                boundary_moves(state, model, None, guided=False)):
            evaluations += 1
            try:
                candidate_graph, candidate_queue = measure(
                    model, candidate, load, mode, service_mode=service_mode)
            except ValueError:
                continue
            candidate_score = objective(candidate_graph, candidate_queue, reference)
            gain = current_score - candidate_score
            if gain > 1e-9:
                heappush(gains, (-gain, sequence, move, candidate,
                                 candidate_graph, candidate_queue))
        if not gains:
            break
        neg_gain, _, move, state, graph, queue = heappop(gains)
        current = graph, queue
        current_score += neg_gain
        trace.append({"step": step, "move": move, "gain": -neg_gain,
                      "score": current_score, "ttft_s": graph.ttft_s,
                      "tpot_s": graph.tpot_s,
                      "max_queue_pressure": queue.max_queue_pressure,
                      "predicted_top_gpu": max(queue.gpu_queue_pressure,
                                               key=queue.gpu_queue_pressure.get)})
    trace[0]["candidate_evaluations"] = evaluations
    trace[0]["planning_s"] = time.perf_counter() - started
    return state, trace


def generate(name: str, *, max_steps: int = 16) -> dict:
    physical, template = scenario(name)
    model = TopologyModel(physical)
    initial = initial_partition(model)
    state, trace = refine_queue(model, initial, LOADS[name], max_steps=max_steps)
    destination = HERE / "layouts" / name
    result = save(model, template, state, destination, trace,
                  algorithm="queue-flow resource prediction with full-neighborhood search")
    prediction = predict(model, state, LOADS[name])
    (destination / "queue_prediction.json").write_text(
        json.dumps({"offered_tokens_per_s": LOADS[name],
                    "gpu_visit_probability": prediction.gpu_visit_probability,
                    "gpu_utilization": prediction.gpu_utilization,
                    "gpu_wait_s": prediction.gpu_wait_s,
                    "gpu_queue_pressure": prediction.gpu_queue_pressure,
                    "link_utilization": prediction.link_utilization,
                    "link_wait_s": prediction.link_wait_s,
                    "max_queue_pressure": prediction.max_queue_pressure,
                    "mean_route_cost_s": prediction.mean_route_cost_s,
                    "iterations": prediction.iterations}, indent=2) + "\n",
        encoding="utf-8")
    return {"scenario": name, "steps": len(trace) - 1,
            "candidate_evaluations": trace[0]["candidate_evaluations"],
            "planning_s": trace[0]["planning_s"],
            "initial_score": trace[0]["score"],
            "final_score": trace[-1]["score"],
            "solution": result["solution"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=LOADS, required=True)
    parser.add_argument("--max-steps", type=int, default=16)
    args = parser.parse_args()
    print(json.dumps(generate(args.scenario, max_steps=args.max_steps), indent=2))


if __name__ == "__main__":
    main()

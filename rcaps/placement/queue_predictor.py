"""Analytic queue-aware route flow for an ordered-layer placement.

The predictor sees only the candidate layout, physical profiles, and offered
load. It never reads simulator queue profiles or evaluation traces. A soft
path-flow pass is alternated with M/G/1 waiting estimates so route choice and
resource pressure influence each other. This is an approximation of the
online scheduler, not a claim that its queue lengths are exact.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from functools import lru_cache
from math import exp
from pathlib import Path

from .path_ensemble import logadd
from .topology import TopologyModel, profile_at


@dataclass(frozen=True)
class Edge:
    left: str | int
    right: str | int
    link: str
    route_cost_s: float
    compute_work_s: float
    link_work_s: float


@dataclass(frozen=True)
class QueuePrediction:
    gpu_visit_probability: dict[int, float]
    gpu_utilization: dict[int, float]
    gpu_wait_s: dict[int, float]
    gpu_queue_pressure: dict[int, float]
    link_utilization: dict[str, float]
    link_wait_s: dict[str, float]
    max_queue_pressure: float
    mean_route_cost_s: float
    iterations: int


@lru_cache(maxsize=1)
def workload_means() -> tuple[float, float]:
    folder = Path(__file__).resolve().parents[2] / "simulator/trace_generator/length_data"
    with (folder / "azure_conv_input.pkl").open("rb") as stream:
        inputs = pickle.load(stream)
    with (folder / "azure_conv_output.pkl").open("rb") as stream:
        outputs = pickle.load(stream)
    return sum(inputs) / len(inputs), sum(outputs) / len(outputs)


def edges_for(model: TopologyModel, state: dict,
              input_tokens: float, output_tokens: float,
              *, service_mode: str = "legacy") -> tuple[list[str | int], list[Edge]]:
    if service_mode not in ("legacy", "phase"):
        raise ValueError(f"Unknown service mode: {service_mode}")
    spans = model.intervals(state)
    nodes: list[str | int] = ["source", *sorted(spans,
                                                key=lambda node: (spans[node][1], node)),
                              "sink"]
    token_size = model.manager.get_model_token_size()
    activation = model.manager.get_model_activation_size()
    edges: list[Edge] = []
    for left in nodes[:-1]:
        boundary = 0 if left == "source" else spans[left][1]
        if left == "source":
            destinations: list[str | int] = [state["shared"]]
        else:
            destinations = [right for right, (start, end) in spans.items()
                            if right != left and start <= boundary < end]
            if boundary == model.layers:
                destinations.append("sink")
        for right in destinations:
            latency, bandwidth = model.link(left, right)
            payload = token_size if left == "source" or right == "sink" else token_size + activation
            link_route = latency + input_tokens * payload / bandwidth
            link_work = (input_tokens + output_tokens) * payload / bandwidth
            compute_route = compute_work = 0.0
            if right != "sink":
                length = spans[right][1] - boundary
                profile = model.profiles[model.types[right]]
                prompt = length * profile_at(profile.prompt_bs2time,
                                             round(input_tokens))
                # The profiling table gives the duration of a batch; divide
                # its decode duration by the typical batch occupancy.
                decode_token = length * profile_at(profile.decode_bs2time,
                                                   model.decode_batch) / model.decode_batch
                compute_route = prompt + decode_token
                if service_mode == "phase":
                    # One prompt pass, then one batched decode pass per
                    # generated token. The legacy max-times-total convention
                    # counts the expensive decode unit cost for input tokens.
                    compute_work = prompt + output_tokens * decode_token
                else:
                    # Preserve the prior experiment exactly for reproduction.
                    compute_work = (input_tokens + output_tokens) * max(
                        prompt / input_tokens, decode_token)
            edges.append(Edge(left, right, f"{left}->{right}",
                              link_route + compute_route, compute_work, link_work))
    return nodes, edges


def route_flow(nodes: list[str | int], edges: list[Edge],
               gpu_wait: dict[int, float], link_wait: dict[str, float],
               temperature_s: float) -> tuple[list[float], float]:
    outgoing: dict[str | int, list[tuple[int, float]]] = {node: [] for node in nodes}
    for index, edge in enumerate(edges):
        penalty = link_wait.get(edge.link, 0.0)
        if edge.right != "sink":
            penalty += gpu_wait.get(edge.right, 0.0)
        outgoing[edge.left].append((index, (edge.route_cost_s + penalty) / temperature_s))
    forward = {node: float("-inf") for node in nodes}
    forward["source"] = 0.0
    for left in nodes[:-1]:
        for index, cost in outgoing[left]:
            right = edges[index].right
            forward[right] = logadd(forward[right], forward[left] - cost)
    if forward["sink"] == float("-inf"):
        raise ValueError("No complete source-to-sink route")
    backward = {node: float("-inf") for node in nodes}
    backward["sink"] = 0.0
    for left in reversed(nodes[:-1]):
        for index, cost in outgoing[left]:
            backward[left] = logadd(backward[left],
                                    -cost + backward[edges[index].right])
    probabilities = [0.0] * len(edges)
    mean_cost = 0.0
    for left in nodes[:-1]:
        for index, cost in outgoing[left]:
            edge = edges[index]
            probability = exp(forward[left] - cost + backward[edge.right] -
                              forward["sink"])
            probabilities[index] = probability
            mean_cost += probability * edge.route_cost_s
    return probabilities, mean_cost


def waits_from_flow(edges: list[Edge], probabilities: list[float],
                    arrival_rate: float, nodes: dict[int, str]
                    ) -> tuple[dict[int, float], dict[int, float], dict[int, float],
                               dict[str, float], dict[str, float]]:
    visits = {node: 0.0 for node in nodes}
    gpu_first = {node: 0.0 for node in nodes}
    gpu_second = {node: 0.0 for node in nodes}
    link_first: dict[str, float] = {}
    link_second: dict[str, float] = {}
    for edge, probability in zip(edges, probabilities):
        if edge.right != "sink":
            visits[edge.right] += probability
            gpu_first[edge.right] += probability * edge.compute_work_s
            gpu_second[edge.right] += probability * edge.compute_work_s ** 2
        link_first[edge.link] = link_first.get(edge.link, 0.0) + probability * edge.link_work_s
        link_second[edge.link] = (link_second.get(edge.link, 0.0) +
                                  probability * edge.link_work_s ** 2)
    gpu_util = {node: arrival_rate * first for node, first in gpu_first.items()}
    link_util = {link: arrival_rate * first for link, first in link_first.items()}
    # M/G/1 queue approximation. The denominator floor prevents runaway
    # penalties from making the fixed-point flow numerically unstable.
    gpu_wait = {node: min(30.0, arrival_rate * gpu_second[node] /
                          (2 * max(0.05, 1 - gpu_util[node]))) for node in nodes}
    link_wait = {link: min(30.0, arrival_rate * link_second[link] /
                            (2 * max(0.05, 1 - link_util[link]))) for link in link_first}
    return visits, gpu_util, gpu_wait, link_util, link_wait


def predict(model: TopologyModel, state: dict, offered_tokens_per_s: float,
            *, temperature_s: float = 0.2, iterations: int = 96,
            service_mode: str = "legacy") -> QueuePrediction:
    if offered_tokens_per_s <= 0 or temperature_s <= 0 or iterations < 1:
        raise ValueError("Positive load, temperature and iteration count required")
    input_tokens, output_tokens = workload_means()
    arrival_rate = offered_tokens_per_s / (input_tokens + output_tokens)
    nodes, edges = edges_for(model, state, input_tokens, output_tokens,
                             service_mode=service_mode)
    probabilities, _ = route_flow(nodes, edges, {}, {}, temperature_s)
    # Method of successive averages avoids the two-branch oscillation caused
    # by directly feeding a congested branch's wait into the next softmax.
    for iteration in range(iterations):
        _, _, gpu_wait, _, link_wait = waits_from_flow(
            edges, probabilities, arrival_rate, model.types)
        target, _ = route_flow(nodes, edges, gpu_wait, link_wait,
                               temperature_s)
        step = 1 / (iteration + 2)
        probabilities = [(1 - step) * old + step * new
                         for old, new in zip(probabilities, target)]
    mean_cost = sum(probability * edge.route_cost_s
                    for probability, edge in zip(probabilities, edges))
    visits, gpu_util, final_gpu_wait, link_util, final_link_wait = waits_from_flow(
        edges, probabilities, arrival_rate, model.types)
    queue_pressure = {node: arrival_rate * visits[node] * final_gpu_wait[node]
                      for node in model.types}
    return QueuePrediction(visits, gpu_util, final_gpu_wait, queue_pressure,
                           link_util, final_link_wait,
                           max(queue_pressure.values()), mean_cost, iterations)

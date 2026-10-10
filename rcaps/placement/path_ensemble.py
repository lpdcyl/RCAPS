"""Soft shortest-path flow on the layer-compatibility DAG.

Forward/backward log-sum-exp passes assign a probability to every compatible
source-to-sink path without enumerating paths. Edge marginals capture the fact
that routes assembled from different canonical branches can merge at a GPU.
The resulting node demand is an explanatory traffic proxy, not a scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

from .topology import TopologyModel, profile_at


def logadd(a: float, b: float) -> float:
    if a == float("-inf"):
        return b
    if b == float("-inf"):
        return a
    high, low = max(a, b), min(a, b)
    return high + log(1 + exp(low - high))


@dataclass(frozen=True)
class EnsembleResult:
    gpu_demand_s: dict[int, float]
    gpu_visit_probability: dict[int, float]
    link_demand_s: dict[str, float]
    edge_probability: dict[str, float]
    mean_prefill_cost_s: float


def measure(model: TopologyModel, state: dict, *, temperature_s: float = 0.2
            ) -> EnsembleResult:
    if temperature_s <= 0:
        raise ValueError("Temperature must be positive")
    spans = model.intervals(state)
    source, sink = "source", "sink"
    nodes: list[str | int] = [source, *sorted(spans,
                                             key=lambda node: (spans[node][1], node)), sink]
    token_size = model.manager.get_model_token_size()
    activation = model.manager.get_model_activation_size()
    edges: dict[str | int, list[tuple[str | int, float, float, float, float]]] = {
        node: [] for node in nodes}
    for left in nodes[:-1]:
        if left == source:
            destinations = [state["shared"]]
            end_left = 0
        else:
            end_left = spans[left][1]
            destinations = [right for right in spans if right != left and
                            spans[right][0] <= end_left < spans[right][1]]
            if end_left == model.layers:
                destinations.append(sink)
        for right in destinations:
            latency, bandwidth = model.link(left, right)
            payload = (token_size if left == source or right == sink
                       else token_size + activation)
            if right == sink:
                compute_s = decode_s = 0.0
            else:
                layers = spans[right][1] - end_left
                profile = model.profiles[model.types[right]]
                compute_s = layers * profile_at(profile.prompt_bs2time,
                                                model.prompt_tokens)
                decode_s = layers * profile_at(profile.decode_bs2time,
                                               model.decode_batch)
            prefill_cost = latency + model.prompt_tokens * payload / bandwidth + compute_s
            edges[left].append((right, prefill_cost, compute_s, decode_s,
                                payload / bandwidth))
    forward = {node: float("-inf") for node in nodes}
    forward[source] = 0.0
    for left in nodes[:-1]:
        for right, cost, _, _, _ in edges[left]:
            forward[right] = logadd(forward[right], forward[left] - cost / temperature_s)
    if forward[sink] == float("-inf"):
        raise ValueError("No complete source-to-sink layer route")
    backward = {node: float("-inf") for node in nodes}
    backward[sink] = 0.0
    for left in reversed(nodes[:-1]):
        for right, cost, _, _, _ in edges[left]:
            backward[left] = logadd(backward[left],
                                    -cost / temperature_s + backward[right])
    gpu_demand = {node: 0.0 for node in spans}
    visits = {node: 0.0 for node in spans}
    link_demand: dict[str, float] = {}
    edge_probability: dict[str, float] = {}
    mean_prefill = 0.0
    for left in nodes[:-1]:
        for right, cost, prefill_s, decode_s, link_s in edges[left]:
            probability = exp(forward[left] - cost / temperature_s +
                              backward[right] - forward[sink])
            label = f"{left}->{right}"
            edge_probability[label] = probability
            link_demand[label] = probability * link_s
            mean_prefill += probability * cost
            if right != sink:
                per_token_service = max(prefill_s / model.prompt_tokens,
                                        decode_s / model.decode_batch)
                gpu_demand[right] += probability * per_token_service
                visits[right] += probability
    return EnsembleResult(gpu_demand, visits, link_demand,
                          edge_probability, mean_prefill)

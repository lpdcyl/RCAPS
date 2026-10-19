"""Deterministic chain construction primitives for V3 M2 search."""

from __future__ import annotations

from .topology import TopologyModel, profile_at


def has_link(model: TopologyModel, left: str | int, right: str | int) -> bool:
    return (f"Link-{left}-{right}" in model.config or
            f"Link-{right}-{left}" in model.config)


def link_cost(model: TopologyModel, left: str | int, right: str | int) -> float:
    if not has_link(model, left, right):
        return float("inf")
    latency, bandwidth = model.link(left, right)
    return latency + model.manager.get_model_activation_size() / bandwidth


def route_order(model: TopologyModel, nodes: tuple[int, ...] | list[int],
                previous: str | int, *, terminal: bool = True) -> list[int] | None:
    pending = set(nodes)
    result = []
    while pending:
        node = min(pending, key=lambda item: (link_cost(model, previous, item),
                                               -model.capacity[item], item))
        if not has_link(model, previous, node):
            return None
        result.append(node)
        pending.remove(node)
        previous = node
    return result if not terminal or has_link(model, previous, "sink") else None


def allocate(model: TopologyModel, nodes: list[int], total: int) -> dict[int, int] | None:
    if not nodes or len(nodes) > total or sum(model.capacity[n] for n in nodes) < total:
        return None
    lengths = {node: 1 for node in nodes}
    costs = {}
    for node in nodes:
        profile = model.profiles[model.types[node]]
        costs[node] = (0.4 * profile_at(profile.prompt_bs2time, model.prompt_tokens) +
                       0.35 * profile_at(profile.decode_bs2time, model.decode_batch))
    for _ in range(total - len(nodes)):
        node = min((n for n in nodes if lengths[n] < model.capacity[n]),
                   key=lambda n: ((lengths[n] + 1) * costs[n], n), default=None)
        if node is None:
            return None
        lengths[node] += 1
    return lengths

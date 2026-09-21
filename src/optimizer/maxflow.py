"""Maximum-flow solving and mathematical invariant checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import networkx as nx

from src.graph.serving_graph import SINK, SOURCE, ServingGraph


Edge = tuple[str, str]


class MaxFlowValidationError(RuntimeError):
    """Raised when a solved flow violates a required mathematical invariant."""


@dataclass(frozen=True, slots=True)
class MaxFlowResult:
    """Validated maximum-flow and minimum-cut results."""

    max_flow_value: float
    min_cut_value: float
    positive_flow_edges: Mapping[Edge, float]
    cut_edges: Mapping[Edge, float]
    edge_capacities: Mapping[Edge, float]
    edge_utilization: Mapping[Edge, float]
    edge_types: Mapping[Edge, str]
    conservation_check: bool
    capacity_constraints_check: bool
    max_flow_min_cut_check: bool


def _flatten_flow(flow_dict: Mapping[str, Mapping[str, float]]) -> dict[Edge, float]:
    return {
        (source, target): float(flow)
        for source, outgoing in flow_dict.items()
        for target, flow in outgoing.items()
    }


def _check_capacity_constraints(
    edge_capacities: Mapping[Edge, float],
    edge_flows: Mapping[Edge, float],
    tolerance: float,
) -> bool:
    for edge, capacity in edge_capacities.items():
        flow = edge_flows.get(edge, 0.0)
        if flow < -tolerance or flow > capacity + tolerance:
            return False
    return True


def _check_flow_conservation(
    graph: nx.DiGraph,
    edge_flows: Mapping[Edge, float],
    tolerance: float,
) -> bool:
    for node in graph.nodes:
        if node in {SOURCE, SINK}:
            continue
        inflow = sum(edge_flows.get((source, node), 0.0) for source in graph.predecessors(node))
        outflow = sum(edge_flows.get((node, target), 0.0) for target in graph.successors(node))
        if abs(inflow - outflow) > tolerance:
            return False
    return True


def solve_max_flow(
    serving_graph: ServingGraph, *, tolerance: float = 1e-9
) -> MaxFlowResult:
    """Solve max-flow/min-cut and fail if any mathematical invariant is violated."""

    graph = serving_graph.graph
    max_flow_value, flow_dict = nx.maximum_flow(
        graph,
        SOURCE,
        SINK,
        capacity="capacity",
        flow_func=nx.algorithms.flow.edmonds_karp,
    )
    min_cut_value, partition = nx.minimum_cut(
        graph,
        SOURCE,
        SINK,
        capacity="capacity",
        flow_func=nx.algorithms.flow.edmonds_karp,
    )
    reachable, non_reachable = partition

    edge_capacities: dict[Edge, float] = {
        (source, target): float(data["capacity"])
        for source, target, data in graph.edges(data=True)
    }
    edge_types: dict[Edge, str] = {
        (source, target): str(data["edge_type"])
        for source, target, data in graph.edges(data=True)
    }
    edge_flows = _flatten_flow(flow_dict)
    positive_flow_edges = {
        edge: flow for edge, flow in edge_flows.items() if flow > tolerance
    }
    cut_edges = {
        (source, target): float(data["capacity"])
        for source, target, data in graph.edges(data=True)
        if source in reachable and target in non_reachable
    }
    edge_utilization = {
        edge: edge_flows.get(edge, 0.0) / capacity
        for edge, capacity in edge_capacities.items()
    }

    capacity_ok = _check_capacity_constraints(
        edge_capacities, edge_flows, tolerance
    )
    conservation_ok = _check_flow_conservation(graph, edge_flows, tolerance)
    theorem_ok = abs(max_flow_value - min_cut_value) <= tolerance

    if not capacity_ok:
        raise MaxFlowValidationError("Solved flow violates an edge capacity constraint")
    if not conservation_ok:
        raise MaxFlowValidationError("Solved flow violates flow conservation")
    if not theorem_ok:
        raise MaxFlowValidationError(
            "Maximum-flow value does not equal minimum-cut capacity"
        )

    return MaxFlowResult(
        max_flow_value=float(max_flow_value),
        min_cut_value=float(min_cut_value),
        positive_flow_edges=dict(sorted(positive_flow_edges.items())),
        cut_edges=dict(sorted(cut_edges.items())),
        edge_capacities=dict(sorted(edge_capacities.items())),
        edge_utilization=dict(sorted(edge_utilization.items())),
        edge_types=dict(sorted(edge_types.items())),
        conservation_check=True,
        capacity_constraints_check=True,
        max_flow_min_cut_check=True,
    )

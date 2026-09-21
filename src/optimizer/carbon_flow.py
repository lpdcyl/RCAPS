"""Carbon-aware minimum-cost flow for a fixed logical serving graph."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping

import networkx as nx
import numpy as np
from scipy.optimize import linprog

from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import SINK, SOURCE, ServingGraph, gpu_in_node, gpu_out_node
from src.optimizer.maxflow import Edge, MaxFlowResult


class CarbonFlowOptimizationError(RuntimeError):
    """Raised when the LP is infeasible or a returned flow is invalid."""


# Carbon coefficients in g/token are around 1e-7 in this toy setup. Scaling the
# entire objective preserves the optimizer while keeping HiGHS well above its
# numerical feasibility tolerances.
OBJECTIVE_SCALE = 1_000_000_000.0


@dataclass(frozen=True, slots=True)
class FlowCarbonMetrics:
    """Carbon accounting and path decomposition for one fixed-throughput flow."""

    throughput: float
    carbon_g_per_second: float
    carbon_g_per_1000_tokens: float
    positive_flow_edges: Mapping[Edge, float]
    gpu_flow_tokens_per_second: Mapping[str, float]
    region_token_flow: Mapping[str, float]
    region_flow_share: Mapping[str, float]
    cross_region_flow_tokens_per_second: float
    cross_region_flow_fraction: float
    path_flow_tokens_per_second: Mapping[str, float]
    path_flow_share: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class CarbonFlowResult:
    """Validated optimum of the fixed-placement carbon-aware flow LP."""

    throughput_target: float
    metrics: FlowCarbonMetrics
    edge_capacities: Mapping[Edge, float]
    edge_carbon_cost_g_per_token: Mapping[Edge, float]
    solver_time_seconds: float
    solver_status: str
    capacity_constraints_check: bool
    conservation_check: bool
    throughput_check: bool


def _gpu_id_for_compute_edge(edge: Edge, carbon_model: CarbonCostModel) -> str | None:
    for gpu_id in carbon_model.gpu_costs:
        if edge == (gpu_in_node(gpu_id), gpu_out_node(gpu_id)):
            return gpu_id
    return None


def _find_positive_path(
    graph: nx.DiGraph,
    remaining: Mapping[Edge, float],
    node: str,
    tolerance: float,
    visited: set[str],
) -> list[str] | None:
    if node == SINK:
        return [SINK]
    visited.add(node)
    for target in sorted(graph.successors(node)):
        if target in visited or remaining.get((node, target), 0.0) <= tolerance:
            continue
        suffix = _find_positive_path(
            graph, remaining, target, tolerance, visited.copy()
        )
        if suffix is not None:
            return [node, *suffix]
    return None


def decompose_flow_paths(
    graph: nx.DiGraph,
    positive_flow_edges: Mapping[Edge, float],
    *,
    tolerance: float = 1e-9,
) -> dict[str, float]:
    """Deterministically decompose an acyclic serving flow into GPU paths."""

    remaining = dict(positive_flow_edges)
    path_flows: dict[str, float] = {}
    while sum(
        remaining.get((SOURCE, target), 0.0)
        for target in graph.successors(SOURCE)
    ) > tolerance:
        path = _find_positive_path(graph, remaining, SOURCE, tolerance, set())
        if path is None:
            raise CarbonFlowOptimizationError(
                "Positive source flow could not be decomposed into a sink path"
            )
        edges = list(zip(path, path[1:]))
        path_flow = min(remaining[edge] for edge in edges)
        gpu_ids = [
            source.removesuffix("_in")
            for source, target in edges
            if graph[source][target]["edge_type"] == "compute"
        ]
        path_name = "->".join(gpu_ids)
        path_flows[path_name] = path_flows.get(path_name, 0.0) + path_flow
        for edge in edges:
            remaining[edge] -= path_flow
    return dict(sorted(path_flows.items()))


def evaluate_flow_carbon(
    serving_graph: ServingGraph,
    flow_edges: Mapping[Edge, float],
    carbon_model: CarbonCostModel,
    throughput: float,
    *,
    tolerance: float = 1e-9,
) -> FlowCarbonMetrics:
    """Evaluate carbon and path shares for a validated fixed-throughput flow."""

    positive = {
        edge: float(flow) for edge, flow in flow_edges.items() if flow > tolerance
    }
    gpu_flow: dict[str, float] = {}
    carbon_rate = 0.0
    for edge, flow in positive.items():
        gpu_id = _gpu_id_for_compute_edge(edge, carbon_model)
        if gpu_id is None:
            continue
        gpu_flow[gpu_id] = flow
        carbon_rate += flow * carbon_model.carbon_g_per_token(gpu_id)
    region_flow = {
        region: sum(
            flow
            for gpu_id, flow in gpu_flow.items()
            if carbon_model.gpu_costs[gpu_id].region == region
        )
        for region in sorted(
            {cost.region for cost in carbon_model.gpu_costs.values()}
        )
    }
    total_compute_flow = sum(region_flow.values())
    region_share = {
        region: (flow / total_compute_flow if total_compute_flow > tolerance else 0.0)
        for region, flow in region_flow.items()
    }
    cross_region_flow = 0.0
    for edge, flow in positive.items():
        source, target = edge
        if serving_graph.graph[source][target]["edge_type"] != "network":
            continue
        source_gpu = source.removesuffix("_out")
        target_gpu = target.removesuffix("_in")
        if (
            source_gpu in carbon_model.gpu_costs
            and target_gpu in carbon_model.gpu_costs
            and carbon_model.gpu_costs[source_gpu].region
            != carbon_model.gpu_costs[target_gpu].region
        ):
            cross_region_flow += flow
    path_flows = decompose_flow_paths(serving_graph.graph, positive, tolerance=tolerance)
    path_shares = {
        path: flow / throughput for path, flow in path_flows.items()
    }
    return FlowCarbonMetrics(
        throughput=throughput,
        carbon_g_per_second=carbon_rate,
        carbon_g_per_1000_tokens=carbon_rate / throughput * 1000.0,
        positive_flow_edges=dict(sorted(positive.items())),
        gpu_flow_tokens_per_second=dict(sorted(gpu_flow.items())),
        region_token_flow=dict(sorted(region_flow.items())),
        region_flow_share=dict(sorted(region_share.items())),
        cross_region_flow_tokens_per_second=cross_region_flow,
        cross_region_flow_fraction=cross_region_flow / throughput,
        path_flow_tokens_per_second=path_flows,
        path_flow_share=path_shares,
    )


def scaled_helix_reference_flow(
    serving_graph: ServingGraph,
    max_flow_result: MaxFlowResult,
    carbon_model: CarbonCostModel,
    throughput_target: float,
) -> FlowCarbonMetrics:
    """Scale one throughput-maximizing Helix flow to the same target throughput.

    This preserves the non-carbon-aware flow decomposition while enabling a
    fair carbon comparison at identical throughput.
    """

    if not 0 < throughput_target <= max_flow_result.max_flow_value:
        raise ValueError("Reference throughput target is outside the feasible range")
    scale = throughput_target / max_flow_result.max_flow_value
    scaled = {
        edge: flow * scale
        for edge, flow in max_flow_result.positive_flow_edges.items()
    }
    return evaluate_flow_carbon(
        serving_graph, scaled, carbon_model, throughput_target
    )


def solve_carbon_aware_flow(
    serving_graph: ServingGraph,
    carbon_model: CarbonCostModel,
    throughput_target: float,
    *,
    tolerance: float = 1e-8,
) -> CarbonFlowResult:
    """Minimize operational-carbon rate at fixed placement and throughput."""

    if throughput_target <= 0:
        raise ValueError("throughput_target must be positive")
    graph = serving_graph.graph
    edges = sorted(graph.edges())
    nodes = sorted(graph.nodes())
    edge_index = {edge: index for index, edge in enumerate(edges)}
    capacities = {
        edge: float(graph[edge[0]][edge[1]]["capacity"]) for edge in edges
    }
    edge_costs: dict[Edge, float] = {}
    objective: list[float] = []
    for edge in edges:
        gpu_id = _gpu_id_for_compute_edge(edge, carbon_model)
        cost = 0.0 if gpu_id is None else carbon_model.carbon_g_per_token(gpu_id)
        edge_costs[edge] = cost
        objective.append(cost * OBJECTIVE_SCALE)

    a_eq = np.zeros((len(nodes), len(edges)), dtype=float)
    b_eq = np.zeros(len(nodes), dtype=float)
    for row, node in enumerate(nodes):
        for target in graph.successors(node):
            a_eq[row, edge_index[(node, target)]] += 1.0
        for source in graph.predecessors(node):
            a_eq[row, edge_index[(source, node)]] -= 1.0
        if node == SOURCE:
            b_eq[row] = throughput_target
        elif node == SINK:
            b_eq[row] = -throughput_target

    start = perf_counter()
    solution = linprog(
        c=np.asarray(objective),
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=[(0.0, capacities[edge]) for edge in edges],
        method="highs",
    )
    solver_time = perf_counter() - start
    if not solution.success or solution.x is None:
        raise CarbonFlowOptimizationError(
            f"Carbon-aware flow LP failed: {solution.message}"
        )

    flows = {edge: float(solution.x[index]) for edge, index in edge_index.items()}
    capacity_ok = all(
        -tolerance <= flows[edge] <= capacities[edge] + tolerance for edge in edges
    )
    conservation_ok = bool(np.allclose(a_eq @ solution.x, b_eq, atol=tolerance))
    achieved = sum(
        flows[(SOURCE, target)] for target in graph.successors(SOURCE)
    )
    throughput_ok = abs(achieved - throughput_target) <= tolerance
    if not capacity_ok:
        raise CarbonFlowOptimizationError("LP result violates capacity constraints")
    if not conservation_ok:
        raise CarbonFlowOptimizationError("LP result violates flow conservation")
    if not throughput_ok:
        raise CarbonFlowOptimizationError("LP result violates throughput target")

    metrics = evaluate_flow_carbon(
        serving_graph, flows, carbon_model, achieved, tolerance=tolerance
    )
    return CarbonFlowResult(
        throughput_target=throughput_target,
        metrics=metrics,
        edge_capacities=dict(sorted(capacities.items())),
        edge_carbon_cost_g_per_token=dict(sorted(edge_costs.items())),
        solver_time_seconds=solver_time,
        solver_status=str(solution.message),
        capacity_constraints_check=True,
        conservation_check=True,
        throughput_check=True,
    )

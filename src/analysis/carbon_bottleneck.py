"""Deterministic bottleneck signals for carbon-aware local placement search."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Mapping

from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import ServingGraph, gpu_in_node, gpu_out_node
from src.optimizer.carbon_flow import CarbonFlowResult
from src.optimizer.maxflow import Edge


@dataclass(frozen=True, slots=True)
class BoundaryBottleneck:
    """One active strict-boundary edge and its local search priority."""

    source_gpu_id: str
    target_gpu_id: str
    boundary_layer: int
    source_compute_utilization: float
    target_compute_utilization: float
    network_utilization: float
    source_carbon_g_per_token_per_layer: float
    target_carbon_g_per_token_per_layer: float
    preferred_recipient_gpu_id: str | None
    low_carbon_headroom: float
    bottleneck_relevant: bool
    priority_score: float


@dataclass(frozen=True, slots=True)
class CarbonBottleneckReport:
    """Capacity, carbon-asymmetry, and placement-boundary diagnostics."""

    compute_utilization: Mapping[str, float]
    saturated_compute_gpus: tuple[str, ...]
    network_utilization: Mapping[Edge, float]
    saturated_network_edges: tuple[Edge, ...]
    gpu_carbon_g_per_token_per_layer: Mapping[str, float]
    low_carbon_headroom_gpus: tuple[str, ...]
    boundary_signals: tuple[BoundaryBottleneck, ...]


def _edge_flow(result: CarbonFlowResult, edge: Edge) -> float:
    return float(result.metrics.positive_flow_edges.get(edge, 0.0))


def analyze_carbon_bottlenecks(
    serving_graph: ServingGraph,
    carbon_model: CarbonCostModel,
    flow_result: CarbonFlowResult,
    *,
    utilization_threshold: float,
    tolerance: float = 1e-9,
) -> CarbonBottleneckReport:
    """Extract stable local-search signals without changing the flow LP."""

    if not 0.0 < utilization_threshold <= 1.0:
        raise ValueError("utilization_threshold must be in (0, 1]")
    if tolerance < 0.0:
        raise ValueError("tolerance must be non-negative")

    compute_utilization: dict[str, float] = {}
    per_layer_carbon: dict[str, float] = {}
    for gpu_id, interval in sorted(serving_graph.placement.intervals.items()):
        edge = (gpu_in_node(gpu_id), gpu_out_node(gpu_id))
        capacity = float(flow_result.edge_capacities[edge])
        compute_utilization[gpu_id] = _edge_flow(flow_result, edge) / capacity
        per_layer_carbon[gpu_id] = (
            carbon_model.carbon_g_per_token(gpu_id) / interval.layer_count
        )

    saturated_compute = tuple(
        gpu_id
        for gpu_id, value in sorted(compute_utilization.items())
        if value >= utilization_threshold - tolerance
    )

    network_utilization: dict[Edge, float] = {}
    for source, target, data in serving_graph.graph.edges(data=True):
        if data["edge_type"] != "network":
            continue
        edge = (source, target)
        capacity = float(flow_result.edge_capacities[edge])
        network_utilization[edge] = _edge_flow(flow_result, edge) / capacity
    saturated_network = tuple(
        edge
        for edge, value in sorted(network_utilization.items())
        if value >= utilization_threshold - tolerance
    )

    cost_median = median(per_layer_carbon.values())
    low_carbon_headroom = tuple(
        gpu_id
        for gpu_id in sorted(compute_utilization)
        if per_layer_carbon[gpu_id] < cost_median - tolerance
        and compute_utilization[gpu_id] < utilization_threshold - tolerance
    )

    boundaries: list[BoundaryBottleneck] = []
    for edge, network_value in sorted(network_utilization.items()):
        source_gpu = edge[0].removesuffix("_out")
        target_gpu = edge[1].removesuffix("_in")
        source_interval = serving_graph.placement.intervals[source_gpu]
        target_interval = serving_graph.placement.intervals[target_gpu]
        if source_interval.end_layer != target_interval.start_layer:
            continue

        source_cost = per_layer_carbon[source_gpu]
        target_cost = per_layer_carbon[target_gpu]
        preferred: str | None
        if source_cost < target_cost - tolerance:
            preferred = source_gpu
        elif target_cost < source_cost - tolerance:
            preferred = target_gpu
        else:
            preferred = None
        headroom = (
            max(0.0, 1.0 - compute_utilization[preferred])
            if preferred is not None
            else 0.0
        )
        carbon_scale = max(source_cost, target_cost, tolerance)
        normalized_asymmetry = abs(source_cost - target_cost) / carbon_scale
        capacity_signal = max(
            compute_utilization[source_gpu],
            compute_utilization[target_gpu],
            network_value,
        )
        structural_signal = preferred is not None and headroom > tolerance
        relevant = (
            source_gpu in saturated_compute
            or target_gpu in saturated_compute
            or edge in saturated_network
            or structural_signal
        )
        score = capacity_signal + normalized_asymmetry + headroom
        boundaries.append(
            BoundaryBottleneck(
                source_gpu_id=source_gpu,
                target_gpu_id=target_gpu,
                boundary_layer=source_interval.end_layer,
                source_compute_utilization=compute_utilization[source_gpu],
                target_compute_utilization=compute_utilization[target_gpu],
                network_utilization=network_value,
                source_carbon_g_per_token_per_layer=source_cost,
                target_carbon_g_per_token_per_layer=target_cost,
                preferred_recipient_gpu_id=preferred,
                low_carbon_headroom=headroom,
                bottleneck_relevant=relevant,
                priority_score=score,
            )
        )

    boundaries.sort(
        key=lambda value: (
            not value.bottleneck_relevant,
            -value.priority_score,
            value.source_gpu_id,
            value.target_gpu_id,
        )
    )
    return CarbonBottleneckReport(
        compute_utilization=dict(sorted(compute_utilization.items())),
        saturated_compute_gpus=saturated_compute,
        network_utilization=dict(sorted(network_utilization.items())),
        saturated_network_edges=saturated_network,
        gpu_carbon_g_per_token_per_layer=dict(sorted(per_layer_carbon.items())),
        low_carbon_headroom_gpus=low_carbon_headroom,
        boundary_signals=tuple(boundaries),
    )

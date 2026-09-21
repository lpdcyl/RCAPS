"""Fast, interval-level carbon flow scheduling on a fixed placement."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping

from src.carbon.model import (
    CarbonCostModel,
    CarbonIntensityInput,
    EnergyProvider,
    resolve_ci_snapshot,
)
from src.graph.serving_graph import LayerPlacement, ModelProfile, ServingGraph, ThroughputProvider, build_serving_graph
from src.graph.topology import ClusterTopology
from src.optimizer.carbon_flow import CarbonFlowResult, solve_carbon_aware_flow
from src.optimizer.maxflow import MaxFlowResult, solve_max_flow


@dataclass(frozen=True, slots=True)
class FlowSchedule:
    """One interval's aggregate flow plan and dispatch-ready quotas."""

    timestamp: float
    duration_seconds: float
    demand_tokens_per_second: float
    served_throughput: float
    ci_snapshot: Mapping[str, float]
    serving_graph: ServingGraph
    flow_result: CarbonFlowResult
    path_quota_tokens_per_second: Mapping[str, float]
    max_flow_result: MaxFlowResult
    optimization_runtime_seconds: float

    @property
    def carbon_g_per_second(self) -> float:
        return self.flow_result.metrics.carbon_g_per_second


class CarbonFlowScheduler:
    """Recompute one carbon-aware aggregate flow per scheduling interval."""

    def __init__(
        self,
        topology: ClusterTopology,
        model: ModelProfile,
        placement: LayerPlacement,
        throughput_provider: ThroughputProvider,
        energy_provider: EnergyProvider,
        ci_source: CarbonIntensityInput,
        *,
        phase: str,
        batch_size: int,
        scheduling_interval_seconds: float,
        solver_tolerance: float = 1e-8,
    ) -> None:
        if scheduling_interval_seconds <= 0.0:
            raise ValueError("scheduling_interval_seconds must be positive")
        self.topology = topology
        self.model = model
        self.placement = placement
        self.throughput_provider = throughput_provider
        self.energy_provider = energy_provider
        self.ci_source = ci_source
        self.phase = phase
        self.batch_size = batch_size
        self.scheduling_interval_seconds = scheduling_interval_seconds
        self.solver_tolerance = solver_tolerance

    def schedule(
        self,
        timestamp: float,
        demand_tokens_per_second: float,
    ) -> FlowSchedule:
        if demand_tokens_per_second <= 0.0:
            raise ValueError("demand_tokens_per_second must be positive")
        start = perf_counter()
        serving = build_serving_graph(
            self.topology,
            self.model,
            self.placement,
            self.throughput_provider,
        )
        maximum = solve_max_flow(serving, tolerance=self.solver_tolerance)
        target = min(float(demand_tokens_per_second), maximum.max_flow_value)
        snapshot = resolve_ci_snapshot(
            self.ci_source,
            (gpu.region for gpu in self.topology.gpus.values()),
            float(timestamp),
        )
        carbon_model = CarbonCostModel.build(
            self.topology,
            self.model,
            self.placement,
            self.energy_provider,
            snapshot,
            phase=self.phase,
            batch_size=self.batch_size,
        )
        result = solve_carbon_aware_flow(
            serving,
            carbon_model,
            target,
            tolerance=self.solver_tolerance,
        )
        return FlowSchedule(
            timestamp=float(timestamp),
            duration_seconds=self.scheduling_interval_seconds,
            demand_tokens_per_second=float(demand_tokens_per_second),
            served_throughput=result.metrics.throughput,
            ci_snapshot=dict(snapshot),
            serving_graph=serving,
            flow_result=result,
            path_quota_tokens_per_second=dict(
                sorted(result.metrics.path_flow_tokens_per_second.items())
            ),
            max_flow_result=maximum,
            optimization_runtime_seconds=perf_counter() - start,
        )

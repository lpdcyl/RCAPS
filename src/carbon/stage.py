"""Stage-aware carbon accounting layered on the existing flow semantics."""

from __future__ import annotations

from dataclasses import dataclass

from src.carbon.model import CarbonCostModel, CarbonIntensityInput, EnergyProvider
from src.graph.serving_graph import LayerPlacement, ModelProfile, ServingGraph
from src.graph.topology import ClusterTopology
from src.optimizer.carbon_flow import FlowCarbonMetrics, evaluate_flow_carbon


@dataclass(frozen=True, slots=True)
class StageWorkload:
    """Token workload split between prefill input and decode output."""

    prefill_tokens: float
    decode_tokens: float

    def __post_init__(self) -> None:
        if self.prefill_tokens < 0.0 or self.decode_tokens < 0.0:
            raise ValueError("stage token counts cannot be negative")
        if self.prefill_tokens + self.decode_tokens <= 0.0:
            raise ValueError("stage workload must contain tokens")


@dataclass(frozen=True, slots=True)
class StageCarbonResult:
    prefill_carbon_g: float
    decode_carbon_g: float
    total_carbon_g: float
    prefill_carbon_g_per_token: float
    decode_carbon_g_per_token: float


@dataclass(frozen=True, slots=True)
class WorkloadWeightedEnergyProvider:
    """Expose a workload-weighted stage energy view to legacy flow APIs."""

    base: EnergyProvider
    prefill_fraction: float
    decode_fraction: float

    def __post_init__(self) -> None:
        if self.prefill_fraction < 0.0 or self.decode_fraction < 0.0:
            raise ValueError("stage fractions cannot be negative")
        if abs(self.prefill_fraction + self.decode_fraction - 1.0) > 1e-12:
            raise ValueError("stage fractions must sum to one")

    @property
    def description(self) -> str:
        return f"{self.base.description}; workload-weighted prefill/decode"

    def energy_joules_per_token(
        self,
        gpu,
        start_layer: int,
        end_layer: int,
        model,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        if phase != "weighted":
            return self.base.energy_joules_per_token(
                gpu, start_layer, end_layer, model, phase=phase, batch_size=batch_size
            )
        return self.prefill_fraction * self.base.energy_joules_per_token(
            gpu, start_layer, end_layer, model, phase="prefill", batch_size=batch_size
        ) + self.decode_fraction * self.base.energy_joules_per_token(
            gpu, start_layer, end_layer, model, phase="decode", batch_size=batch_size
        )

    def energy_joules_per_token_for_layer_count(
        self,
        gpu,
        layer_count: int,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        if phase != "weighted":
            return self.base.energy_joules_per_token_for_layer_count(
                gpu, layer_count, phase=phase, batch_size=batch_size
            )
        return self.prefill_fraction * self.base.energy_joules_per_token_for_layer_count(
            gpu, layer_count, phase="prefill", batch_size=batch_size
        ) + self.decode_fraction * self.base.energy_joules_per_token_for_layer_count(
            gpu, layer_count, phase="decode", batch_size=batch_size
        )


def _per_token(metrics: FlowCarbonMetrics) -> float:
    return metrics.carbon_g_per_1000_tokens / 1000.0


def evaluate_stage_carbon(
    serving_graph: ServingGraph,
    flow_edges: dict[tuple[str, str], float],
    throughput: float,
    topology: ClusterTopology,
    model: ModelProfile,
    placement: LayerPlacement,
    energy_provider: EnergyProvider,
    carbon_intensity: CarbonIntensityInput,
    workload: StageWorkload,
    *,
    batch_size: int,
    timestamp: float | None = None,
) -> StageCarbonResult:
    """Evaluate prefill and decode carbon on one validated placement/flow."""

    if throughput <= 0.0:
        raise ValueError("throughput must be positive")
    metrics: dict[str, FlowCarbonMetrics] = {}
    for phase in ("prefill", "decode"):
        cost = CarbonCostModel.build(
            topology,
            model,
            placement,
            energy_provider,
            carbon_intensity,
            phase=phase,
            batch_size=batch_size,
            timestamp=timestamp,
        )
        metrics[phase] = evaluate_flow_carbon(
            serving_graph, flow_edges, cost, throughput
        )
    prefill_rate = _per_token(metrics["prefill"])
    decode_rate = _per_token(metrics["decode"])
    prefill_carbon = prefill_rate * workload.prefill_tokens
    decode_carbon = decode_rate * workload.decode_tokens
    return StageCarbonResult(
        prefill_carbon,
        decode_carbon,
        prefill_carbon + decode_carbon,
        prefill_rate,
        decode_rate,
    )

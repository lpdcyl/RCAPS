"""Parameterized GPU energy and operational-carbon cost models."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol, TypeAlias, runtime_checkable

from src.graph.serving_graph import LayerPlacement, ModelProfile
from src.graph.topology import ClusterTopology, GPUNode


JOULES_PER_KWH = 3_600_000.0


class MissingEnergyProfileError(LookupError):
    """Raised when an energy parameter is missing for a requested workload."""


@runtime_checkable
class EnergyProvider(Protocol):
    """Return configured energy/token for a GPU's placed layer interval."""

    @property
    def description(self) -> str:
        """Human-readable description of the energy model."""

    def energy_joules_per_token(
        self,
        gpu: GPUNode,
        start_layer: int,
        end_layer: int,
        model: ModelProfile,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        """Return operational compute energy in joules per processed token."""

    def energy_joules_per_token_for_layer_count(
        self,
        gpu: GPUNode,
        layer_count: int,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        """Return energy/token for a homogeneous interval of ``layer_count``."""


@runtime_checkable
class CarbonIntensityProvider(Protocol):
    """Resolve carbon intensity for a region at an optional point in time."""

    def get_ci(self, region: str, timestamp: float | None = None) -> float:
        """Return carbon intensity in gCO2e/kWh."""


def validate_carbon_intensity_g_per_kwh(region: str, value: float) -> float:
    """Validate and normalize one regional carbon-intensity value."""

    intensity = float(value)
    if not isfinite(intensity) or intensity < 0.0:
        raise ValueError(
            f"Carbon intensity for region {region!r} must be finite and non-negative"
        )
    return intensity


@dataclass(frozen=True, slots=True)
class ConstantCIProvider:
    """Immutable adapter for the legacy static region-to-CI mapping API."""

    carbon_intensity_g_per_kwh: Mapping[str, float]

    def __post_init__(self) -> None:
        normalized: dict[str, float] = {}
        for region, value in self.carbon_intensity_g_per_kwh.items():
            if not isinstance(region, str) or not region:
                raise ValueError("Carbon-intensity region keys must be non-empty strings")
            normalized[region] = validate_carbon_intensity_g_per_kwh(region, value)
        object.__setattr__(
            self,
            "carbon_intensity_g_per_kwh",
            MappingProxyType(normalized),
        )

    def get_ci(self, region: str, timestamp: float | None = None) -> float:
        del timestamp
        try:
            return self.carbon_intensity_g_per_kwh[region]
        except KeyError as exc:
            raise ValueError(
                f"Missing carbon intensity for region {region!r}"
            ) from exc


CarbonIntensityInput: TypeAlias = Mapping[str, float] | CarbonIntensityProvider


def as_ci_provider(ci_source: CarbonIntensityInput) -> CarbonIntensityProvider:
    """Adapt a legacy mapping or pass through a CI provider."""

    if isinstance(ci_source, Mapping):
        return ConstantCIProvider(ci_source)
    if isinstance(ci_source, CarbonIntensityProvider):
        return ci_source
    raise TypeError(
        "ci_source must be a region-to-intensity mapping or CarbonIntensityProvider"
    )


def resolve_ci_snapshot(
    ci_source: CarbonIntensityInput,
    regions: Iterable[str],
    timestamp: float | None = None,
) -> dict[str, float]:
    """Resolve each requested region once into an invocation-level snapshot."""

    provider = as_ci_provider(ci_source)
    snapshot: dict[str, float] = {}
    for region in sorted(set(regions)):
        if not isinstance(region, str) or not region:
            raise ValueError("Carbon-intensity regions must be non-empty strings")
        snapshot[region] = validate_carbon_intensity_g_per_kwh(
            region,
            provider.get_ci(region, timestamp),
        )
    return snapshot


def operational_carbon_g(
    energy_joules: float,
    carbon_intensity_g_per_kwh: float,
) -> float:
    """Convert operational energy and carbon intensity to grams of CO2e."""

    energy = float(energy_joules)
    if not isfinite(energy) or energy < 0.0:
        raise ValueError("Energy must be finite and non-negative")
    intensity = validate_carbon_intensity_g_per_kwh(
        "<resolved>", carbon_intensity_g_per_kwh
    )
    return intensity * energy / JOULES_PER_KWH


@dataclass(frozen=True, slots=True)
class ConfiguredLinearEnergyProvider:
    """Simulator assumption using configured joules/token/layer parameters.

    This provider does not infer energy/token from TDP. It looks up a configured
    parameter by GPU type, inference phase, and batch size, then scales it by
    the number of placed layers.
    """

    profiles: Mapping[str, Mapping[str, Mapping[int, float]]]

    @property
    def description(self) -> str:
        return "Configured operational-energy proxy (simulator assumption)"

    def energy_joules_per_token(
        self,
        gpu: GPUNode,
        start_layer: int,
        end_layer: int,
        model: ModelProfile,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        if not 0 <= start_layer < end_layer <= model.num_layers:
            raise ValueError("Energy request has an invalid layer interval")
        return self.energy_joules_per_token_for_layer_count(
            gpu,
            end_layer - start_layer,
            phase=phase,
            batch_size=batch_size,
        )

    def energy_joules_per_token_for_layer_count(
        self,
        gpu: GPUNode,
        layer_count: int,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        """Evaluate the configured linear proxy for a layer count."""

        if layer_count <= 0:
            raise ValueError("layer_count must be positive")
        try:
            per_layer = float(
                self.profiles[gpu.gpu_type][phase][batch_size]
            )
        except KeyError as exc:
            raise MissingEnergyProfileError(
                "Missing energy profile for "
                f"GPU={gpu.gpu_type!r}, phase={phase!r}, batch_size={batch_size}"
            ) from exc
        if per_layer <= 0:
            raise ValueError("Energy profile values must be positive")
        return per_layer * layer_count


@dataclass(frozen=True, slots=True)
class MultipliedEnergyProvider:
    """Apply explicit per-GPU-type multipliers to another energy provider."""

    base: EnergyProvider
    multipliers: Mapping[str, float]

    def __post_init__(self) -> None:
        if any(float(value) <= 0 for value in self.multipliers.values()):
            raise ValueError("Energy multipliers must be positive")

    @property
    def description(self) -> str:
        return f"{self.base.description}; synthetic type multipliers"

    def _multiplier(self, gpu: GPUNode) -> float:
        return float(self.multipliers.get(gpu.gpu_type, 1.0))

    def energy_joules_per_token(
        self,
        gpu: GPUNode,
        start_layer: int,
        end_layer: int,
        model: ModelProfile,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        return self._multiplier(gpu) * self.base.energy_joules_per_token(
            gpu,
            start_layer,
            end_layer,
            model,
            phase=phase,
            batch_size=batch_size,
        )

    def energy_joules_per_token_for_layer_count(
        self,
        gpu: GPUNode,
        layer_count: int,
        *,
        phase: str,
        batch_size: int,
    ) -> float:
        return self._multiplier(gpu) * self.base.energy_joules_per_token_for_layer_count(
            gpu,
            layer_count,
            phase=phase,
            batch_size=batch_size,
        )


@dataclass(frozen=True, slots=True)
class GPUCarbonCost:
    """Per-token operational-carbon proxy for one placed GPU."""

    gpu_id: str
    region: str
    carbon_intensity_g_per_kwh: float
    energy_joules_per_token: float
    carbon_g_per_token: float


@dataclass(frozen=True, slots=True)
class CarbonCostModel:
    """Compute per-GPU energy and operational carbon for a fixed placement."""

    gpu_costs: Mapping[str, GPUCarbonCost]
    phase: str
    batch_size: int
    accounting_scope: str = "operational GPU-compute carbon proxy"

    @classmethod
    def build(
        cls,
        topology: ClusterTopology,
        model: ModelProfile,
        placement: LayerPlacement,
        energy_provider: EnergyProvider,
        carbon_intensity_by_region: CarbonIntensityInput,
        *,
        phase: str,
        batch_size: int,
        timestamp: float | None = None,
    ) -> "CarbonCostModel":
        """Create costs without modifying placement or logical topology."""

        placement.validate(topology, model)
        ci_snapshot = resolve_ci_snapshot(
            carbon_intensity_by_region,
            (gpu.region for gpu in topology.gpus.values()),
            timestamp,
        )
        costs: dict[str, GPUCarbonCost] = {}
        for gpu_id, gpu in topology.gpus.items():
            intensity = ci_snapshot[gpu.region]
            interval = placement.intervals[gpu_id]
            energy = energy_provider.energy_joules_per_token(
                gpu,
                interval.start_layer,
                interval.end_layer,
                model,
                phase=phase,
                batch_size=batch_size,
            )
            carbon = operational_carbon_g(energy, intensity)
            costs[gpu_id] = GPUCarbonCost(
                gpu_id=gpu_id,
                region=gpu.region,
                carbon_intensity_g_per_kwh=intensity,
                energy_joules_per_token=energy,
                carbon_g_per_token=carbon,
            )
        return cls(gpu_costs=costs, phase=phase, batch_size=batch_size)

    def carbon_g_per_token(self, gpu_id: str) -> float:
        """Return the operational-carbon cost of processing one token."""

        return self.gpu_costs[gpu_id].carbon_g_per_token

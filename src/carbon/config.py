"""Configuration loaders for energy parameters and Phase 2 CI sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.carbon.model import ConfiguredLinearEnergyProvider
from src.utils.config import load_yaml


@dataclass(frozen=True, slots=True)
class Phase2ExperimentConfig:
    """Configuration for fixed-placement carbon-aware routing."""

    placement_name: str
    network_topology_file: str
    throughput_ratio_rho: float
    phase: str
    batch_size: int
    sweep_region: str
    sweep_values: tuple[float, ...]
    fixed_carbon_intensity: Mapping[str, float]
    summary_csv: str
    path_csv: str
    flow_share_figure: str


@dataclass(frozen=True, slots=True)
class Phase3ExperimentConfig:
    """Configuration for routing-versus-placement static experiments."""

    network_topology_file: str
    throughput_provider: str
    throughput_ratio_rho: float
    phase: str
    batch_size: int
    sweep_region: str
    sweep_values: tuple[float, ...]
    fixed_carbon_intensity: Mapping[str, float]
    routing_gap_epsilon: float
    routing_gap_sensitivity: tuple[float, ...]
    bandwidth_mbps_values: tuple[float, ...]
    helix_routing_csv: str
    strategy_sweep_csv: str
    routing_breakpoints_csv: str
    placement_breakpoints_csv: str
    transition_figure: str
    phase_diagram_csv: str
    phase_diagram_figure: str


@dataclass(frozen=True, slots=True)
class Phase35ExperimentConfig:
    """Predeclared Phase 3.5 sensitivity scenarios and output paths."""

    rhos: tuple[float, ...]
    gpu_scenarios: Mapping[str, Mapping[str, str]]
    network_capacity_tokens_per_second: tuple[float, ...]
    energy_gpu_types: tuple[str, ...]
    energy_multipliers: tuple[float, ...]
    baseline_scenario: str
    baseline_rho: float
    baseline_capacity_tokens_per_second: float
    boundary_degeneracy_tolerance: float
    outputs: Mapping[str, str]


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_energy_provider(
    config_dir: str | Path,
) -> tuple[ConfiguredLinearEnergyProvider, Mapping[str, Any]]:
    """Load simulator energy parameters without deriving them from TDP."""

    data = load_yaml(Path(config_dir) / "energy_profiles.yaml")
    metadata = _mapping(data.get("metadata"), "energy metadata")
    if metadata.get("tdp_used_as_energy_per_token") is not False:
        raise ValueError("Energy configuration must not treat TDP as energy/token")
    if str(data.get("provider")) != "configured_linear":
        raise ValueError("Phase 2 currently supports provider: configured_linear")

    raw_types = _mapping(data.get("gpu_types"), "energy gpu_types")
    profiles: dict[str, dict[str, dict[int, float]]] = {}
    for gpu_type, raw_gpu in raw_types.items():
        phases = _mapping(_mapping(raw_gpu, str(gpu_type)).get("phases"), "phases")
        gpu_phases: dict[str, dict[int, float]] = {}
        for phase, raw_phase in phases.items():
            batches = _mapping(
                _mapping(raw_phase, str(phase)).get("batch_sizes"), "batch_sizes"
            )
            gpu_phases[str(phase)] = {
                int(batch_size): float(
                    _mapping(raw_value, "batch energy")[
                        "joules_per_token_per_layer"
                    ]
                )
                for batch_size, raw_value in batches.items()
            }
        profiles[str(gpu_type)] = gpu_phases
    return ConfiguredLinearEnergyProvider(profiles), metadata


def _inclusive_float_range(start: float, stop: float, step: float) -> tuple[float, ...]:
    if step <= 0 or stop < start:
        raise ValueError("CI sweep requires stop >= start and step > 0")
    count = int(round((stop - start) / step))
    values = tuple(start + index * step for index in range(count + 1))
    if abs(values[-1] - stop) > 1e-9:
        raise ValueError("CI sweep range must be exactly divisible by step")
    return values


def load_phase2_experiment(config_dir: str | Path) -> Phase2ExperimentConfig:
    """Load the fixed-placement carbon-aware routing experiment."""

    data = load_yaml(Path(config_dir) / "phase2_experiment.yaml")
    rho = float(data["throughput_ratio_rho"])
    if not 0 < rho <= 1:
        raise ValueError("throughput_ratio_rho must be in (0, 1]")
    carbon = _mapping(data.get("carbon_intensity_g_per_kwh"), "carbon intensity")
    fixed = {
        str(region): float(value)
        for region, value in _mapping(
            carbon.get("fixed_regions"), "fixed_regions"
        ).items()
    }
    sweep = _mapping(carbon.get("sweep"), "carbon sweep")
    outputs = _mapping(data.get("outputs"), "outputs")
    return Phase2ExperimentConfig(
        placement_name=str(data["placement"]),
        network_topology_file=str(data["network_topology"]),
        throughput_ratio_rho=rho,
        phase=str(data["phase"]),
        batch_size=int(data["batch_size"]),
        sweep_region=str(sweep["region"]),
        sweep_values=_inclusive_float_range(
            float(sweep["start"]), float(sweep["stop"]), float(sweep["step"])
        ),
        fixed_carbon_intensity=fixed,
        summary_csv=str(outputs["summary_csv"]),
        path_csv=str(outputs["path_csv"]),
        flow_share_figure=str(outputs["flow_share_figure"]),
    )


def load_phase3_experiment(config_dir: str | Path) -> Phase3ExperimentConfig:
    """Load the static routing-placement sweep and phase-diagram settings."""

    data = load_yaml(Path(config_dir) / "phase3_experiment.yaml")
    rho = float(data["rho"])
    if not 0 < rho <= 1:
        raise ValueError("rho must be in (0, 1]")
    provider = str(data.get("throughput_provider", "profiled")).lower()
    if provider not in {"analytical", "profiled"}:
        raise ValueError("throughput_provider must be analytical or profiled")
    carbon = _mapping(data.get("carbon"), "carbon")
    fixed = {
        str(region): float(value)
        for region, value in _mapping(carbon.get("fixed_regions"), "fixed_regions").items()
    }
    sweep = _mapping(carbon.get("sweep"), "carbon sweep")
    epsilon = float(data["routing_gap_epsilon"])
    sensitivity = tuple(float(value) for value in data["routing_gap_sensitivity"])
    if not 0 <= epsilon < 1 or any(not 0 <= value < 1 for value in sensitivity):
        raise ValueError("Routing gap epsilon values must be in [0, 1)")
    bandwidths = tuple(float(value) for value in data["cross_region_bandwidth_mbps"])
    if not bandwidths or any(value <= 0 for value in bandwidths):
        raise ValueError("Cross-region bandwidth values must be positive")
    outputs = _mapping(data.get("outputs"), "outputs")
    return Phase3ExperimentConfig(
        network_topology_file=str(data["network_topology"]),
        throughput_provider=provider,
        throughput_ratio_rho=rho,
        phase=str(data["phase"]),
        batch_size=int(data["batch_size"]),
        sweep_region=str(sweep["region"]),
        sweep_values=_inclusive_float_range(
            float(sweep["start"]), float(sweep["stop"]), float(sweep["step"])
        ),
        fixed_carbon_intensity=fixed,
        routing_gap_epsilon=epsilon,
        routing_gap_sensitivity=sensitivity,
        bandwidth_mbps_values=bandwidths,
        helix_routing_csv=str(outputs["helix_routing_csv"]),
        strategy_sweep_csv=str(outputs["strategy_sweep_csv"]),
        routing_breakpoints_csv=str(outputs["routing_breakpoints_csv"]),
        placement_breakpoints_csv=str(outputs["placement_breakpoints_csv"]),
        transition_figure=str(outputs["transition_figure"]),
        phase_diagram_csv=str(outputs["phase_diagram_csv"]),
        phase_diagram_figure=str(outputs["phase_diagram_figure"]),
    )


def load_phase35_experiment(config_dir: str | Path) -> Phase35ExperimentConfig:
    """Load the staged, synthetic Phase 3.5 sensitivity design."""

    data = load_yaml(Path(config_dir) / "phase35_sensitivity.yaml")
    rhos = tuple(float(value) for value in data["rho_values"])
    if not rhos or any(not 0 < value <= 1 for value in rhos):
        raise ValueError("Phase 3.5 rho values must be in (0, 1]")
    raw_scenarios = _mapping(data.get("gpu_scenarios"), "gpu_scenarios")
    scenarios: dict[str, dict[str, str]] = {}
    expected_ids: set[str] | None = None
    for name, raw_mapping in raw_scenarios.items():
        mapping = {
            str(gpu_id): str(gpu_type)
            for gpu_id, gpu_type in _mapping(
                raw_mapping, f"gpu_scenarios.{name}"
            ).items()
        }
        if expected_ids is None:
            expected_ids = set(mapping)
        elif set(mapping) != expected_ids:
            raise ValueError("Every GPU scenario must configure the same GPU ids")
        scenarios[str(name)] = mapping
    network = _mapping(data.get("network"), "network")
    capacities = tuple(
        float(value) for value in network["capacity_tokens_per_second"]
    )
    if not capacities or any(value <= 0 for value in capacities):
        raise ValueError("Network token capacities must be positive")
    energy = _mapping(data.get("energy_sensitivity"), "energy_sensitivity")
    energy_types = tuple(str(value) for value in energy["gpu_types"])
    multipliers = tuple(float(value) for value in energy["multipliers"])
    if not energy_types or not multipliers or any(value <= 0 for value in multipliers):
        raise ValueError("Energy sensitivity requires positive multipliers")
    baseline = _mapping(data.get("baseline"), "baseline")
    baseline_scenario = str(baseline["gpu_scenario"])
    if baseline_scenario not in scenarios:
        raise ValueError("Baseline GPU scenario is not declared")
    baseline_rho = float(baseline["rho"])
    if not 0 < baseline_rho <= 1:
        raise ValueError("Baseline rho must be in (0, 1]")
    boundary = _mapping(data.get("boundary"), "boundary")
    tolerance = float(boundary["degeneracy_relative_tolerance"])
    if tolerance < 0:
        raise ValueError("Boundary tolerance must be non-negative")
    outputs = {
        str(name): str(path)
        for name, path in _mapping(data.get("outputs"), "outputs").items()
    }
    return Phase35ExperimentConfig(
        rhos=rhos,
        gpu_scenarios=scenarios,
        network_capacity_tokens_per_second=capacities,
        energy_gpu_types=energy_types,
        energy_multipliers=multipliers,
        baseline_scenario=baseline_scenario,
        baseline_rho=baseline_rho,
        baseline_capacity_tokens_per_second=float(
            baseline["capacity_tokens_per_second"]
        ),
        boundary_degeneracy_tolerance=tolerance,
        outputs=outputs,
    )

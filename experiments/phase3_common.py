"""Shared loading and serialization for static Phase 3 experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from src.carbon.config import (
    Phase3ExperimentConfig,
    load_energy_provider,
    load_phase3_experiment,
)
from src.carbon.model import EnergyProvider
from src.graph.serving_graph import (
    AnalyticalThroughputProvider,
    ProfiledThroughputProvider,
    ThroughputProvider,
)
from src.graph.topology import ClusterTopology
from src.optimizer.maxflow import Edge
from src.optimizer.placement_milp import PlacementMILPResult, solve_throughput_optimal_placement
from src.simulator.simulator import SimulationInputs, load_simulation_inputs, load_topology


@dataclass(frozen=True, slots=True)
class Phase3Context:
    config: Phase3ExperimentConfig
    simulation: SimulationInputs
    topology: ClusterTopology
    throughput_provider: ThroughputProvider
    energy_provider: EnergyProvider


def load_phase3_context(config_dir: str | Path) -> Phase3Context:
    """Load all immutable inputs for a Phase 3 experiment."""

    root = Path(config_dir)
    simulation = load_simulation_inputs(root)
    config = load_phase3_experiment(root)
    topology = load_topology(root, config.network_topology_file, simulation.gpus)
    provider: ThroughputProvider
    if config.throughput_provider == "profiled":
        provider = ProfiledThroughputProvider(simulation.profiles)
    else:
        provider = AnalyticalThroughputProvider()
    energy, _ = load_energy_provider(root)
    return Phase3Context(config, simulation, topology, provider, energy)


def solve_helix_baseline(
    context: Phase3Context, topology: ClusterTopology | None = None
) -> PlacementMILPResult:
    """Solve the carbon-independent throughput placement baseline."""

    return solve_throughput_optimal_placement(
        context.topology if topology is None else topology,
        context.simulation.model,
        context.throughput_provider,
    )


def carbon_intensities(
    config: Phase3ExperimentConfig, sweep_value: float
) -> dict[str, float]:
    values = dict(config.fixed_carbon_intensity)
    values[config.sweep_region] = float(sweep_value)
    return values


def json_float_mapping(values: Mapping[str, float]) -> str:
    return json.dumps(
        {key: float(value) for key, value in sorted(values.items())},
        separators=(",", ":"),
    )


def json_edge_mapping(values: Mapping[Edge, float]) -> str:
    return json.dumps(
        {f"{edge[0]}->{edge[1]}": float(value) for edge, value in sorted(values.items())},
        separators=(",", ":"),
    )

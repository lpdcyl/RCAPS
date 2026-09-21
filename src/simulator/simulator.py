"""Configuration-driven orchestration for the Phase 1 simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.graph.serving_graph import (
    AnalyticalThroughputProvider,
    LayerInterval,
    LayerPlacement,
    ModelProfile,
    ProfiledThroughputProvider,
    ServingGraph,
    ThroughputProvider,
    build_serving_graph,
)
from src.graph.topology import ClusterTopology, GPUNode, NetworkLink
from src.optimizer.maxflow import MaxFlowResult, solve_max_flow
from src.utils.config import load_yaml


@dataclass(frozen=True, slots=True)
class ValidationCase:
    """One configuration-defined numerical validation scenario."""

    name: str
    placement_name: str
    network_topology_file: str
    expected_max_flow: float
    expected_min_cut: float


@dataclass(frozen=True, slots=True)
class SimulationInputs:
    """Validated objects loaded from the four Phase 1 configuration groups."""

    model: ModelProfile
    gpus: tuple[GPUNode, ...]
    profiles: Mapping[str, Mapping[int, float]]
    placements: Mapping[str, LayerPlacement]
    throughput_provider: ThroughputProvider
    allow_partial_inference: bool
    random_seed: int
    validation_cases: tuple[ValidationCase, ...]


@dataclass(frozen=True, slots=True)
class SimulationRun:
    """The logical graph and validated solution for one scenario."""

    case: ValidationCase
    serving_graph: ServingGraph
    result: MaxFlowResult


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _load_gpus(config_dir: Path) -> tuple[tuple[GPUNode, ...], dict[str, dict[int, float]]]:
    data = load_yaml(config_dir / "gpu_profiles.yaml")
    type_data = _require_mapping(data.get("gpu_types"), "gpu_types")
    raw_gpus = data.get("gpus")
    if not isinstance(raw_gpus, list):
        raise ValueError("gpus must be a list")

    profiles: dict[str, dict[int, float]] = {}
    for gpu_type, raw_profile in type_data.items():
        profile = _require_mapping(raw_profile, f"gpu_types.{gpu_type}")
        raw_throughputs = _require_mapping(
            profile.get("tokens_per_second", {}),
            f"gpu_types.{gpu_type}.tokens_per_second",
        )
        profiles[str(gpu_type)] = {
            int(layer_count): float(value)
            for layer_count, value in raw_throughputs.items()
        }

    gpus: list[GPUNode] = []
    seen: set[str] = set()
    for raw_gpu in raw_gpus:
        gpu_data = _require_mapping(raw_gpu, "gpu entry")
        gpu_id = str(gpu_data["id"])
        gpu_type = str(gpu_data["gpu_type"])
        if gpu_id in seen:
            raise ValueError(f"Duplicate GPU id: {gpu_id}")
        if gpu_type not in type_data:
            raise ValueError(f"GPU {gpu_id} refers to unknown type {gpu_type}")
        type_profile = _require_mapping(type_data[gpu_type], f"gpu_types.{gpu_type}")
        gpus.append(
            GPUNode(
                gpu_id=gpu_id,
                region=str(gpu_data["region"]),
                gpu_type=gpu_type,
                memory_gb=float(type_profile["memory_gb"]),
                effective_compute_units_per_second=float(
                    type_profile["effective_compute_units_per_second"]
                ),
            )
        )
        seen.add(gpu_id)
    return tuple(gpus), profiles


def _expand_layer_values(
    profile: Mapping[str, Any],
    num_layers: int,
    explicit_key: str,
    default_key: str,
) -> tuple[float, ...]:
    explicit = profile.get(explicit_key)
    if explicit is not None:
        if not isinstance(explicit, list):
            raise ValueError(f"{explicit_key} must be a list")
        return tuple(float(value) for value in explicit)
    return (float(profile[default_key]),) * num_layers


def _load_model(config_dir: Path, model_name: str) -> ModelProfile:
    data = load_yaml(config_dir / "model_profiles.yaml")
    models = _require_mapping(data.get("models"), "models")
    if model_name not in models:
        raise ValueError(f"Unknown model profile: {model_name}")
    profile = _require_mapping(models[model_name], f"models.{model_name}")
    num_layers = int(profile["num_layers"])
    return ModelProfile(
        name=model_name,
        num_layers=num_layers,
        token_bytes=float(profile["token_bytes"]),
        activation_bytes_per_token=float(profile["activation_bytes_per_token"]),
        layer_compute_units_per_token=_expand_layer_values(
            profile,
            num_layers,
            "layer_compute_units_per_token",
            "default_layer_compute_units_per_token",
        ),
        layer_memory_gb=_expand_layer_values(
            profile,
            num_layers,
            "layer_memory_gb",
            "default_layer_memory_gb",
        ),
    )


def _load_placements(experiment: Mapping[str, Any]) -> dict[str, LayerPlacement]:
    raw_placements = _require_mapping(experiment.get("placements"), "placements")
    placements: dict[str, LayerPlacement] = {}
    for name, raw_intervals in raw_placements.items():
        interval_data = _require_mapping(raw_intervals, f"placements.{name}")
        intervals: dict[str, LayerInterval] = {}
        for gpu_id, bounds in interval_data.items():
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError(
                    f"Placement interval for {gpu_id} must be [start, end]"
                )
            intervals[str(gpu_id)] = LayerInterval(int(bounds[0]), int(bounds[1]))
        placements[str(name)] = LayerPlacement(str(name), intervals)
    return placements


def _load_validation_cases(experiment: Mapping[str, Any]) -> tuple[ValidationCase, ...]:
    raw_cases = experiment.get("validation_cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("validation_cases must be a non-empty list")
    return tuple(
        ValidationCase(
            name=str(case["name"]),
            placement_name=str(case["placement"]),
            network_topology_file=str(case["network_topology"]),
            expected_max_flow=float(case["expected_max_flow"]),
            expected_min_cut=float(case["expected_min_cut"]),
        )
        for case in raw_cases
    )


def load_simulation_inputs(config_dir: str | Path) -> SimulationInputs:
    """Load model, GPU, provider, placement, and experiment settings from YAML."""

    root = Path(config_dir)
    experiment = load_yaml(root / "experiment.yaml")
    gpus, profiles = _load_gpus(root)
    model = _load_model(root, str(experiment["model"]))
    placements = _load_placements(experiment)

    provider_name = str(experiment["throughput_provider"]).lower()
    if provider_name == "analytical":
        provider: ThroughputProvider = AnalyticalThroughputProvider()
    elif provider_name == "profiled":
        provider = ProfiledThroughputProvider(profiles)
    else:
        raise ValueError(f"Unknown throughput_provider: {provider_name}")

    allow_partial = bool(experiment.get("allow_partial_inference", False))
    if allow_partial:
        raise NotImplementedError("Phase 1 requires allow_partial_inference: false")

    cases = _load_validation_cases(experiment)
    for case in cases:
        if case.placement_name not in placements:
            raise ValueError(
                f"Validation case {case.name} refers to unknown placement "
                f"{case.placement_name}"
            )

    return SimulationInputs(
        model=model,
        gpus=gpus,
        profiles=profiles,
        placements=placements,
        throughput_provider=provider,
        allow_partial_inference=allow_partial,
        random_seed=int(experiment.get("random_seed", 0)),
        validation_cases=cases,
    )


def load_topology(
    config_dir: str | Path,
    topology_file: str,
    gpus: tuple[GPUNode, ...],
) -> ClusterTopology:
    """Load explicit directed links from one network topology YAML file."""

    data = load_yaml(Path(config_dir) / topology_file)
    raw_links = data.get("links")
    if not isinstance(raw_links, list):
        raise ValueError("links must be a list")
    links = tuple(
        NetworkLink(
            source=str(link["source"]),
            target=str(link["target"]),
            bandwidth_mbps=float(link["bandwidth_mbps"]),
        )
        for link in raw_links
    )
    return ClusterTopology.from_iterables(gpus, links)


def run_validation_case(
    config_dir: str | Path,
    inputs: SimulationInputs,
    case: ValidationCase,
    *,
    tolerance: float = 1e-9,
) -> SimulationRun:
    """Build and solve one configuration-defined validation case."""

    topology = load_topology(config_dir, case.network_topology_file, inputs.gpus)
    serving_graph = build_serving_graph(
        topology,
        inputs.model,
        inputs.placements[case.placement_name],
        inputs.throughput_provider,
        allow_partial_inference=inputs.allow_partial_inference,
    )
    result = solve_max_flow(serving_graph, tolerance=tolerance)
    if abs(result.max_flow_value - case.expected_max_flow) > tolerance:
        raise AssertionError(
            f"Case {case.name}: expected max flow {case.expected_max_flow}, "
            f"got {result.max_flow_value}"
        )
    if abs(result.min_cut_value - case.expected_min_cut) > tolerance:
        raise AssertionError(
            f"Case {case.name}: expected min cut {case.expected_min_cut}, "
            f"got {result.min_cut_value}"
        )
    return SimulationRun(case=case, serving_graph=serving_graph, result=result)


def run_all_validation_cases(config_dir: str | Path) -> tuple[SimulationRun, ...]:
    """Run every numerical case declared in ``experiment.yaml``."""

    inputs = load_simulation_inputs(config_dir)
    return tuple(
        run_validation_case(config_dir, inputs, case)
        for case in inputs.validation_cases
    )

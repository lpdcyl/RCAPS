"""Shared, configuration-driven machinery for Phase 3.5 experiments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from experiments.phase3_common import (
    Phase3Context,
    carbon_intensities,
    json_float_mapping,
    load_phase3_context,
)
from src.analysis.breakpoint import (
    PlacementSignature,
    detect_placement_breakpoints,
    logical_edge_set,
    placement_signature,
    serialize_placement_signature,
)
from src.analysis.placement_boundary import (
    ValidatedPlacementBoundary,
    validate_placement_boundary,
)
from src.analysis.routing_gap import routing_gap
from src.carbon.config import Phase35ExperimentConfig, load_phase35_experiment
from src.carbon.model import CarbonCostModel, EnergyProvider, MultipliedEnergyProvider
from src.graph.serving_graph import LayerPlacement, build_serving_graph
from src.graph.topology import ClusterTopology, GPUNode, with_cross_region_bandwidth
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.placement_milp import (
    PlacementMILPResult,
    solve_carbon_aware_placement,
    solve_throughput_optimal_placement,
)
from src.utils.config import bandwidth_mbps_to_activation_tokens_per_second


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


@dataclass(frozen=True, slots=True)
class Phase35Context:
    phase3: Phase3Context
    config: Phase35ExperimentConfig


@dataclass(frozen=True, slots=True)
class SweepRun:
    summary: pd.DataFrame
    topology: ClusterTopology
    energy_provider: EnergyProvider
    helix: PlacementMILPResult
    placements: tuple[LayerPlacement, ...]
    edge_sets: tuple[frozenset[tuple[str, str, str]], ...]
    study: str
    scenario: str
    rho: float
    energy_scenario: str
    bandwidth_mbps: float
    capacity_tokens_per_second: float


def load_phase35_context(config_dir: str | Path = CONFIG_DIR) -> Phase35Context:
    return Phase35Context(
        load_phase3_context(config_dir), load_phase35_experiment(config_dir)
    )


def output_path(
    context: Phase35Context, key: str, output_dir: str | Path | None = None
) -> Path:
    configured = context.config.outputs[key]
    return (
        PROJECT_ROOT / configured
        if output_dir is None
        else Path(output_dir) / Path(configured).name
    )


def topology_with_gpu_scenario(
    base: ClusterTopology, gpu_types: Mapping[str, str]
) -> ClusterTopology:
    """Replace GPU types/capabilities while preserving ids, regions, and links."""

    if set(gpu_types) != set(base.gpus):
        missing = sorted(set(base.gpus) - set(gpu_types))
        extra = sorted(set(gpu_types) - set(base.gpus))
        raise ValueError(f"GPU scenario id mismatch; missing={missing}, extra={extra}")
    templates: dict[str, GPUNode] = {}
    for gpu in base.gpus.values():
        templates.setdefault(gpu.gpu_type, gpu)
    unknown = sorted(set(gpu_types.values()) - set(templates))
    if unknown:
        raise ValueError(f"GPU scenario uses unknown types: {unknown}")
    gpus = []
    for gpu_id, original in sorted(base.gpus.items()):
        template = templates[gpu_types[gpu_id]]
        gpus.append(
            GPUNode(
                gpu_id,
                original.region,
                template.gpu_type,
                template.memory_gb,
                template.effective_compute_units_per_second,
            )
        )
    return ClusterTopology.from_iterables(gpus, base.links)


def capacity_tokens_to_mbps(capacity: float, activation_bytes: float) -> float:
    if capacity <= 0 or activation_bytes <= 0:
        raise ValueError("Capacity and activation size must be positive")
    return capacity * 8.0 * activation_bytes / 1_000_000.0


def _ci_for_ratio(context: Phase35Context, ratio: float) -> dict[str, float]:
    config = context.phase3.config
    values = dict(config.fixed_carbon_intensity)
    if config.sweep_region == "A" and "B" in values:
        values["A"] = float(ratio) * values["B"]
    elif config.sweep_region == "B" and "A" in values:
        if ratio <= 0:
            raise ValueError("CI_A / CI_B ratio must be positive")
        values["B"] = values["A"] / float(ratio)
    else:
        raise ValueError("Phase 3.5 requires a two-region A/B CI sweep")
    return values


def _region_share(metrics: object, region: str) -> float:
    return float(getattr(metrics, "region_flow_share").get(region, 0.0))


def run_ci_sweep(
    context: Phase35Context,
    *,
    study: str,
    scenario: str,
    rho: float,
    topology: ClusterTopology,
    energy_provider: EnergyProvider | None = None,
    energy_scenario: str = "baseline",
    capacity_tokens_per_second: float | None = None,
) -> SweepRun:
    """Run one complete CI sweep with a scenario-specific Helix baseline."""

    phase3 = context.phase3
    provider = phase3.throughput_provider
    model = phase3.simulation.model
    energy = phase3.energy_provider if energy_provider is None else energy_provider
    if capacity_tokens_per_second is None:
        capacity_tokens_per_second = context.config.baseline_capacity_tokens_per_second
    bandwidth = capacity_tokens_to_mbps(
        capacity_tokens_per_second, model.activation_bytes_per_token
    )
    topology = with_cross_region_bandwidth(topology, bandwidth)
    helix = solve_throughput_optimal_placement(topology, model, provider)
    target = float(rho) * helix.validated_max_flow
    helix_signature = placement_signature(helix.placement)
    helix_serving = build_serving_graph(topology, model, helix.placement, provider)
    rows: list[dict[str, object]] = []
    placements: list[LayerPlacement] = []
    edge_sets: list[frozenset[tuple[str, str, str]]] = []
    for sweep_value in phase3.config.sweep_values:
        intensities = carbon_intensities(phase3.config, sweep_value)
        routing_model = CarbonCostModel.build(
            topology,
            model,
            helix.placement,
            energy,
            intensities,
            phase=phase3.config.phase,
            batch_size=phase3.config.batch_size,
        )
        routing = solve_carbon_aware_flow(helix_serving, routing_model, target)
        joint = solve_carbon_aware_placement(
            topology,
            model,
            provider,
            energy,
            intensities,
            target,
            phase=phase3.config.phase,
            batch_size=phase3.config.batch_size,
        )
        gap = routing_gap(
            routing.metrics.carbon_g_per_second, joint.carbon_g_per_second
        )
        joint_signature = placement_signature(joint.placement)
        joint_serving = build_serving_graph(topology, model, joint.placement, provider)
        placements.append(joint.placement)
        edge_sets.append(logical_edge_set(joint_serving))
        ci_a = float(intensities["A"])
        ci_b = float(intensities["B"])
        rows.append(
            {
                "study": study,
                "scenario": scenario,
                "rho": float(rho),
                "energy_scenario": energy_scenario,
                "ci_a": ci_a,
                "ci_b": ci_b,
                "ci_ratio": ci_a / ci_b,
                "bandwidth": bandwidth,
                "bandwidth_mbps": bandwidth,
                "capacity_tokens_per_second": float(capacity_tokens_per_second),
                "F_H": helix.validated_max_flow,
                "F_target": target,
                "routing_carbon": routing.metrics.carbon_g_per_second,
                "joint_carbon": joint.carbon_g_per_second,
                "routing_gap": gap,
                "routing_sufficient_1pct": gap <= 0.01,
                "routing_sufficient_3pct": gap <= 0.03,
                "routing_sufficient_5pct": gap <= 0.05,
                "helix_placement": serialize_placement_signature(helix_signature),
                "carbon_placement": serialize_placement_signature(joint_signature),
                "placement_changed": joint_signature != helix_signature,
                "validated_cost_crossing": False,
                "degenerate_switch": False,
                "cross_region_flow_fraction_routing": (
                    routing.metrics.cross_region_flow_fraction
                ),
                "cross_region_flow_fraction_joint": (
                    joint.validated_flow.metrics.cross_region_flow_fraction
                ),
                "region_A_token_flow_routing": routing.metrics.region_token_flow.get(
                    "A", 0.0
                ),
                "region_B_token_flow_routing": routing.metrics.region_token_flow.get(
                    "B", 0.0
                ),
                "region_A_token_flow_joint": (
                    joint.validated_flow.metrics.region_token_flow.get("A", 0.0)
                ),
                "region_B_token_flow_joint": (
                    joint.validated_flow.metrics.region_token_flow.get("B", 0.0)
                ),
                "region_A_flow_share_routing": _region_share(routing.metrics, "A"),
                "region_B_flow_share_routing": _region_share(routing.metrics, "B"),
                "region_A_flow_share_joint": _region_share(
                    joint.validated_flow.metrics, "A"
                ),
                "region_B_flow_share_joint": _region_share(
                    joint.validated_flow.metrics, "B"
                ),
                "routing_flow_signature": json_float_mapping(
                    routing.metrics.path_flow_share
                ),
                "joint_flow_signature": json_float_mapping(
                    joint.validated_flow.metrics.path_flow_share
                ),
            }
        )
    return SweepRun(
        pd.DataFrame(rows),
        topology,
        energy,
        helix,
        tuple(placements),
        tuple(edge_sets),
        study,
        scenario,
        float(rho),
        energy_scenario,
        bandwidth,
        float(capacity_tokens_per_second),
    )


def validate_run_boundaries(
    context: Phase35Context, run: SweepRun
) -> tuple[SweepRun, tuple[ValidatedPlacementBoundary, ...]]:
    """Validate every adjacent placement signature switch in one sweep."""

    ratios = tuple(float(value) for value in run.summary["ci_ratio"])
    signatures = tuple(placement_signature(value) for value in run.placements)
    transitions = detect_placement_breakpoints(ratios, signatures, run.edge_sets)
    model = context.phase3.simulation.model
    provider = context.phase3.throughput_provider
    phase_config = context.phase3.config

    def evaluate(placement: LayerPlacement, ratio: float) -> float:
        serving = build_serving_graph(run.topology, model, placement, provider)
        carbon = CarbonCostModel.build(
            run.topology,
            model,
            placement,
            run.energy_provider,
            _ci_for_ratio(context, ratio),
            phase=phase_config.phase,
            batch_size=phase_config.batch_size,
        )
        result = solve_carbon_aware_flow(
            serving,
            carbon,
            run.rho * run.helix.validated_max_flow,
        )
        return result.metrics.carbon_g_per_second

    boundaries = tuple(
        validate_placement_boundary(
            transition,
            evaluate,
            degeneracy_tolerance=context.config.boundary_degeneracy_tolerance,
        )
        for transition in transitions
    )
    summary = run.summary.copy()
    for boundary in boundaries:
        mask = np.isclose(summary["ci_ratio"], boundary.right_ci_ratio)
        summary.loc[mask, "validated_cost_crossing"] = boundary.validated
        summary.loc[mask, "degenerate_switch"] = boundary.degenerate
    return replace(run, summary=summary), boundaries


def boundary_rows(
    run: SweepRun, boundaries: tuple[ValidatedPlacementBoundary, ...]
) -> list[dict[str, object]]:
    rows = []
    for value in boundaries:
        rows.append(
            {
                "study": run.study,
                "scenario": run.scenario,
                "rho": run.rho,
                "energy_scenario": run.energy_scenario,
                "bandwidth_mbps": run.bandwidth_mbps,
                "capacity_tokens_per_second": run.capacity_tokens_per_second,
                "left_ci_ratio": value.left_ci_ratio,
                "mid_ci_ratio": value.mid_ci_ratio,
                "right_ci_ratio": value.right_ci_ratio,
                "old_placement": serialize_placement_signature(value.old_placement),
                "new_placement": serialize_placement_signature(value.new_placement),
                "old_cost_left": value.old_cost_left,
                "new_cost_left": value.new_cost_left,
                "old_cost_mid": value.old_cost_mid,
                "new_cost_mid": value.new_cost_mid,
                "old_cost_right": value.old_cost_right,
                "new_cost_right": value.new_cost_right,
                "delta_left": value.delta_left,
                "delta_mid": value.delta_mid,
                "delta_right": value.delta_right,
                "cost_crossing": value.cost_crossing,
                "validated_placement_boundary": value.validated,
                "degenerate": value.degenerate,
                "migration_layer_count": value.migration_layer_count,
                "graph_edge_change": value.graph_edge_change,
            }
        )
    return rows


def aggregate_sweep(run: SweepRun) -> dict[str, object]:
    frame = run.summary
    signatures = frame["carbon_placement"].tolist()
    changes = sum(left != right for left, right in zip(signatures, signatures[1:]))
    return {
        "study": run.study,
        "scenario": run.scenario,
        "rho": run.rho,
        "energy_scenario": run.energy_scenario,
        "bandwidth_mbps": run.bandwidth_mbps,
        "capacity_tokens_per_second": run.capacity_tokens_per_second,
        "F_H": float(frame["F_H"].iloc[0]),
        "F_target": float(frame["F_target"].iloc[0]),
        "max_routing_gap": float(frame["routing_gap"].max()),
        "mean_routing_gap": float(frame["routing_gap"].mean()),
        "fraction_gap_gt_1pct": float((frame["routing_gap"] > 0.01).mean()),
        "fraction_gap_gt_3pct": float((frame["routing_gap"] > 0.03).mean()),
        "fraction_gap_gt_5pct": float((frame["routing_gap"] > 0.05).mean()),
        "routing_sufficient_fraction": float((frame["routing_gap"] <= 0.01).mean()),
        "validated_boundary_count": int(frame["validated_cost_crossing"].sum()),
        "placement_signature_change_count": int(changes),
    }


def energy_provider_for_scenario(
    context: Phase35Context, gpu_type: str | None, multiplier: float
) -> EnergyProvider:
    multipliers = {} if gpu_type is None else {gpu_type: float(multiplier)}
    return MultipliedEnergyProvider(context.phase3.energy_provider, multipliers)


def scenario_topology(context: Phase35Context, scenario: str) -> ClusterTopology:
    return topology_with_gpu_scenario(
        context.phase3.topology, context.config.gpu_scenarios[scenario]
    )


def actual_cross_region_capacity(
    topology: ClusterTopology, activation_bytes: float
) -> tuple[float, ...]:
    """Expose capacities actually present on cross-region physical links."""

    values = []
    for link in topology.links:
        source = topology.gpus.get(link.source)
        target = topology.gpus.get(link.target)
        if source is not None and target is not None and source.region != target.region:
            values.append(
                bandwidth_mbps_to_activation_tokens_per_second(
                    link.bandwidth_mbps, activation_bytes
                )
            )
    return tuple(values)

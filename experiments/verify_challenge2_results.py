"""Recompute representative Challenge 2 points from frozen inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from experiments.exp_challenge2 import _energy_provider
from experiments.phase35_common import (
    capacity_tokens_to_mbps,
    load_phase35_context,
    scenario_topology,
)
from src.analysis.breakpoint import placement_signature, serialize_placement_signature
from src.analysis.routing_gap import routing_gap
from src.carbon.config import load_cbgp_config
from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import build_serving_graph
from src.graph.topology import with_cross_region_bandwidth
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.cbgp import solve_cbgp
from src.optimizer.placement_milp import (
    solve_carbon_aware_placement,
    solve_throughput_optimal_placement,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"
RESULT_DIR = PROJECT_ROOT / "results/challenge2"


def _select_cases(points: pd.DataFrame) -> tuple[tuple[str, object], ...]:
    sufficient = points.loc[points["routing_sufficient"]].iloc[0]
    successful = points.loc[points["cbgp_reduction"].idxmax()]
    failure_pool = points.loc[
        points["placement_necessary"]
        & (points["gap_closed"].fillna(0.0) < 0.5)
    ].sort_values("routing_gap", ascending=False)
    failure = failure_pool.iloc[0]
    necessary_pool = points.loc[
        points["placement_necessary"]
        & ~points["scenario_id"].isin(
            [successful["scenario_id"], failure["scenario_id"]]
        )
    ].sort_values("routing_gap", ascending=False)
    necessary = necessary_pool.iloc[0]
    return (
        ("routing_sufficient", sufficient),
        ("placement_necessary", necessary),
        ("cbgp_success", successful),
        ("cbgp_failure", failure),
    )


def _manual_carbon(flow: object, costs: CarbonCostModel) -> float:
    return sum(
        value * costs.carbon_g_per_token(gpu_id)
        for gpu_id, value in flow.metrics.gpu_flow_tokens_per_second.items()
    )


def verify() -> pd.DataFrame:
    points = pd.read_csv(RESULT_DIR / "challenge2_point_results.csv")
    context = load_phase35_context(CONFIG_DIR)
    config = load_cbgp_config(CONFIG_DIR)
    model = context.phase3.simulation.model
    throughput_provider = context.phase3.throughput_provider
    phase = context.phase3.config.phase
    batch_size = context.phase3.config.batch_size
    rows: list[dict[str, object]] = []

    for role, point in _select_cases(points):
        topology = with_cross_region_bandwidth(
            scenario_topology(context, str(point["gpu_scenario"])),
            capacity_tokens_to_mbps(
                float(point["network_capacity"]),
                model.activation_bytes_per_token,
            ),
        )
        energy = _energy_provider(context, str(point["energy_scenario"]))
        helix = solve_throughput_optimal_placement(
            topology, model, throughput_provider
        )
        target = float(point["rho"]) * helix.validated_max_flow
        intensities = {
            "A": float(point["ci_a"]),
            "B": float(point["ci_b"]),
        }
        serving = build_serving_graph(
            topology, model, helix.placement, throughput_provider
        )
        routing_costs = CarbonCostModel.build(
            topology,
            model,
            helix.placement,
            energy,
            intensities,
            phase=phase,
            batch_size=batch_size,
        )
        routing = solve_carbon_aware_flow(
            serving,
            routing_costs,
            target,
            tolerance=config.solver_tolerance,
        )
        cbgp = solve_cbgp(
            topology,
            model,
            throughput_provider,
            energy,
            intensities,
            helix.placement,
            target,
            config,
            phase=phase,
            batch_size=batch_size,
        )
        oracle = solve_carbon_aware_placement(
            topology,
            model,
            throughput_provider,
            energy,
            intensities,
            target,
            phase=phase,
            batch_size=batch_size,
            tolerance=config.solver_tolerance,
        )
        cbgp_costs = CarbonCostModel.build(
            topology,
            model,
            cbgp.placement,
            energy,
            intensities,
            phase=phase,
            batch_size=batch_size,
        )
        oracle_costs = CarbonCostModel.build(
            topology,
            model,
            oracle.placement,
            energy,
            intensities,
            phase=phase,
            batch_size=batch_size,
        )

        routing_carbon = routing.metrics.carbon_g_per_second
        cbgp_carbon = cbgp.flow.metrics.carbon_g_per_second
        joint_carbon = oracle.carbon_g_per_second
        gap = routing_gap(routing_carbon, joint_carbon)
        reduction = (routing_carbon - cbgp_carbon) / routing_carbon
        oracle_gap = (cbgp_carbon - joint_carbon) / routing_carbon
        gap_closed = (
            float("nan")
            if gap <= min(config.placement_gap_thresholds)
            else (routing_carbon - cbgp_carbon) / (routing_carbon - joint_carbon)
        )
        carbon_arithmetic_errors = (
            abs(_manual_carbon(routing, routing_costs) - routing_carbon),
            abs(_manual_carbon(cbgp.flow, cbgp_costs) - cbgp_carbon),
            abs(
                _manual_carbon(oracle.validated_flow, oracle_costs)
                - joint_carbon
            ),
        )
        metric_errors = [
            abs(target - float(point["F_target"])),
            abs(routing_carbon - float(point["routing_carbon"])),
            abs(cbgp_carbon - float(point["cbgp_carbon"])),
            abs(joint_carbon - float(point["joint_carbon"])),
            abs(gap - float(point["routing_gap"])),
            abs(reduction - float(point["cbgp_reduction"])),
            abs(oracle_gap - float(point["oracle_gap"])),
            *carbon_arithmetic_errors,
        ]
        if not (np.isnan(gap_closed) and np.isnan(point["gap_closed"])):
            metric_errors.append(abs(gap_closed - float(point["gap_closed"])))
        signatures_match = (
            serialize_placement_signature(placement_signature(helix.placement))
            == point["initial_placement_signature"]
            and serialize_placement_signature(placement_signature(cbgp.placement))
            == point["cbgp_placement_signature"]
            and serialize_placement_signature(placement_signature(oracle.placement))
            == point["oracle_placement_signature"]
        )
        throughput_errors = (
            abs(routing.metrics.throughput - target),
            abs(cbgp.flow.metrics.throughput - target),
            abs(oracle.achieved_throughput - target),
        )
        max_error = max(*metric_errors, *throughput_errors)
        rows.append(
            {
                "role": role,
                "scenario_id": point["scenario_id"],
                "max_absolute_error": max_error,
                "signatures_match": signatures_match,
                "throughput_constraints_match": max(throughput_errors) <= 1e-8,
                "carbon_arithmetic_match": max(carbon_arithmetic_errors) <= 1e-12,
                "passed": (
                    max_error <= 1e-9
                    and signatures_match
                    and max(throughput_errors) <= 1e-8
                ),
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(RESULT_DIR / "challenge2_verification.csv", index=False)
    if not bool(result["passed"].all()):
        raise AssertionError("At least one Challenge 2 sample verification failed")
    return result


def main() -> None:
    result = verify()
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()

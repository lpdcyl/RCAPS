import pytest

from conftest import CONFIG_DIR
from src.carbon.model import CarbonCostModel, ConfiguredLinearEnergyProvider
from src.graph.serving_graph import build_serving_graph
from src.optimizer.carbon_flow import (
    scaled_helix_reference_flow,
    solve_carbon_aware_flow,
)
from src.optimizer.maxflow import solve_max_flow
from src.simulator.simulator import load_simulation_inputs, load_topology


def energy_provider() -> ConfiguredLinearEnergyProvider:
    return ConfiguredLinearEnergyProvider(
        {
            "A100": {"decode": {1: 0.100}},
            "L4": {"decode": {1: 0.055}},
            "T4": {"decode": {1: 0.085}},
        }
    )


def build_phase2(ci_a: float):
    inputs = load_simulation_inputs(CONFIG_DIR)
    topology = load_topology(CONFIG_DIR, "network_topology.yaml", inputs.gpus)
    placement = inputs.placements["placement_a"]
    serving = build_serving_graph(
        topology, inputs.model, placement, inputs.throughput_provider
    )
    maxflow = solve_max_flow(serving)
    carbon = CarbonCostModel.build(
        topology,
        inputs.model,
        placement,
        energy_provider(),
        {"A": ci_a, "B": 200.0},
        phase="decode",
        batch_size=1,
    )
    return serving, maxflow, carbon


def test_carbon_flow_meets_throughput_and_invariants() -> None:
    serving, maxflow, carbon = build_phase2(100.0)
    target = 0.95 * maxflow.max_flow_value
    result = solve_carbon_aware_flow(serving, carbon, target)
    assert result.metrics.throughput == pytest.approx(104.5)
    assert result.capacity_constraints_check
    assert result.conservation_check
    assert result.throughput_check


def test_fixed_flow_objective_equals_manual_gpu_carbon_sum() -> None:
    serving, maxflow, carbon = build_phase2(100.0)
    result = solve_carbon_aware_flow(
        serving, carbon, 0.95 * maxflow.max_flow_value
    )
    manual_carbon_g_per_second = sum(
        flow * carbon.carbon_g_per_token(gpu_id)
        for gpu_id, flow in result.metrics.gpu_flow_tokens_per_second.items()
    )
    assert result.metrics.carbon_g_per_second == pytest.approx(
        manual_carbon_g_per_second,
        abs=1e-12,
    )


def test_carbon_flow_not_worse_than_same_throughput_reference() -> None:
    serving, maxflow, carbon = build_phase2(400.0)
    target = 0.95 * maxflow.max_flow_value
    reference = scaled_helix_reference_flow(serving, maxflow, carbon, target)
    optimized = solve_carbon_aware_flow(serving, carbon, target)
    assert optimized.metrics.carbon_g_per_second <= reference.carbon_g_per_second + 1e-12


def test_ci_change_redistributes_fixed_placement_flow() -> None:
    serving_low, maxflow_low, carbon_low = build_phase2(50.0)
    serving_high, maxflow_high, carbon_high = build_phase2(800.0)
    low = solve_carbon_aware_flow(
        serving_low, carbon_low, 0.95 * maxflow_low.max_flow_value
    )
    high = solve_carbon_aware_flow(
        serving_high, carbon_high, 0.95 * maxflow_high.max_flow_value
    )
    assert low.metrics.path_flow_share != high.metrics.path_flow_share
    assert low.metrics.throughput == pytest.approx(high.metrics.throughput)


def test_fixed_placement_and_graph_are_not_modified() -> None:
    serving, maxflow, carbon = build_phase2(300.0)
    nodes_before = set(serving.graph.nodes)
    edges_before = set(serving.graph.edges)
    solve_carbon_aware_flow(serving, carbon, 0.95 * maxflow.max_flow_value)
    assert set(serving.graph.nodes) == nodes_before
    assert set(serving.graph.edges) == edges_before

import pytest

from conftest import make_topology
from src.graph.serving_graph import AnalyticalThroughputProvider, build_serving_graph
from src.optimizer.maxflow import solve_max_flow


def solve(topology, model, placement):
    serving = build_serving_graph(
        topology, model, placement, AnalyticalThroughputProvider()
    )
    return solve_max_flow(serving)


def test_placement_a_flow_110(phase1_topology, phase1_model, placement_a) -> None:
    result = solve(phase1_topology, phase1_model, placement_a)
    assert result.max_flow_value == pytest.approx(110)
    assert result.min_cut_value == pytest.approx(110)


def test_placement_b_flow_100(phase1_topology, phase1_model, placement_b) -> None:
    result = solve(phase1_topology, phase1_model, placement_b)
    assert result.max_flow_value == pytest.approx(100)
    assert result.min_cut_value == pytest.approx(100)


def test_placement_a_low_bandwidth_flow_80(
    phase1_gpus, phase1_model, placement_a
) -> None:
    topology = make_topology(phase1_gpus, cross_capacity=20)
    result = solve(topology, phase1_model, placement_a)
    assert result.max_flow_value == pytest.approx(80)
    assert result.min_cut_value == pytest.approx(80)


def test_maxflow_equals_mincut(phase1_topology, phase1_model, placement_a) -> None:
    result = solve(phase1_topology, phase1_model, placement_a)
    assert result.max_flow_min_cut_check
    assert result.max_flow_value == pytest.approx(result.min_cut_value)


def test_capacity_constraints(phase1_topology, phase1_model, placement_a) -> None:
    result = solve(phase1_topology, phase1_model, placement_a)
    assert result.capacity_constraints_check
    for edge, flow in result.positive_flow_edges.items():
        assert 0 <= flow <= result.edge_capacities[edge] + 1e-9


def test_flow_conservation(phase1_topology, phase1_model, placement_a) -> None:
    result = solve(phase1_topology, phase1_model, placement_a)
    assert result.conservation_check


def test_expected_low_bandwidth_cut(
    phase1_gpus, phase1_model, placement_a
) -> None:
    topology = make_topology(phase1_gpus, cross_capacity=20)
    result = solve(topology, phase1_model, placement_a)
    expected = {
        ("c1_out", "c4_in"),
        ("c2_out", "c4_in"),
        ("c3_out", "c5_in"),
        ("c3_out", "c6_in"),
    }
    assert set(result.cut_edges) == expected
    assert sum(result.cut_edges.values()) == pytest.approx(80)

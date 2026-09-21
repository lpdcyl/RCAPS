import pytest

from src.analysis.breakpoint import placement_signature
from src.analysis.carbon_bottleneck import analyze_carbon_bottlenecks
from src.carbon.config import CBGPConfig
from src.carbon.model import CarbonCostModel, ConfiguredLinearEnergyProvider
from src.graph.serving_graph import (
    LayerInterval,
    LayerPlacement,
    ModelProfile,
    ProfiledThroughputProvider,
    build_serving_graph,
)
from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
    GPUNode,
    NetworkLink,
)
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.cbgp import generate_local_boundary_candidates, solve_cbgp
from src.optimizer.placement_milp import solve_carbon_aware_placement


def _config(*, max_shift: int = 2, min_improvement: float = 1e-6) -> CBGPConfig:
    return CBGPConfig(
        bottleneck_utilization_threshold=0.75,
        max_boundary_shift=max_shift,
        max_iterations=4,
        min_relative_improvement=min_improvement,
        solver_tolerance=1e-8,
        placement_gap_thresholds=(0.01, 0.03, 0.05),
        random_seed=7,
    )


def _case(
    *,
    boundary: int = 3,
    network_capacity: float = 200.0,
    compute_capacity: float = 100.0,
    memory_b: float = 4.0,
):
    model = ModelProfile("cbgp-toy", 4, 4, 1_000, (1.0,) * 4, (1.0,) * 4)
    gpus = [
        GPUNode("a", "A", "same", 4.0, 100.0),
        GPUNode("b", "B", "same", memory_b, 100.0),
    ]
    network_mbps = network_capacity * 8.0 * model.activation_bytes_per_token / 1_000_000.0
    topology = ClusterTopology.from_iterables(
        gpus,
        [
            NetworkLink(COORDINATOR_SOURCE, "a", 10.0),
            NetworkLink(COORDINATOR_SOURCE, "b", 10.0),
            NetworkLink("a", COORDINATOR_SINK, 10.0),
            NetworkLink("b", COORDINATOR_SINK, 10.0),
            NetworkLink("a", "b", network_mbps),
            NetworkLink("b", "a", network_mbps),
        ],
    )
    placement = LayerPlacement(
        "initial",
        {
            "a": LayerInterval(0, boundary),
            "b": LayerInterval(boundary, 4),
        },
    )
    throughput = ProfiledThroughputProvider(
        {"same": {1: compute_capacity, 2: compute_capacity, 3: compute_capacity}}
    )
    energy = ConfiguredLinearEnergyProvider(
        {"same": {"decode": {1: 1.0}}}
    )
    return topology, model, placement, throughput, energy


def _flow_and_report(
    *,
    boundary: int = 3,
    target: float = 80.0,
    network_capacity: float = 200.0,
    compute_capacity: float = 100.0,
    memory_b: float = 4.0,
    intensities: dict[str, float] | None = None,
    threshold: float = 0.75,
):
    topology, model, placement, throughput, energy = _case(
        boundary=boundary,
        network_capacity=network_capacity,
        compute_capacity=compute_capacity,
        memory_b=memory_b,
    )
    ci = {"A": 200.0, "B": 50.0} if intensities is None else intensities
    serving = build_serving_graph(topology, model, placement, throughput)
    carbon = CarbonCostModel.build(
        topology,
        model,
        placement,
        energy,
        ci,
        phase="decode",
        batch_size=1,
    )
    flow = solve_carbon_aware_flow(serving, carbon, target)
    report = analyze_carbon_bottlenecks(
        serving,
        carbon,
        flow,
        utilization_threshold=threshold,
    )
    return topology, model, placement, throughput, energy, flow, report


def test_compute_bottleneck_detection_marks_saturated_gpus() -> None:
    *_, report = _flow_and_report(target=80.0, compute_capacity=100.0)
    assert report.compute_utilization == pytest.approx({"a": 0.8, "b": 0.8})
    assert report.saturated_compute_gpus == ("a", "b")


def test_network_bottleneck_detection_marks_saturated_edge() -> None:
    *_, report = _flow_and_report(
        target=100.0,
        network_capacity=100.0,
        compute_capacity=120.0,
        threshold=0.99,
    )
    assert report.network_utilization[("a_out", "b_in")] == pytest.approx(1.0)
    assert report.saturated_network_edges == (("a_out", "b_in"),)


def test_candidate_generation_produces_both_one_layer_shifts() -> None:
    topology, model, placement, *_, report = _flow_and_report(boundary=2)
    candidates = generate_local_boundary_candidates(
        placement,
        report,
        topology,
        model,
        max_boundary_shift=1,
        bottleneck_guided=False,
    )
    boundaries = sorted(value.intervals["a"].end_layer for value in candidates)
    assert boundaries == [1, 3]


def test_memory_invalid_candidate_is_filtered() -> None:
    topology, model, placement, *_, report = _flow_and_report(
        boundary=3, memory_b=2.0
    )
    candidates = generate_local_boundary_candidates(
        placement,
        report,
        topology,
        model,
        max_boundary_shift=2,
        bottleneck_guided=False,
    )
    assert candidates
    assert all(value.intervals["b"].layer_count <= 2 for value in candidates)


def test_generated_candidates_preserve_continuity_and_legality() -> None:
    topology, model, placement, throughput, *_, report = _flow_and_report(boundary=2)
    candidates = generate_local_boundary_candidates(
        placement,
        report,
        topology,
        model,
        max_boundary_shift=1,
        bottleneck_guided=False,
    )
    for candidate in candidates:
        candidate.validate(topology, model)
        assert candidate.intervals["a"].end_layer == candidate.intervals["b"].start_layer
        build_serving_graph(topology, model, candidate, throughput)


def test_cbgp_is_deterministic() -> None:
    topology, model, placement, throughput, energy = _case()
    arguments = (
        topology,
        model,
        throughput,
        energy,
        {"A": 200.0, "B": 50.0},
        placement,
        80.0,
        _config(),
    )
    first = solve_cbgp(*arguments, phase="decode", batch_size=1)
    second = solve_cbgp(*arguments, phase="decode", batch_size=1)
    assert placement_signature(first.placement) == placement_signature(second.placement)


def test_symmetric_no_benefit_case_keeps_placement() -> None:
    topology, model, placement, throughput, energy = _case(boundary=2)
    result = solve_cbgp(
        topology,
        model,
        throughput,
        energy,
        {"A": 100.0, "B": 100.0},
        placement,
        80.0,
        _config(),
        phase="decode",
        batch_size=1,
    )
    assert not result.placement_changed
    assert result.flow.metrics.carbon_g_per_second == pytest.approx(
        result.initial_flow.metrics.carbon_g_per_second
    )


def test_beneficial_local_shift_reduces_carbon() -> None:
    topology, model, placement, throughput, energy = _case(boundary=3)
    result = solve_cbgp(
        topology,
        model,
        throughput,
        energy,
        {"A": 200.0, "B": 50.0},
        placement,
        80.0,
        _config(),
        phase="decode",
        batch_size=1,
    )
    assert result.placement_changed
    assert result.placement.intervals["b"].layer_count == 3
    assert result.flow.metrics.carbon_g_per_second < result.initial_flow.metrics.carbon_g_per_second


def test_oracle_ordering_holds_for_beneficial_case() -> None:
    topology, model, placement, throughput, energy = _case(boundary=3)
    intensities = {"A": 200.0, "B": 50.0}
    cbgp = solve_cbgp(
        topology,
        model,
        throughput,
        energy,
        intensities,
        placement,
        80.0,
        _config(),
        phase="decode",
        batch_size=1,
    )
    oracle = solve_carbon_aware_placement(
        topology,
        model,
        throughput,
        energy,
        intensities,
        80.0,
        phase="decode",
        batch_size=1,
    )
    assert oracle.carbon_g_per_second <= cbgp.flow.metrics.carbon_g_per_second + 1e-9
    assert cbgp.flow.metrics.carbon_g_per_second <= cbgp.initial_flow.metrics.carbon_g_per_second + 1e-9


def test_equivalent_candidates_terminate_without_cycle() -> None:
    topology, model, placement, throughput, energy = _case(boundary=2)
    result = solve_cbgp(
        topology,
        model,
        throughput,
        energy,
        {"A": 100.0, "B": 100.0},
        placement,
        80.0,
        _config(min_improvement=0.0),
        phase="decode",
        batch_size=1,
    )
    assert result.termination_reason == "improvement_below_threshold"
    assert result.visited_placement_count == 1
    assert len(result.iterations) == 1

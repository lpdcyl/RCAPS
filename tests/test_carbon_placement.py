import pytest

from src.analysis.breakpoint import placement_signature
from src.carbon.model import (
    CarbonCostModel,
    ConfiguredLinearEnergyProvider,
    ConstantCIProvider,
)
from src.graph.serving_graph import ModelProfile, ProfiledThroughputProvider, build_serving_graph
from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
    GPUNode,
    NetworkLink,
)
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.placement_milp import (
    solve_carbon_aware_placement,
    solve_throughput_optimal_placement,
)


def _carbon_transition_case():
    model = ModelProfile("carbon-toy", 4, 4, 1_000, (1.0,) * 4, (1.0,) * 4)
    gpus = [
        GPUNode("a", "A", "same", 4, 100),
        GPUNode("b", "B", "same", 4, 100),
    ]
    topology = ClusterTopology.from_iterables(
        gpus,
        [
            NetworkLink(COORDINATOR_SOURCE, "a", 1.0),
            NetworkLink(COORDINATOR_SOURCE, "b", 1.0),
            NetworkLink("a", COORDINATOR_SINK, 1.0),
            NetworkLink("b", COORDINATOR_SINK, 1.0),
            NetworkLink("a", "b", 1.0),
            NetworkLink("b", "a", 1.0),
        ],
    )
    throughput = ProfiledThroughputProvider({"same": {1: 100.0, 3: 100.0}})
    energy = ConfiguredLinearEnergyProvider({"same": {"decode": {1: 1.0}}})
    return topology, model, throughput, energy


def test_joint_carbon_is_not_worse_and_meets_target() -> None:
    topology, model, throughput, energy = _carbon_transition_case()
    helix = solve_throughput_optimal_placement(topology, model, throughput)
    target = 0.8 * helix.validated_max_flow
    intensities = {"A": 50.0, "B": 200.0}
    serving = build_serving_graph(topology, model, helix.placement, throughput)
    carbon_model = CarbonCostModel.build(
        topology,
        model,
        helix.placement,
        energy,
        intensities,
        phase="decode",
        batch_size=1,
    )
    routing = solve_carbon_aware_flow(serving, carbon_model, target)
    joint = solve_carbon_aware_placement(
        topology,
        model,
        throughput,
        energy,
        intensities,
        target,
        phase="decode",
        batch_size=1,
    )
    assert joint.achieved_throughput == pytest.approx(target)
    assert joint.carbon_g_per_second <= routing.metrics.carbon_g_per_second + 1e-10


def test_ci_flip_changes_provably_preferred_placement() -> None:
    topology, model, throughput, energy = _carbon_transition_case()
    helix = solve_throughput_optimal_placement(topology, model, throughput)
    target = 0.8 * helix.validated_max_flow
    low_a = solve_carbon_aware_placement(
        topology,
        model,
        throughput,
        energy,
        {"A": 50.0, "B": 200.0},
        target,
        phase="decode",
        batch_size=1,
    )
    high_a = solve_carbon_aware_placement(
        topology,
        model,
        throughput,
        energy,
        {"A": 800.0, "B": 200.0},
        target,
        phase="decode",
        batch_size=1,
    )
    assert low_a.selected_layer_counts["a"] == 3
    assert high_a.selected_layer_counts["b"] == 3
    assert placement_signature(low_a.placement) != placement_signature(high_a.placement)


def test_joint_placement_uses_one_ci_snapshot_and_shared_cost_semantics() -> None:
    topology, model, throughput, energy = _carbon_transition_case()
    target = 0.8 * solve_throughput_optimal_placement(
        topology, model, throughput
    ).validated_max_flow
    intensities = {"A": 50.0, "B": 200.0}

    class CountingProvider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, float | None]] = []

        def get_ci(self, region: str, timestamp: float | None = None) -> float:
            self.calls.append((region, timestamp))
            return intensities[region]

    provider = CountingProvider()
    joint = solve_carbon_aware_placement(
        topology,
        model,
        throughput,
        energy,
        provider,
        target,
        phase="decode",
        batch_size=1,
        timestamp=456.0,
    )
    assert provider.calls == [("A", 456.0), ("B", 456.0)]

    selected_costs = CarbonCostModel.build(
        topology,
        model,
        joint.placement,
        energy,
        ConstantCIProvider(intensities),
        phase="decode",
        batch_size=1,
    )
    manual_carbon_g_per_second = sum(
        flow * selected_costs.carbon_g_per_token(gpu_id)
        for gpu_id, flow in joint.validated_flow.metrics.gpu_flow_tokens_per_second.items()
    )
    assert joint.carbon_g_per_second == pytest.approx(
        manual_carbon_g_per_second,
        abs=1e-12,
    )
    assert joint.milp_carbon_g_per_second == pytest.approx(
        manual_carbon_g_per_second,
        abs=1e-12,
    )

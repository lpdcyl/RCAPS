from itertools import product

import pytest

from src.graph.serving_graph import (
    AnalyticalThroughputProvider,
    LayerInterval,
    LayerPlacement,
    ModelProfile,
    build_serving_graph,
)
from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
    GPUNode,
    NetworkLink,
    with_cross_region_bandwidth,
)
from src.optimizer.maxflow import solve_max_flow
from src.optimizer.placement_milp import solve_throughput_optimal_placement


def _model(layers: int = 4) -> ModelProfile:
    return ModelProfile(
        "tiny",
        layers,
        4,
        1_000,
        (1.0,) * layers,
        (1.0,) * layers,
    )


def _complete_topology() -> ClusterTopology:
    gpus = [
        GPUNode("g1", "A", "fast", 4, 40),
        GPUNode("g2", "A", "medium", 4, 30),
        GPUNode("g3", "A", "slow", 4, 20),
    ]
    links: list[NetworkLink] = []
    for gpu in gpus:
        links.append(NetworkLink(COORDINATOR_SOURCE, gpu.gpu_id, 1.0))
        links.append(NetworkLink(gpu.gpu_id, COORDINATOR_SINK, 1.0))
    for source in gpus:
        for target in gpus:
            if source != target:
                links.append(NetworkLink(source.gpu_id, target.gpu_id, 1.0))
    return ClusterTopology.from_iterables(gpus, links)


def _enumerated_best(topology: ClusterTopology, model: ModelProfile) -> float:
    provider = AnalyticalThroughputProvider()
    intervals = [
        LayerInterval(start, end)
        for start in range(model.num_layers)
        for end in range(start + 1, model.num_layers + 1)
    ]
    best = 0.0
    for candidate in product(intervals, repeat=len(topology.gpus)):
        placement = LayerPlacement("enumerated", dict(zip(sorted(topology.gpus), candidate)))
        try:
            serving = build_serving_graph(topology, model, placement, provider)
        except ValueError:
            continue
        best = max(best, solve_max_flow(serving).max_flow_value)
    return best


def test_milp_matches_exhaustive_tiny_oracle() -> None:
    topology = _complete_topology()
    model = _model()
    result = solve_throughput_optimal_placement(
        topology, model, AnalyticalThroughputProvider()
    )
    assert result.milp_throughput == pytest.approx(_enumerated_best(topology, model))
    assert result.validated_max_flow == pytest.approx(result.milp_throughput)
    result.placement.validate(topology, model)


def test_cross_region_bandwidth_changes_required_pipeline_throughput() -> None:
    model = _model()
    gpus = [
        GPUNode("a", "A", "same", 4, 40),
        GPUNode("b", "B", "same", 4, 40),
    ]
    base = ClusterTopology.from_iterables(
        gpus,
        [
            NetworkLink(COORDINATOR_SOURCE, "a", 1.0),
            NetworkLink("b", COORDINATOR_SINK, 1.0),
            NetworkLink("a", "b", 0.08),
        ],
    )
    provider = AnalyticalThroughputProvider()
    high = solve_throughput_optimal_placement(
        with_cross_region_bandwidth(base, 0.08), model, provider
    )
    low = solve_throughput_optimal_placement(
        with_cross_region_bandwidth(base, 0.04), model, provider
    )
    assert high.validated_max_flow == pytest.approx(10.0)
    assert low.validated_max_flow == pytest.approx(5.0)
    assert base.get_link("a", "b").bandwidth_mbps == pytest.approx(0.08)
    assert high.placement.intervals.keys() == low.placement.intervals.keys()


def test_non_homogeneous_layers_are_rejected() -> None:
    topology = _complete_topology()
    model = ModelProfile(
        "heterogeneous",
        4,
        4,
        1_000,
        (1.0, 1.0, 2.0, 1.0),
        (1.0,) * 4,
    )
    with pytest.raises(NotImplementedError, match="homogeneous layer compute"):
        solve_throughput_optimal_placement(
            topology, model, AnalyticalThroughputProvider()
        )

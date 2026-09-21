import pytest

from src.graph.serving_graph import (
    SOURCE,
    SINK,
    AnalyticalThroughputProvider,
    LayerPlacement,
    build_serving_graph,
    gpu_in_node,
    gpu_out_node,
)
from src.graph.topology import ClusterTopology, NetworkLink


def test_strict_logical_edge_validity(
    phase1_topology, phase1_model, placement_a
) -> None:
    serving = build_serving_graph(
        phase1_topology,
        phase1_model,
        placement_a,
        AnalyticalThroughputProvider(),
    )
    assert serving.graph.has_edge(gpu_out_node("c1"), gpu_in_node("c3"))
    assert serving.graph.has_edge(gpu_out_node("c4"), gpu_in_node("c5"))


def test_invalid_layer_connection(
    phase1_topology, phase1_model, placement_a
) -> None:
    serving = build_serving_graph(
        phase1_topology,
        phase1_model,
        placement_a,
        AnalyticalThroughputProvider(),
    )
    assert not serving.graph.has_edge(gpu_out_node("c1"), gpu_in_node("c5"))
    assert not serving.graph.has_edge(gpu_out_node("c3"), gpu_in_node("c4"))


def test_physical_link_is_required(
    phase1_topology, phase1_model, placement_a
) -> None:
    kept_links = tuple(
        link
        for link in phase1_topology.links
        if (link.source, link.target) != ("c1", "c3")
    )
    topology = ClusterTopology(phase1_topology.gpus, kept_links)
    serving = build_serving_graph(
        topology, phase1_model, placement_a, AnalyticalThroughputProvider()
    )
    assert not serving.graph.has_edge(gpu_out_node("c1"), gpu_in_node("c3"))


def test_source_edge_only_for_first_layer(
    phase1_topology, phase1_model, placement_a
) -> None:
    serving = build_serving_graph(
        phase1_topology,
        phase1_model,
        placement_a,
        AnalyticalThroughputProvider(),
    )
    assert serving.graph.has_edge(SOURCE, gpu_in_node("c1"))
    assert serving.graph.has_edge(SOURCE, gpu_in_node("c2"))
    assert not serving.graph.has_edge(SOURCE, gpu_in_node("c3"))


def test_sink_edge_only_for_last_layer(
    phase1_topology, phase1_model, placement_a
) -> None:
    serving = build_serving_graph(
        phase1_topology,
        phase1_model,
        placement_a,
        AnalyticalThroughputProvider(),
    )
    assert serving.graph.has_edge(gpu_out_node("c5"), SINK)
    assert serving.graph.has_edge(gpu_out_node("c6"), SINK)
    assert not serving.graph.has_edge(gpu_out_node("c4"), SINK)


def test_partial_inference_is_rejected(
    phase1_topology, phase1_model, placement_a
) -> None:
    with pytest.raises(NotImplementedError, match="partial inference"):
        build_serving_graph(
            phase1_topology,
            phase1_model,
            placement_a,
            AnalyticalThroughputProvider(),
            allow_partial_inference=True,
        )

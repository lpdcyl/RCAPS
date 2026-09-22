from __future__ import annotations

from types import SimpleNamespace

import pytest

from simulator.event_simulator.base_node import NodeType
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
from src.graph.serving_graph import LayerInterval
from src.integration.helix_adapter import (
    layer_placement_from_helix,
    topology_from_helix,
    route_from_helix_pipeline,
)
from src.integration.helix_request_metrics import extract_query_metrics


def _history(phase: str, start: float, end: float, *, token_count: int = 1):
    return SimpleNamespace(
        request_phase=SimpleNamespace(name=phase),
        start_time=start,
        end_time=end,
        token_seq_length=token_count,
    )


def _query(*, output_tokens: int = 3, inferred: int | None = None):
    return SimpleNamespace(
        query_uid=7,
        creation_time=10.0,
        input_seq_length=4,
        output_seq_length=output_tokens,
        inferred_token_count=4 + output_tokens if inferred is None else inferred,
        inference_history=[
            _history("Initialization", 10.0, 11.5, token_count=4),
            _history("Increment", 11.5, 12.0),
            _history("Increment", 12.0, 12.7),
            _history("Increment", 12.7, 13.5),
        ][: 1 + output_tokens],
    )


def test_ttft_tbt_e2e_and_preserved_helix_metrics() -> None:
    metrics = extract_query_metrics(_query(), completion_time=13.5)
    assert metrics.complete
    assert metrics.ttft == pytest.approx(1.5)
    assert metrics.e2e == pytest.approx(3.5)
    assert metrics.tbt_mean == pytest.approx(0.75)
    assert metrics.tbt_p50 == pytest.approx(0.75)
    assert metrics.tbt_p95 == pytest.approx(0.795)
    assert metrics.tbt_p99 == pytest.approx(0.799)
    assert metrics.helix_prompt_latency == pytest.approx(1.5)
    assert metrics.helix_decode_iteration_latency_mean == pytest.approx(2 / 3)


def test_single_decode_token_has_unavailable_tbt() -> None:
    query = _query(output_tokens=1)
    metrics = extract_query_metrics(query, completion_time=12.0)
    assert metrics.complete
    assert metrics.tbt_mean is None
    assert metrics.tbt_p50 is None
    assert metrics.tbt_p95 is None
    assert metrics.tbt_p99 is None


def test_unfinished_query_does_not_receive_e2e() -> None:
    query = _query(output_tokens=3, inferred=5)
    metrics = extract_query_metrics(query)
    assert not metrics.complete
    assert metrics.ttft == pytest.approx(1.5)
    assert metrics.e2e is None


def test_non_monotonic_timestamps_are_rejected() -> None:
    query = _query()
    query.inference_history[2] = _history("Increment", 11.0, 11.9)
    with pytest.raises(ValueError, match="not monotonic"):
        extract_query_metrics(query, completion_time=13.5)


def test_helix_placement_node_and_route_mapping() -> None:
    nodes = [
        SimpleNamespace(node_uid=4, in_vram_model_layers={4: object(), 5: object()}),
        SimpleNamespace(node_uid=2, in_vram_model_layers={0: object(), 1: object(), 2: object(), 3: object()}),
    ]
    placement, node_to_gpu = layer_placement_from_helix(nodes)
    assert node_to_gpu == {2: "helix-node-2", 4: "helix-node-4"}
    assert placement.intervals["helix-node-2"] == LayerInterval(0, 4)
    assert placement.intervals["helix-node-4"] == LayerInterval(4, 6)

    route = route_from_helix_pipeline(
        [
            SimpleNamespace(link_uid=100, node_uid=2, layers_to_infer=[0, 1, 2, 3]),
            SimpleNamespace(link_uid=101, node_uid=4, layers_to_infer=[4, 5]),
            SimpleNamespace(link_uid=102, node_uid=1, layers_to_infer=None),
        ]
    )
    assert route.link_uids == (100, 101, 102)
    assert route.node_uids == (2, 4, 1)
    assert route.layer_intervals[-1] is None


def test_helix_topology_mapping_requires_explicit_carbon_metadata() -> None:
    source = SimpleNamespace(node_uid=0, node_type=NodeType.Source)
    compute = SimpleNamespace(
        node_uid=2,
        node_type=NodeType.Compute,
        machine_type="A100",
        vram_size=40_000_000_000,
    )
    sink = SimpleNamespace(node_uid=1, node_type=NodeType.Sink)
    links = [
        SimpleNamespace(node_in=source, node_out=compute, bandwidth=125_000_000),
        SimpleNamespace(node_in=compute, node_out=sink, bandwidth=125_000_000),
    ]
    topology, mapping = topology_from_helix(
        compute_nodes=[compute],
        links=links,
        region_by_node_uid={2: "region-a"},
        effective_compute_units_by_node_uid={2: 10.0},
    )
    assert mapping == {2: "helix-node-2"}
    assert topology.gpus["helix-node-2"].region == "region-a"
    assert topology.get_link("coordinator_source", "helix-node-2").bandwidth_mbps == pytest.approx(1000)


def test_online_feeder_trace_is_deterministic_for_fixed_seed() -> None:
    first = OnlineRequestFeeder(600.0, 16.0, 3, seed=0).trace
    second = OnlineRequestFeeder(600.0, 16.0, 3, seed=0).trace
    assert first == second

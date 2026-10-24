"""Focused KV admission invariants; no simulator or GPU run required."""

from types import SimpleNamespace

from experiments.v3_cluster42.kv_admission import KVAdmittedV3, SliceKVAdmittedV3
from simulator.event_simulator.kv_cache import KVCache


def test_full_lifetime_reservation_and_release():
    node = SimpleNamespace(in_vram_model_layers=list(range(10)),
                           kv_cache=SimpleNamespace(max_capacity=20_000))
    live = {1: SimpleNamespace(input_seq_length=500)}
    scheduler = object.__new__(KVAdmittedV3)
    scheduler.simulator = SimpleNamespace(compute_nodes={9: node},
                                          query_manager=SimpleNamespace(queries_on_the_fly=live))
    scheduler.session_paths = {}
    scheduler.execution_dag = SimpleNamespace(edge_set={("source", 9)})
    scheduler.simulator.source_node = SimpleNamespace(node_uid=0)
    scheduler.simulator.sink_node = SimpleNamespace(node_uid=10)
    scheduler._reserved = {}
    scheduler.peak_reserved = {}
    scheduler._session_reservations = {}
    scheduler._routing_request = SimpleNamespace(token_seq_length=500)
    scheduler._capacity_veto = False
    scheduler._reservation_version = 0
    scheduler._blocked_at = None
    assert scheduler._allow_placement_edge(0, 9)
    scheduler._reserved[9] = 15_000
    scheduler._session_reservations[1] = {9: 15_000}
    scheduler.session_paths[1] = [9]
    assert not scheduler._allow_placement_edge(0, 9)
    assert scheduler._capacity_veto
    live.clear()
    assert scheduler.reap_finished()
    assert scheduler._reserved[9] == 0
    assert scheduler._allow_placement_edge(0, 9)


def test_failed_route_cached_until_capacity_released():
    scheduler = object.__new__(KVAdmittedV3)
    live = {1: object()}
    scheduler.simulator = SimpleNamespace(
        query_manager=SimpleNamespace(queries_on_the_fly=live))
    scheduler._session_reservations = {1: {9: 100}}
    scheduler._reserved = {9: 100}
    scheduler.session_paths = {1: [9]}
    scheduler._reservation_version = 0
    scheduler._blocked_at = None
    scheduler.kv_admission = {"deferred_checks": 0, "cached_deferred_checks": 0}
    calls = []

    def no_route(request):
        calls.append(request.request_uid)
        scheduler._capacity_veto = True
        raise RuntimeError("Placement has no source-to-sink layer route")

    scheduler._route = no_route
    request = SimpleNamespace(request_uid=5)
    assert not scheduler._admit(request)
    assert not scheduler._admit(request)
    assert calls == [5]
    live.clear()
    assert not scheduler._admit(request)
    assert calls == [5, 5]


def test_executed_suffix_reservation_bounds_real_kv():
    """A partial route fits, its full decode lifetime fits, and release wakes it."""
    scheduler = object.__new__(SliceKVAdmittedV3)
    left = SimpleNamespace(in_vram_model_layers=list(range(8)))
    right = SimpleNamespace(in_vram_model_layers=list(range(5, 10)),
                            kv_cache=KVCache(list(range(5, 10)), 3000))
    live = {1: object()}
    scheduler.simulator = SimpleNamespace(
        compute_nodes={8: left, 9: right}, source_node=SimpleNamespace(node_uid=0),
        sink_node=SimpleNamespace(node_uid=10),
        query_manager=SimpleNamespace(queries_on_the_fly=live))
    scheduler.execution_dag = SimpleNamespace(edge_set={(8, 9)})
    scheduler.session_paths = {}
    scheduler._reserved = {}
    scheduler.peak_reserved = {}
    scheduler._session_reservations = {}
    scheduler._reservation_version = 0
    scheduler._blocked_at = None
    scheduler.kv_admission = {"admitted": 0, "deferred_checks": 0,
                              "cached_deferred_checks": 0, "minimum_headroom": None}
    # Enter node 9 after layer 7; only layers 8 and 9 allocate KV there.
    scheduler._routing_request = SimpleNamespace(token_seq_length=500)
    assert scheduler._allow_placement_edge(8, 9)
    assert (500 + 1000) * len(right.in_vram_model_layers) > right.kv_cache.max_capacity
    route = [SimpleNamespace(node_uid=8, layers_to_infer=list(range(8))),
             SimpleNamespace(node_uid=9, layers_to_infer=[8, 9]),
             SimpleNamespace(node_uid=10, layers_to_infer=None)]
    left.kv_cache = KVCache(list(range(8)), 12000)
    scheduler._route = lambda request: route
    request = SimpleNamespace(request_uid=1, base_query_uid=1, token_seq_length=500,
                              set_pipeline=lambda stages: None)
    assert scheduler._admit(request)
    assert scheduler._session_reservations[1] == {8: 12000, 9: 3000}
    # Exercise the actual simulator cache up to the public output upper bound.
    for node, layers in ((left, list(range(8))), (right, [8, 9])):
        node.kv_cache.initialize_query_kv_cache(layers, 1, 500)
        for _ in range(1000):
            node.kv_cache.grow_query_kv_cache(layers, 1)
        assert node.kv_cache.available_capacity == 0
    scheduler._routing_request = request
    assert not scheduler._allow_placement_edge(8, 9)
    for node, layers in ((left, list(range(8))), (right, [8, 9])):
        node.kv_cache.remove_query_kv_cache(layers, 1)
    live.clear()
    assert scheduler.reap_finished()
    assert scheduler._reserved == {8: 0, 9: 0}
    assert scheduler._allow_placement_edge(8, 9)
    assert right.kv_cache.kv_cache[5] == {}


if __name__ == "__main__":
    test_full_lifetime_reservation_and_release()
    test_failed_route_cached_until_capacity_released()
    test_executed_suffix_reservation_bounds_real_kv()

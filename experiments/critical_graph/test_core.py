"""Checks for event causality and legal graph-to-topology mappings."""

from __future__ import annotations

import unittest

from .event_graph import EventGraph, interleaved_workload_graph
from .partition import initial_partition, refine, scenario
from .path_ensemble import measure as path_ensemble_measure
from .topology import TopologyModel


class CriticalGraphTests(unittest.TestCase):
    def test_longest_path_uses_dependencies_and_resource_order(self):
        graph = EventGraph()
        graph.add("first", 2, kind="compute", resource="gpu:0",
                  serialize_resource=True)
        graph.add("independent", 5, kind="compute")
        graph.add("second", 3, ("independent",), kind="compute",
                  resource="gpu:0", serialize_resource=True)
        path = graph.critical_path("second")
        self.assertEqual(path.completion_s, 8)
        self.assertEqual(path.events, ("independent", "second"))

    def test_concurrent_requests_share_gpu(self):
        stage = {"device": "0", "prefill_s": 1.0, "decode_s": 1.0,
                 "incoming_link": "source->0", "incoming_latency_s": 0,
                 "incoming_bytes_per_s": 1e12, "payload_bytes": 0}
        graph, first, last = interleaved_workload_graph(
            [[stage], [stage]], prompt_tokens=1, generated_tokens=1,
            arrivals_s=[0, 0])
        self.assertEqual([graph.critical_path(event).completion_s for event in first],
                         [1, 2])
        self.assertEqual(first, last)

    def test_link_occupancy_and_propagation_match_simulator(self):
        stage = {"device": "0", "prefill_s": 0.0, "decode_s": 0.0,
                 "incoming_link": "source->0", "incoming_latency_s": 0.2,
                 "incoming_bytes_per_s": 100.0, "payload_bytes": 100.0}
        graph, first, _ = interleaved_workload_graph(
            [[stage]], prompt_tokens=1, generated_tokens=1, arrivals_s=[0])
        self.assertAlmostEqual(graph.critical_path(first[0]).completion_s, 1.2)

    def test_partition_covers_layers_and_improves_surrogate(self):
        for name in ("single", "multi"):
            with self.subTest(name=name):
                cluster, _ = scenario(name)
                model = TopologyModel(cluster)
                initial = initial_partition(model)
                spans = model.intervals(initial)
                self.assertTrue(all(end - start <= model.capacity[node]
                                    for node, (start, end) in spans.items()))
                refined, trace = refine(model, initial, max_steps=4)
                model.intervals(refined)
                self.assertTrue(all(a["score"] > b["score"]
                                    for a, b in zip(trace, trace[1:])))

    def test_physical_link_latency_changes_critical_path(self):
        cluster, _ = scenario("multi")
        model = TopologyModel(cluster)
        state = initial_partition(model)
        before = model.measure(state)
        section = f"Link-source-{state['shared']}"
        old = model.config[section]["latency"]
        model.config[section]["latency"] = "1 * Sec"
        model._links.clear()
        after = model.measure(state)
        model.config[section]["latency"] = old
        self.assertGreater(after.ttft_s, before.ttft_s)

    def test_path_ensemble_conserves_complete_route_flow(self):
        cluster, _ = scenario("multi")
        model = TopologyModel(cluster)
        state = initial_partition(model)
        ensemble = path_ensemble_measure(model, state)
        self.assertAlmostEqual(ensemble.edge_probability[
            f"source->{state['shared']}"], 1.0)
        self.assertAlmostEqual(sum(value for edge, value in
                                   ensemble.edge_probability.items()
                                   if edge.endswith("->sink")), 1.0)
        self.assertTrue(all(0 <= value <= 1 + 1e-9 for value in
                            ensemble.gpu_visit_probability.values()))
        for node, visit in ensemble.gpu_visit_probability.items():
            incoming = sum(value for edge, value in
                           ensemble.edge_probability.items()
                           if edge.endswith(f"->{node}"))
            outgoing = sum(value for edge, value in
                           ensemble.edge_probability.items()
                           if edge.startswith(f"{node}->"))
            self.assertAlmostEqual(incoming, outgoing)
            self.assertAlmostEqual(visit, incoming)


if __name__ == "__main__":
    unittest.main()

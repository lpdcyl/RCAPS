"""Invariants needed before using a route mask in a formal window."""

from __future__ import annotations

import unittest

from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from .joint import (ROOT, arrival_trace, canonical_edges, case_inputs,
                    observed_edge_counts, read, runtime_edges, selective_edges,
                    verify_edges)
from rcaps.v3.placement import validate


class JointCandidateInvariants(unittest.TestCase):
    def test_subgraphs_preserve_complete_paths_and_device_reachability(self):
        for case, topology in (("C1_single", "single"), ("C1_multi", "multi")):
            with self.subTest(case=case):
                model, _, _ = case_inputs(case)
                state = read(ROOT / "rcaps/v3_layouts" / topology / "placement.json")["state"]
                dag = validate(model, state)["dag"]
                backbone = canonical_edges(state, dag)
                full_row = read(ROOT / "benchmarks/runs" / topology /
                                "seed0/rcaps_v3.json")
                selected = selective_edges(state, dag, full_row["route_counts"])
                self.assertLessEqual(backbone, selected)
                self.assertLessEqual(selected, dag.edge_set)
                verify_edges(dag, selected)
                self.assertEqual(len(runtime_edges(selected)), len(selected))
                self.assertGreater(sum(observed_edge_counts(
                    full_row["route_counts"], dag).values()), 0)

    def test_burst_keeps_requests_and_is_temporally_nonuniform(self):
        duration = 300
        ordinary = OnlineRequestFeeder(cluster_token_throughput=700,
                                       start_time=0, duration=duration, seed=100).trace
        burst = arrival_trace(700, duration, 100, "burst")
        self.assertEqual([(i, o) for _, i, o in ordinary],
                         [(i, o) for _, i, o in burst])
        self.assertEqual(len(ordinary), len(burst))
        self.assertTrue(all(0 <= t < duration for t, _, _ in burst))
        original_middle = sum(duration / 3 <= t < duration / 2
                              for t, _, _ in ordinary)
        burst_middle = sum(duration / 3 <= t < duration / 2
                           for t, _, _ in burst)
        self.assertGreater(burst_middle, original_middle)

    def test_illegal_or_stranded_edges_are_rejected(self):
        model, _, _ = case_inputs("C1_single")
        state = read(ROOT / "rcaps/v3_layouts/single/placement.json")["state"]
        dag = validate(model, state)["dag"]
        with self.assertRaises(ValueError):
            verify_edges(dag, {("source", "nonexistent"), *dag.edges})
        with self.assertRaises(ValueError):
            verify_edges(dag, {(a, b) for a, b in dag.edges if a != "source"})


if __name__ == "__main__":
    unittest.main()

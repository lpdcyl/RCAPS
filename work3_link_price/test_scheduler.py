"""Small checks for sparse-edge admission and the inherited price."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from experiments.v3_gated_pathspace.scheduler import admitted_edges
from work3_link_price.scheduler import PricedGatedScheduler


class TestPrice(unittest.TestCase):
    def test_sparse_edges_keep_canonical_and_only_fast_detour(self):
        canonical = frozenset({("source", 1), (1, 2), (2, "sink")})
        full = canonical | {(1, 3), (3, 2)}
        bandwidth = {(1, 2): 13_000_000, (1, 3): 100_000_000,
                     (3, 2): 10_000_000}
        allowed = admitted_edges(canonical, full, bandwidth)
        self.assertEqual(allowed, canonical | {(1, 3)})

    def test_price_zero_when_disabled(self):
        scheduler = PricedGatedScheduler(SimpleNamespace(compute_nodes={}),
                                         canonical_edges=frozenset(),
                                         externality=False)
        self.assertEqual(scheduler._externality(object(), object(), {}), 0.0)

    def test_price_is_inherited_causal_formula(self):
        first = SimpleNamespace(node_uid=1, outbound_nic_speed=100.0)
        second = SimpleNamespace(node_uid=2, inbound_nic_speed=100.0,
                                 node_type=SimpleNamespace(name="Compute"))
        link = SimpleNamespace(link_uid=7, node_in=first, node_out=second,
                               bandwidth=10.0, latency=0.2)
        scheduler = PricedGatedScheduler(SimpleNamespace(compute_nodes={1: first, 2: second}),
                                         canonical_edges=frozenset())
        request = SimpleNamespace(token_size=10.0, activation_size=30.0,
                                  token_seq_length=1)
        self.assertAlmostEqual(scheduler._externality(link, request, {7: 0.5}), 4.0)
        self.assertEqual(scheduler.route_prices, [4.0])


if __name__ == "__main__":
    unittest.main()

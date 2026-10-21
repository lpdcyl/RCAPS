"""Slow-link-gated path admission for V3 M3 (candidate, not the frozen method).

Diagnosis (experiments/v3_cycle_pricing, experiments/v3_cohort_routing):
switching between replicas of the same segment fragments decode batches
(seed 100: mean decode batch 2.91 on the full DAG vs 5.58 on canonical routes
in C1 single). On C1 three-cluster it nevertheless pays off, because the
switches bypass slow inter-cluster links inside canonical replicas.

The candidate keeps canonical routes and admits a cross-replica edge only
when it is a fast link that bypasses a slow canonical edge leaving its tail
GPU or entering its head GPU. A link is slow when its bandwidth is at most
50 MB/s, the threshold already used by experiments/v3_phase_link_diagnosis.
Route price, tie order and decode path are the frozen V3 ones. Canonical
routes are always admitted, so a complete execution path always exists.
"""

from __future__ import annotations

from experiments.v3_cycle_pricing.scheduler import RouteRecorder
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler
from rcaps.v3.resource_graph import from_simulator

SLOW_LINK_BPS = 50_000_000


def admitted_edges(canonical: frozenset, full_edges, bandwidth: dict) -> frozenset:
    """Canonical edges plus fast cross-replica edges that bypass a slow one."""
    def compute(node) -> bool:
        return not isinstance(node, str)

    def slow(edge) -> bool:
        return bandwidth[edge] <= SLOW_LINK_BPS

    slow_tails = {a for a, b in canonical if compute(a) and compute(b) and slow((a, b))}
    slow_heads = {b for a, b in canonical if compute(a) and compute(b) and slow((a, b))}
    detours = {(a, b) for a, b in full_edges
               if (a, b) not in canonical and compute(a) and compute(b)
               and not slow((a, b)) and (a in slow_tails or b in slow_heads)}
    return frozenset(canonical | detours)


class SlowLinkGatedScheduler(RouteRecorder, CanonicalGraphDagScheduler):
    def __init__(self, simulator, *, allowed_edges: frozenset):
        super().__init__(simulator, allowed_edges=allowed_edges)
        self.canonical_edges = allowed_edges
        self.detour_edges = None

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        if self.detour_edges is None:
            dag = from_simulator(self.simulator)
            sim = self.simulator

            def name(uid):
                if uid == sim.source_node.node_uid:
                    return "source"
                if uid == sim.sink_node.node_uid:
                    return "sink"
                return uid

            bandwidth = {(name(l.node_in.node_uid), name(l.node_out.node_uid)): l.bandwidth
                         for l in sim.links.values()}
            self.allowed_edges = admitted_edges(self.canonical_edges, dag.edge_set, bandwidth)
            self.detour_edges = self.allowed_edges - self.canonical_edges
        return super()._allow_placement_edge(left_uid, right_uid)

"""Canonical routes plus a chosen subset of four physical slow-link bypasses."""

from __future__ import annotations

from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler, admitted_edges
from rcaps.v3.resource_graph import from_simulator

EDGE_ORDER = ((6, 13), (11, 8), (20, 22), (23, 18))


class FixedDetourSubsetScheduler(SlowLinkGatedScheduler):
    def __init__(self, simulator, *, allowed_edges: frozenset, mask: int):
        if not 0 <= mask < (1 << len(EDGE_ORDER)):
            raise ValueError("Invalid admission mask")
        super().__init__(simulator, allowed_edges=allowed_edges)
        self.mask = mask
        self.available_detours = None

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

            bandwidth = {(name(link.node_in.node_uid), name(link.node_out.node_uid)):
                         link.bandwidth for link in sim.links.values()}
            expected = admitted_edges(self.canonical_edges, dag.edge_set, bandwidth) - self.canonical_edges
            if expected != frozenset(EDGE_ORDER):
                raise AssertionError(f"Frozen bypass set changed: {sorted(expected)}")
            chosen = frozenset(edge for i, edge in enumerate(EDGE_ORDER) if self.mask & (1 << i))
            self.allowed_edges = self.canonical_edges | chosen
            self.detour_edges = chosen
            self.available_detours = expected
        return super()._allow_placement_edge(left_uid, right_uid)

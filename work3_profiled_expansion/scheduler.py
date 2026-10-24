"""Static sparse gate plus specified, legal and fast V3 profile edges."""

from __future__ import annotations

from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler, admitted_edges, SLOW_LINK_BPS
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler
from rcaps.v3.resource_graph import from_simulator


class ProfileExpandedScheduler(SlowLinkGatedScheduler):
    def __init__(self, simulator, *, allowed_edges: frozenset,
                 additional_edges: frozenset[tuple[int, int]]):
        super().__init__(simulator, allowed_edges=allowed_edges)
        self.additional_edges = additional_edges

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
            gated = admitted_edges(self.canonical_edges, dag.edge_set, bandwidth)
            if not self.additional_edges <= dag.edge_set - gated:
                raise ValueError("Additional edge is already admitted or not legal")
            if any(bandwidth[edge] <= SLOW_LINK_BPS for edge in self.additional_edges):
                raise ValueError("Additional edge is not fast")
            self.allowed_edges = frozenset(gated | self.additional_edges)
            self.detour_edges = self.allowed_edges - self.canonical_edges
        return CanonicalGraphDagScheduler._allow_placement_edge(self, left_uid, right_uid)

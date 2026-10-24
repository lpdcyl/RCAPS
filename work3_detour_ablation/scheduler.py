"""Use the old sparse gate while excluding exactly one audited fast detour."""

from __future__ import annotations

from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler, admitted_edges
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler
from rcaps.v3.resource_graph import from_simulator


class LeaveOneOutScheduler(SlowLinkGatedScheduler):
    def __init__(self, simulator, *, allowed_edges: frozenset,
                 excluded_edge: tuple[int, int] | None):
        super().__init__(simulator, allowed_edges=allowed_edges)
        self.excluded_edge = excluded_edge

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
            admitted = admitted_edges(self.canonical_edges, dag.edge_set, bandwidth)
            detours = admitted - self.canonical_edges
            if self.excluded_edge is not None and self.excluded_edge not in detours:
                raise ValueError(f"Excluded edge is not an admitted detour: {self.excluded_edge}")
            self.allowed_edges = frozenset(admitted - {self.excluded_edge})
            self.detour_edges = self.allowed_edges - self.canonical_edges
        return CanonicalGraphDagScheduler._allow_placement_edge(self, left_uid, right_uid)

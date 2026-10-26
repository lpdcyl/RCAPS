"""Static admission; route prices and tie order are inherited from frozen V3."""

from __future__ import annotations

from collections import Counter

from rcaps.v3.resource_graph import LayerCompatibilityDag, from_simulator
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler

SLOW_LINK_BPS = 50_000_000


def canonical_edges(state, full, uid_offset=2):
    segments = state["segments"]
    edges = set()
    for segment in segments:
        for replica in segment["replicas"]:
            edges.update((a + uid_offset, b + uid_offset)
                         for a, b in zip(replica, replica[1:]))
    edges.update(("source", r[0] + uid_offset) for r in segments[0]["replicas"])
    edges.update((r[-1] + uid_offset, "sink") for r in segments[-1]["replicas"])
    for left, right in zip(segments, segments[1:]):
        for a in left["replicas"]:
            for b in right["replicas"]:
                edge = (a[-1] + uid_offset, b[0] + uid_offset)
                if edge in full.edge_set:
                    edges.add(edge)
    if not edges <= full.edge_set:
        raise ValueError("Canonical edge is absent from deployed layer DAG")
    if not LayerCompatibilityDag(full.spans, tuple(edges), full.layers).path_count():
        raise ValueError("Canonical graph has no complete path")
    return frozenset(edges)


def admitted_edges(canonical, full_edges, bandwidth, threshold=SLOW_LINK_BPS):
    slow = {(a, b) for a, b in canonical
            if not isinstance(a, str) and not isinstance(b, str)
            and bandwidth[a, b] <= threshold}
    tails, heads = {a for a, _ in slow}, {b for _, b in slow}
    detours = {(a, b) for a, b in full_edges
               if (a, b) not in canonical and not isinstance(a, str)
               and not isinstance(b, str) and bandwidth[a, b] > threshold
               and (a in tails or b in heads)}
    return frozenset(canonical | detours)


class AdmissionScheduler(GraphModeledQueueAwareDagScheduler):
    def __init__(self, simulator, *, state, admission="sparse",
                 threshold=SLOW_LINK_BPS, routing_state="live"):
        super().__init__(simulator)
        if admission not in {"full", "canonical", "sparse"}:
            raise ValueError(admission)
        if routing_state not in {"live", "static", "no_session"}:
            raise ValueError(routing_state)
        self.placement_state = state
        self.admission_mode = admission
        self.threshold = threshold
        self.routing_state = routing_state
        self.allowed_edges = None
        self.canonical_edges = None

    def _initialize_graph(self):
        self.execution_dag = from_simulator(self.simulator)
        self.canonical_edges = canonical_edges(self.placement_state, self.execution_dag)
        def name(uid):
            if uid == self.simulator.source_node.node_uid:
                return "source"
            if uid == self.simulator.sink_node.node_uid:
                return "sink"
            return uid
        bandwidth = {(name(l.node_in.node_uid), name(l.node_out.node_uid)): l.bandwidth
                     for l in self.simulator.links.values()}
        self.allowed_edges = (self.execution_dag.edge_set if self.admission_mode == "full"
                              else self.canonical_edges if self.admission_mode == "canonical"
                              else admitted_edges(self.canonical_edges,
                                                  self.execution_dag.edge_set,
                                                  bandwidth, self.threshold))

    def _allow_placement_edge(self, left_uid, right_uid):
        if self.allowed_edges is None:
            self._initialize_graph()
        left = "source" if left_uid == self.simulator.source_node.node_uid else left_uid
        right = "sink" if right_uid == self.simulator.sink_node.node_uid else right_uid
        return (left, right) in self.allowed_edges

    def _active_session_counts(self):
        if self.routing_state in {"static", "no_session"}:
            return Counter()
        return super()._active_session_counts()

    def _release_snapshot(self):
        if self.routing_state == "static":
            now = self.simulator.current_time
            return ({uid: now for uid in self.simulator.compute_nodes},
                    {uid: now for uid in self.simulator.links})
        return super()._release_snapshot()

    def summary(self):
        if self.allowed_edges is None:
            self._initialize_graph()
        return {"mode": self.admission_mode, "routing_state": self.routing_state,
                "threshold_Bps": self.threshold,
                "full_edge_count": len(self.execution_dag.edges),
                "canonical_edge_count": len(self.canonical_edges),
                "allowed_edge_count": len(self.allowed_edges),
                "allowed_edges": sorted([list(e) for e in self.allowed_edges], key=str)}

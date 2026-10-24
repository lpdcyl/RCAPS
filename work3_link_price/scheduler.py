"""Admission-time Prompt/Decode link externality on the validated sparse DAG."""

from __future__ import annotations

from experiments.v3_cycle_pricing.scheduler import RouteRecorder
from experiments.v3_gated_pathspace.scheduler import admitted_edges
from experiments.v3_m3_interference.scheduler import InterferenceAwareDagScheduler
from rcaps.v3.resource_graph import from_simulator


class PricedGatedScheduler(RouteRecorder, InterferenceAwareDagScheduler):
    """Keep gated edges and V3 costs; add the no-fit T12 link externality."""

    def __init__(self, simulator, *, canonical_edges: frozenset,
                 externality: bool = True):
        super().__init__(simulator, externality=externality, switch_cost=False)
        self.canonical_edges = canonical_edges
        self.allowed_edges = None
        self.route_prices = []

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        if self.allowed_edges is None:
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
            self.allowed_edges = admitted_edges(self.canonical_edges, dag.edge_set, bandwidth)
            if not self.canonical_edges <= self.allowed_edges:
                raise AssertionError("The sparse graph lost a canonical edge")
        if self.execution_dag is None:
            self.execution_dag = from_simulator(self.simulator)
        left = ("source" if left_uid == self.simulator.source_node.node_uid else left_uid)
        right = ("sink" if right_uid == self.simulator.sink_node.node_uid else right_uid)
        return ((left, right) in self.execution_dag.edge_set and
                (left, right) in self.allowed_edges)

    def _externality(self, link, request, decode_rate):
        price = super()._externality(link, request, decode_rate)
        if price:
            self.route_prices.append(price)
        return price

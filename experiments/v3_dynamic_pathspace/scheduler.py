"""Request-level path admission before the unchanged V3 M3 route ranking.

Canonical edges and the old slow-link bypass are always present. Other legal
compute edges are admitted only when observed queue/link relief exceeds the
positive difference between the candidate and canonical successor's marginal
decode-round work for the public-trace median of 154 output tokens. This is
a batch-fragmentation proxy, not a prediction of actual output length.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from experiments.v3_cluster42.kv_admission import _KVAdmission, SliceKVAdmittedV3
from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler, RouteRecorder
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler, admitted_edges
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler
from rcaps.v3.resource_graph import from_simulator
from simulator.event_simulator.request import RequestPhase

MEDIAN_OUTPUT_TOKENS = 154


class DynamicPathScheduler(RouteRecorder, CanonicalGraphDagScheduler):
    """Choose an allowed-edge set per prompt; leave M3's ranking intact."""

    def __init__(self, simulator, *, allowed_edges: frozenset, protect_batches=True):
        super().__init__(simulator, allowed_edges=allowed_edges)
        self.canonical_edges = allowed_edges
        self.protect_batches = protect_batches
        self.static_edges = None
        self._candidate_edges = None
        self._canonical_successors = None
        self._links = None
        self.gate_counts = Counter()
        self.gate_by_edge = defaultdict(Counter)

    def _name(self, uid):
        sim = self.simulator
        if uid == sim.source_node.node_uid:
            return "source"
        if uid == sim.sink_node.node_uid:
            return "sink"
        return uid

    def _prepare_edges(self):
        if self.static_edges is not None:
            return
        dag = from_simulator(self.simulator)
        links = defaultdict(list)
        bandwidth = {}
        for link in self.simulator.links.values():
            edge = (self._name(link.node_in.node_uid),
                    self._name(link.node_out.node_uid))
            links[edge].append(link)
            bandwidth[edge] = max(bandwidth.get(edge, 0), link.bandwidth)
        self._links = links
        self.static_edges = admitted_edges(self.canonical_edges, dag.edge_set, bandwidth)
        successors = defaultdict(list)
        for left, right in self.canonical_edges:
            if isinstance(left, int) and isinstance(right, int):
                successors[left].append(right)
        self._canonical_successors = successors
        self._candidate_edges = tuple(sorted(
            ((left, right) for left, right in dag.edge_set - self.static_edges
             if isinstance(left, int) and isinstance(right, int)
             and left in successors), key=str))

    def _pressure(self, left, right, request, gpu_release, link_release):
        now = self.simulator.current_time
        gpu_wait = max(0.0, gpu_release.get(right, now) - now)
        return min(
            gpu_wait + max(0.0, link_release[link.link_uid] - now) +
            self._transfer_time(link, request)
            for link in self._links[(left, right)])

    def _marginal_batch_work(self, left, right, sessions):
        sim = self.simulator
        boundary = max(sim.compute_nodes[left].in_vram_model_layers) + 1
        node = sim.compute_nodes[right]
        end = max(node.in_vram_model_layers) + 1
        limit = max(1, min(node.inference_settings.decode_typical_tokens,
                           node.inference_settings.decode_max_tokens))

        def round_work(count):
            work = 0.0
            while count:
                batch = min(count, limit)
                work += (2 if batch == 1 else 1) * sum(
                    self._layer_service(node, layer, RequestPhase.Increment, batch)
                    for layer in range(boundary, end))
                count -= batch
            return work

        return max(0.0, round_work(sessions + 1) - round_work(sessions))

    def _batch_penalty(self, left, right, reference, sessions):
        if not self.protect_batches:
            return 0.0
        candidate = self._marginal_batch_work(left, right, sessions[right])
        baseline = self._marginal_batch_work(left, reference, sessions[reference])
        return MEDIAN_OUTPUT_TOKENS * max(0.0, candidate - baseline)

    def _route(self, request):
        self._prepare_edges()
        gpu_release, link_release = self._release_snapshot()
        sessions = self._active_session_counts()
        admitted = set()
        self.gate_counts["route_checks"] += 1
        for left, right in self._candidate_edges:
            candidate = self._pressure(left, right, request, gpu_release, link_release)
            reference, reference_uid = min(
                (self._pressure(left, successor, request, gpu_release, link_release),
                 successor) for successor in self._canonical_successors[left])
            relief = reference - candidate
            penalty = self._batch_penalty(left, right, reference_uid, sessions)
            self.gate_counts["candidate_checks"] += 1
            edge = f"{left}->{right}"
            if relief > 0:
                self.gate_counts["positive_relief_sum_s"] += relief
                self.gate_counts["positive_relief_count"] += 1
                self.gate_counts["positive_penalty_sum_s"] += penalty
            if relief > penalty:
                admitted.add((left, right))
                self.gate_counts["dynamic_admitted"] += 1
                self.gate_by_edge[edge]["admitted"] += 1
            elif relief > 0:
                self.gate_counts["batch_vetoed"] += 1
                self.gate_by_edge[edge]["batch_vetoed"] += 1
            else:
                self.gate_counts["no_relief"] += 1
        self.allowed_edges = self.static_edges | admitted
        try:
            route = super()._route(request)
            previous = "source"
            for stage in route[:-1]:
                edge = (previous, stage.node_uid)
                if edge in admitted:
                    self.gate_counts["dynamic_selected"] += 1
                    self.gate_by_edge[f"{previous}->{stage.node_uid}"]["selected"] += 1
                elif edge in self.static_edges - self.canonical_edges:
                    self.gate_counts["static_selected"] += 1
                previous = stage.node_uid
            return route
        finally:
            self.allowed_edges = self.static_edges


class ExecutedLayerKVAdmission(_KVAdmission):
    """Use the same full-lifetime executed-layer guard in every cell."""

    _edge_layer_count = SliceKVAdmittedV3._edge_layer_count
    _route_layer_counts = SliceKVAdmittedV3._route_layer_counts


class KVFull(ExecutedLayerKVAdmission, RecordedV3Scheduler):
    pass


class KVCanonical(ExecutedLayerKVAdmission, RouteRecorder, CanonicalGraphDagScheduler):
    pass


class KVStatic(ExecutedLayerKVAdmission, SlowLinkGatedScheduler):
    pass


class KVDynamic(ExecutedLayerKVAdmission, DynamicPathScheduler):
    pass


class LinkPressureDynamicPathScheduler(DynamicPathScheduler):
    """Open new detours for link relief only; M3 still ranks by GPU and link."""

    def _pressure(self, left, right, request, gpu_release, link_release):
        now = self.simulator.current_time
        return min(
            max(0.0, link_release[link.link_uid] - now) +
            self._transfer_time(link, request)
            for link in self._links[(left, right)])


class KVLinkDynamic(ExecutedLayerKVAdmission, LinkPressureDynamicPathScheduler):
    pass

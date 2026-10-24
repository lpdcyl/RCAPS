"""Whole-route admission above the unchanged M3 route optimizer.

Only online queue state, public hardware profiles and active session counts
are read. Batch work is a one-round proxy, not a TPOT or lifetime prediction.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import exp, isfinite

from experiments.v3_cycle_pricing.scheduler import RouteRecorder
from experiments.v3_dynamic_pathspace.scheduler import ExecutedLayerKVAdmission
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler
from simulator.event_simulator.request import RequestPhase


@dataclass
class StableGate:
    tau_s: float = 1.0
    open_s: float = 0.01
    close_s: float = 0.0
    dwell_s: float = 1.0
    opened: bool = False
    filtered_s: float = 0.0
    last_time: float | None = None
    last_switch: float | None = None
    switches: int = 0

    def update(self, now: float, value: float) -> bool:
        if not isfinite(now) or not isfinite(value):
            raise ValueError("Nonfinite control observation")
        if self.last_time is None:
            self.last_time = self.last_switch = now
        if now < self.last_time:
            raise ValueError("Control time moved backwards")
        elapsed = now - self.last_time
        self.filtered_s += (1.0 - exp(-elapsed / self.tau_s)) * (value - self.filtered_s)
        self.last_time = now
        target = self.opened
        if not self.opened and self.filtered_s > self.open_s:
            target = True
        elif self.opened and self.filtered_s <= self.close_s:
            target = False
        if target != self.opened and now - self.last_switch >= self.dwell_s:
            self.opened = target
            self.last_switch = now
            self.switches += 1
        return self.opened


def signature(route):
    return tuple((s.link_uid, s.node_uid, tuple(s.layers_to_infer or ())) for s in route)


class RouteController(CanonicalGraphDagScheduler):
    def __init__(self, simulator, *, baseline_edges, full_edges,
                 use_batch_cost=True, use_stability=True):
        super().__init__(simulator, allowed_edges=baseline_edges)
        if not baseline_edges <= full_edges:
            raise ValueError("Baseline must be a subset of the legal full DAG")
        self.baseline_edges = baseline_edges
        self.full_edges = full_edges
        self.use_batch_cost = use_batch_cost
        self.use_stability = use_stability
        self.control = StableGate()
        self.control_events = []
        self.control_counts = Counter()
        self._pinned_snapshot = None
        self._pinned_sessions = None

    def _release_snapshot(self):
        if self._pinned_snapshot is not None:
            return self._pinned_snapshot
        return super()._release_snapshot()

    def _active_session_counts(self):
        if self._pinned_sessions is not None:
            return self._pinned_sessions
        return super()._active_session_counts()

    def _probe(self, request, edges):
        assigned = self.routes_assigned
        self.allowed_edges = edges
        try:
            # Bypass RouteRecorder and this controller; no reservations or
            # session paths are committed by the frozen M3 routing routine.
            return CanonicalGraphDagScheduler._route(self, request)
        except RuntimeError as error:
            if "source-to-sink layer route" in str(error) and self._capacity_veto:
                return None
            raise
        finally:
            self.routes_assigned = assigned

    def _score(self, route, request, snapshot, sessions):
        gpu_release, link_release = snapshot
        now = self.simulator.current_time
        terms = Counter()
        for stage in route:
            link = self.simulator.links[stage.link_uid]
            terms["link_wait_s"] += max(0.0, link_release[stage.link_uid] - now)
            terms["transfer_s"] += self._transfer_time(link, request)
            if stage.layers_to_infer is None:
                continue
            node = self.simulator.compute_nodes[stage.node_uid]
            first, end = stage.layers_to_infer[0], stage.layers_to_infer[-1] + 1
            terms["prompt_s"] += sum(self._layer_service(
                node, layer, RequestPhase.Initialization, request.token_seq_length)
                for layer in range(first, end))
            terms["gpu_wait_s"] += max(0.0, gpu_release.get(node.node_uid, now) - now)
            terms["session_s"] += sessions[node.node_uid] * self._decode_token_service(
                node, first, end, sessions[node.node_uid])
        return sum(terms.values()), dict(terms)

    def _round_work(self, node, count):
        limit = max(1, min(node.inference_settings.decode_typical_tokens,
                           node.inference_settings.decode_max_tokens))
        result = 0.0
        while count:
            batch = min(count, limit)
            # Match ComputeNode.get_inference_statistics' singleton scaling.
            result += (2 if batch == 1 else 1) * sum(self._layer_service(
                node, layer, RequestPhase.Increment, batch)
                for layer in node.in_vram_model_layers)
            count -= batch
        return result

    def _batch_work(self, route, sessions):
        # Full resident-cycle proxy; live requests need not synchronize and
        # may execute only a suffix. This assumption is explicitly audited.
        return sum(self._round_work(self.simulator.compute_nodes[s.node_uid],
                                    sessions[s.node_uid] + 1) -
                   self._round_work(self.simulator.compute_nodes[s.node_uid],
                                    sessions[s.node_uid]) for s in route[:-1])

    def _route(self, request):
        snapshot = super()._release_snapshot()
        sessions = super()._active_session_counts()
        self._pinned_snapshot, self._pinned_sessions = snapshot, sessions
        assigned = self.routes_assigned
        before_reserved = dict(self._reserved)
        before_sessions = dict(self.session_paths)
        try:
            baseline = self._probe(request, self.baseline_edges)
            expanded = self._probe(request, self.full_edges)
            if self._reserved != before_reserved or self.session_paths != before_sessions:
                raise AssertionError("Candidate probes changed committed state")
            if expanded is None:
                if baseline is not None:
                    raise AssertionError("Full superset lost a feasible baseline path")
                raise RuntimeError("Placement has no source-to-sink layer route")
            event = {"query_uid": request.base_query_uid,
                     "time_s": self.simulator.current_time,
                     "baseline": signature(baseline) if baseline is not None else None,
                     "expanded": signature(expanded), "capacity_fallback": baseline is None}
            if baseline is None:
                chosen = expanded
                self.control_counts["capacity_fallback"] += 1
                event.update(selected_expanded=True, net_proxy_s=None,
                             filtered_s=self.control.filtered_s,
                             gate_open=self.control.opened)
            else:
                c0, terms0 = self._score(baseline, request, snapshot, sessions)
                c1, terms1 = self._score(expanded, request, snapshot, sessions)
                if c1 > c0 + 1e-8:
                    raise AssertionError("Superset M3 minimum exceeds baseline minimum")
                b0, b1 = self._batch_work(baseline, sessions), self._batch_work(expanded, sessions)
                penalty = max(0.0, b1 - b0) if self.use_batch_cost else 0.0
                net = c0 - c1 - penalty
                opened = (self.control.update(self.simulator.current_time, net)
                          if self.use_stability else net > self.control.open_s)
                different = signature(baseline) != signature(expanded)
                selected = different and opened and net > 0
                chosen = expanded if selected else baseline
                event.update(cost_baseline_s=c0, cost_expanded_s=c1,
                             terms_baseline=terms0, terms_expanded=terms1,
                             batch_baseline_s=b0, batch_expanded_s=b1,
                             batch_penalty_s=penalty, net_proxy_s=net,
                             filtered_s=self.control.filtered_s,
                             gate_open=opened, candidates_differ=different,
                             selected_expanded=selected)
                self.control_counts["different_candidates"] += different
                self.control_counts["positive_net"] += different and net > 0
                self.control_counts["expanded_selected"] += selected
                self.control_counts["batch_veto"] += different and c0 > c1 and net <= 0
            self.control_counts["decisions"] += 1
            self.control_events.append(event)
            self.routes_assigned = assigned + 1
            return chosen
        finally:
            self.allowed_edges = self.baseline_edges
            self._pinned_snapshot = self._pinned_sessions = None


class KVRouteController(ExecutedLayerKVAdmission, RouteRecorder, RouteController):
    pass

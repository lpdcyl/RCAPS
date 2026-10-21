"""Decode-cohort pricing for V3 M3 (candidate, not the frozen method).

A GPU runs one batch per resident layer and cycles through its layers. Decode
tokens that reach it through the same upstream edge tend to arrive in the same
wave and share a batch. A prompt route whose edge (u -> v) carries no live
session opens a new wave at v: on every decode step v runs an extra batch,
and the simulator charges a one-request decode batch twice its profile
(``simulator/event_simulator/model.py:131-134``). Frozen V3 prices every
session as a one-request batch, so it cannot tell joining a live cohort from
opening a new one; path diversity then fragments decode batches.

The candidate adds, for an edge with no live session, the one-request decode
round of the layers the request runs on v, scaled by ``cohort_tokens``:
1 prices one decode step, the reference output length prices the decode
lifetime the locked route will pay. Edges already carrying a live session
add nothing. Everything else is the frozen route price, tie order and DAG.
"""

from __future__ import annotations

from collections import Counter

from simulator.event_simulator.request import PipelineStage, RequestPhase

from experiments.v3_cycle_pricing.scheduler import RouteRecorder
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler


class CohortPricing:
    cohort_tokens = 1.0

    def _live_edges(self) -> Counter:
        self._active_session_counts()  # prunes finished sessions
        source = self.simulator.source_node.node_uid
        edges = Counter()
        for path in self.session_paths.values():
            edges.update(zip((source, *path), path))
        return edges

    def _route(self, request):
        # Frozen WorkloadQueueDagScheduler._route plus the marked cohort term.
        sim = self.simulator
        source = sim.source_node
        sink = sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        sessions = self._active_session_counts()
        live_edges = self._live_edges()
        nodes = []
        for node in sim.compute_nodes.values():
            if node.in_vram_model_layers:
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda entry: (entry[2], entry[1], entry[0].node_uid))
        best = {(0, source.node_uid): (0.0, ())}
        for node, start, end in nodes:
            winner = None
            for (boundary, last_uid), (cost, path) in best.items():
                if not start <= boundary < end or last_uid == node.node_uid:
                    continue
                if not self._allow_placement_edge(last_uid, node.node_uid):
                    continue
                previous = (source if last_uid == source.node_uid
                            else sim.compute_nodes[last_uid])
                prompt = sum(self._layer_service(node, layer,
                                                 RequestPhase.Initialization,
                                                 request.token_seq_length)
                             for layer in range(boundary, end))
                decode_token = self._decode_token_service(
                    node, boundary, end, sessions[node.node_uid])
                gpu_wait = max(0.0, gpu_release.get(node.node_uid,
                                                     sim.current_time) - sim.current_time)
                gpu_cost = prompt + gpu_wait + sessions[node.node_uid] * decode_token
                # Cohort term: opening a new decode wave at this GPU.
                if not live_edges[(last_uid, node.node_uid)]:
                    gpu_cost += self.cohort_tokens * decode_token
                for link in previous.outbound_links.values():
                    if link.node_out.node_uid != node.node_uid:
                        continue
                    link_wait = max(0.0, link_release[link.link_uid] - sim.current_time)
                    score = cost + gpu_cost + link_wait + self._transfer_time(link, request)
                    candidate = (score, path + ((link.link_uid, node.node_uid,
                                                 boundary, end),))
                    if winner is None or candidate[0] < winner[0]:
                        winner = candidate
            if winner is not None:
                key = (end, node.node_uid)
                if key not in best or winner[0] < best[key][0]:
                    best[key] = winner
        winner = None
        for (boundary, last_uid), (cost, path) in best.items():
            if boundary != n_layers:
                continue
            if not self._allow_placement_edge(last_uid, sink.node_uid):
                continue
            previous = sim.compute_nodes[last_uid]
            for link in previous.outbound_links.values():
                if link.node_out.node_uid != sink.node_uid:
                    continue
                link_wait = max(0.0, link_release[link.link_uid] - sim.current_time)
                candidate = (cost + link_wait + self._transfer_time(link, request),
                             path, link.link_uid)
                if winner is None or candidate[0] < winner[0]:
                    winner = candidate
        if winner is None:
            raise RuntimeError("Placement has no source-to-sink layer route")
        _, path, final_link = winner
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid, layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in path]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=sink.node_uid, layers_to_infer=None))
        self.routes_assigned += 1
        return stages


class StepCohortScheduler(RouteRecorder, CohortPricing,
                          GraphModeledQueueAwareDagScheduler):
    """Price a new wave for one decode step."""

    cohort_tokens = 1.0


class LifetimeCohortScheduler(RouteRecorder, CohortPricing,
                              GraphModeledQueueAwareDagScheduler):
    """Price a new wave for the reference decode lifetime (dev-trace median)."""

    cohort_tokens = 154.0

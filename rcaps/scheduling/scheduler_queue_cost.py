"""Profile-calibrated workload shortest path on the layered DAG."""

from __future__ import annotations

from simulator.event_simulator.request import PipelineStage, RequestPhase

from .routing_dag import QueueDagScheduler


class WorkloadQueueDagScheduler(QueueDagScheduler):
    """Minimize observed queue work plus active-session work and service.

    The path cost has seconds as its unit. Every GPU and link contributes its
    current unfinished work, and every KV session contributes one profiled
    decode token amortized over the normal decode batch size. No queue-price
    coefficients are calibrated against a benchmark run.
    """

    include_committed = False
    include_session_round = False

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        """Hook for a candidate that explicitly reads the deployed M1 DAG."""
        return True

    def _decode_token_service(self, node, first, end, active_sessions):
        typical = max(1, node.inference_settings.decode_typical_tokens)
        return sum(self._layer_service(node, layer, RequestPhase.Increment,
                                       typical) / typical
                   for layer in range(first, end))

    def _route(self, request):
        sim = self.simulator
        source = sim.source_node
        sink = sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        sessions = self._active_session_counts()
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


class SingleTokenQueueCostScheduler(WorkloadQueueDagScheduler):
    """Price each live KV session using one measured decode-token service."""

    def _decode_token_service(self, node, first, end, active_sessions):
        return sum(self._layer_service(node, layer, RequestPhase.Increment, 1)
                   for layer in range(first, end))


# Older ablation classes and result names use this historical class name.
SerialWorkloadQueueDagScheduler = SingleTokenQueueCostScheduler


class CorrectedSerialWorkloadQueueDagScheduler(SerialWorkloadQueueDagScheduler):
    """Account for the simulator's doubled service time at decode batch one."""

    def _decode_token_service(self, node, first, end, active_sessions):
        return 2 * super()._decode_token_service(node, first, end, active_sessions)


class AdaptiveBatchWorkloadQueueDagScheduler(WorkloadQueueDagScheduler):
    """Price live KV sessions at their observed decode batch occupancy."""

    def _decode_token_service(self, node, first, end, active_sessions):
        typical = max(1, node.inference_settings.decode_typical_tokens)
        batch = min(active_sessions + 1, typical)
        return sum(self._layer_service(node, layer, RequestPhase.Increment,
                                       batch) / batch
                   for layer in range(first, end))


class PromptLinkWorkloadQueueDagScheduler(SerialWorkloadQueueDagScheduler):
    """Serve prompts first on a contested link to protect first-token latency."""

    prompt_link_priority = True


class AgeProtectedWorkloadQueueDagScheduler(PromptLinkWorkloadQueueDagScheduler):
    """Run a prompt batch first after it has waited one decode service batch."""

    def schedule_execution(self, node, executable_requests):
        prompts = [request for request in executable_requests
                   if request.phase == RequestPhase.Initialization]
        decodes = [request for request in executable_requests
                   if request.phase == RequestPhase.Increment]
        if prompts and decodes:
            oldest = min(request.location_history[-1][1] for request in prompts)
            typical = max(1, node.inference_settings.decode_typical_tokens)
            batch = min(len(decodes), typical)
            decode_service = self._layer_service(
                node, node.current_layer_id, RequestPhase.Increment, batch)
            if self.simulator.current_time - oldest >= decode_service:
                return super().schedule_execution(node, prompts)
        return super().schedule_execution(node, executable_requests)

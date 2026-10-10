"""Lexicographic decode-capacity / prompt-finish DAG labels."""

from __future__ import annotations

from simulator.event_simulator.request import PipelineStage, RequestPhase

from experiments.queue_dag.routing_dag import QueueDagScheduler


class DecodeFirstQueueDagScheduler(QueueDagScheduler):
    """Minimize one decode service round, then the queue-aware prompt finish.

    The first label is a bottleneck-pressure proxy for throughput; the second
    is the earliest-finish label. Both are derived from live sessions and
    hardware profiles. The lexicographic order avoids fitted objective weights.
    """

    @staticmethod
    def _one_token_transfer(link, request) -> float:
        if link.node_in.node_type.name == "Source" or link.node_out.node_type.name == "Sink":
            payload = request.token_size
        else:
            payload = request.token_size + request.activation_size
        bandwidth = min(link.bandwidth, link.node_in.outbound_nic_speed,
                        link.node_out.inbound_nic_speed)
        return link.latency + payload / bandwidth

    def _decode_round(self):
        sim = self.simulator
        sessions = self._active_session_counts()
        result = {}
        for uid, node in sim.compute_nodes.items():
            if not node.in_vram_model_layers:
                continue
            remaining = sessions[uid] + 1
            limit = max(1, min(node.inference_settings.decode_typical_tokens,
                               node.inference_settings.decode_max_tokens))
            service = 0.0
            while remaining:
                batch = min(remaining, limit)
                service += sum(self._layer_service(node, layer,
                                                   RequestPhase.Increment, batch)
                               for layer in node.in_vram_model_layers)
                remaining -= batch
            result[uid] = service
        return result

    def _route(self, request):
        sim = self.simulator
        source = sim.source_node
        sink = sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        round_time = self._decode_round()
        nodes = []
        for node in sim.compute_nodes.values():
            if node.in_vram_model_layers:
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda entry: (entry[2], entry[1], entry[0].node_uid))
        best = {(0, source.node_uid): (0.0, sim.current_time, ())}
        for node, start, end in nodes:
            winner = None
            for (boundary, last_uid), (decode, finish, path) in best.items():
                if not start <= boundary < end or last_uid == node.node_uid:
                    continue
                previous = (source if last_uid == source.node_uid
                            else sim.compute_nodes[last_uid])
                for link in previous.outbound_links.values():
                    if link.node_out.node_uid != node.node_uid:
                        continue
                    arrival = max(finish, link_release[link.link_uid]) + self._transfer_time(
                        link, request)
                    compute = sum(self._layer_service(node, layer,
                                                      RequestPhase.Initialization,
                                                      request.token_seq_length)
                                  for layer in range(boundary, end))
                    done = max(arrival, gpu_release.get(node.node_uid, sim.current_time)) + compute
                    candidate = (decode + self._one_token_transfer(link, request) +
                                 round_time[node.node_uid], done,
                                 path + ((link.link_uid, node.node_uid, boundary, end),))
                    if winner is None or candidate[:2] < winner[:2]:
                        winner = candidate
            if winner is not None:
                key = (end, node.node_uid)
                if key not in best or winner[:2] < best[key][:2]:
                    best[key] = winner
        winner = None
        for (boundary, last_uid), (decode, finish, path) in best.items():
            if boundary != n_layers:
                continue
            previous = sim.compute_nodes[last_uid]
            for link in previous.outbound_links.values():
                if link.node_out.node_uid != sink.node_uid:
                    continue
                done = max(finish, link_release[link.link_uid]) + self._transfer_time(
                    link, request)
                candidate = (decode + self._one_token_transfer(link, request),
                             done, path, link.link_uid)
                if winner is None or candidate[:2] < winner[:2]:
                    winner = candidate
        if winner is None:
            raise RuntimeError("Placement has no source-to-sink layer route")
        _, _, path, final_link = winner
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid, layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in path]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=sink.node_uid, layers_to_infer=None))
        self.routes_assigned += 1
        return stages

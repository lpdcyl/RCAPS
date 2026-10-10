"""Pareto-label DAG search for the throughput-delay tradeoff."""

from __future__ import annotations

from simulator.event_simulator.request import PipelineStage, RequestPhase

from experiments.queue_dag.experimental.scheduler_decode import DecodeFirstQueueDagScheduler


def insert_nondominated(labels, candidate):
    """Retain labels whose prompt time and decode cycle are both useful."""
    time, decode, _ = candidate
    if any(other_time <= time and other_decode <= decode
           for other_time, other_decode, _ in labels):
        return
    labels[:] = [(other_time, other_decode, path)
                 for other_time, other_decode, path in labels
                 if not (time <= other_time and decode <= other_decode)]
    labels.append(candidate)


class ParetoQueueDagScheduler(DecodeFirstQueueDagScheduler):
    """Choose the minimum product of prompt completion and decode cycle.

    The product is scale invariant and has no fitted objective coefficient.
    Earlier prompt time and lower decode-cycle time form the Pareto labels.
    """

    @staticmethod
    def _final_score(prompt_latency, decode_cycle):
        return prompt_latency * decode_cycle

    def _route(self, request):
        sim = self.simulator
        source = sim.source_node
        sink = sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        round_time = self._decode_round()
        nodes = []
        for node in sim.compute_nodes.values():
            if (node.in_vram_model_layers and
                    (not hasattr(self, "allowed_nodes") or
                     node.node_uid in self.allowed_nodes)):
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda entry: (entry[2], entry[1], entry[0].node_uid))
        labels = {(0, source.node_uid): [(sim.current_time, 0.0, ())]}
        for node, start, end in nodes:
            candidates = []
            for (boundary, last_uid), state_labels in labels.items():
                if not start <= boundary < end or last_uid == node.node_uid:
                    continue
                previous = (source if last_uid == source.node_uid
                            else sim.compute_nodes[last_uid])
                if (hasattr(self, "edge_allowed") and
                        not self.edge_allowed(previous, node)):
                    continue
                for link in previous.outbound_links.values():
                    if link.node_out.node_uid != node.node_uid:
                        continue
                    compute = sum(self._layer_service(node, layer,
                                                      RequestPhase.Initialization,
                                                      request.token_seq_length)
                                  for layer in range(boundary, end))
                    added_decode = (self._one_token_transfer(link, request) +
                                    round_time[node.node_uid])
                    for finish, decode, path in state_labels:
                        arrival = max(finish, link_release[link.link_uid]) + self._transfer_time(
                            link, request)
                        done = max(arrival, gpu_release.get(node.node_uid, sim.current_time)) + compute
                        insert_nondominated(candidates, (
                            done, decode + added_decode,
                            path + ((link.link_uid, node.node_uid, boundary, end),)))
            if candidates:
                labels[(end, node.node_uid)] = candidates
        final = []
        for (boundary, last_uid), state_labels in labels.items():
            if boundary != n_layers:
                continue
            if (hasattr(self, "allowed_final_nodes") and
                    last_uid not in self.allowed_final_nodes):
                continue
            previous = sim.compute_nodes[last_uid]
            for link in previous.outbound_links.values():
                if link.node_out.node_uid != sink.node_uid:
                    continue
                for finish, decode, path in state_labels:
                    done = max(finish, link_release[link.link_uid]) + self._transfer_time(
                        link, request)
                    final.append((done, decode + self._one_token_transfer(link, request),
                                  path, link.link_uid))
        if not final:
            raise RuntimeError("Placement has no source-to-sink layer route")
        chosen = min(
            final, key=lambda entry: (self._final_score(
                                          entry[0] - sim.current_time, entry[1]),
                                      entry[0], entry[1]))
        self.last_route_score = (chosen[0] - sim.current_time, chosen[1])
        _, _, path, final_link = chosen
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid, layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in path]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=sink.node_uid, layers_to_infer=None))
        self.routes_assigned += 1
        return stages


class FirstTokenQueueDagScheduler(ParetoQueueDagScheduler):
    """Minimize predicted prompt plus one decode cycle in seconds."""

    @staticmethod
    def _final_score(prompt_latency, decode_cycle):
        return prompt_latency + decode_cycle


class ObservedQueueDagScheduler(FirstTokenQueueDagScheduler):
    """Reserve observed queues and one recurrent decode cycle only."""

    include_committed = False


class ImmediateQueueDagScheduler(FirstTokenQueueDagScheduler):
    """Reserve only work currently executing or physically queued."""

    include_committed = False
    include_session_round = False

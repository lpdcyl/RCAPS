"""Two-label DAG routing for prompt latency and pipeline decode capacity.

Prompt completion follows max-plus event timing; the steady decode interval of
a pipeline is its slowest stage. Keeping nondominated labels at each layer
boundary avoids collapsing these different objectives into one edge weight.
"""

from __future__ import annotations

from simulator.event_simulator.request import PipelineStage, RequestPhase

from experiments.queue_dag.routing_dag import QueueDagScheduler
from experiments.queue_dag.experimental.scheduler_pareto import insert_nondominated


class BottleneckParetoQueueDagScheduler(QueueDagScheduler):
    """Choose the path with the smallest worst relative objective regret."""

    include_committed = False
    include_session_round = False

    def _decode_period(self, node, first: int, end: int, sessions: int) -> float:
        remaining = sessions + 1  # include the newly admitted KV session
        limit = max(1, min(node.inference_settings.decode_typical_tokens,
                           node.inference_settings.decode_max_tokens))
        period = 0.0
        while remaining:
            batch = min(remaining, limit)
            period += sum(self._layer_service(node, layer,
                                               RequestPhase.Increment, batch)
                          for layer in range(first, end))
            remaining -= batch
        return period

    def _route(self, request):
        sim = self.simulator
        source, sink = sim.source_node, sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        sessions = self._active_session_counts()
        nodes = []
        for node in sim.compute_nodes.values():
            if node.in_vram_model_layers:
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda entry: (entry[2], entry[1], entry[0].node_uid))

        # Each label is (predicted prompt finish, decode period, route).
        labels = {(0, source.node_uid): [(sim.current_time, 0.0, ())]}
        for node, start, end in nodes:
            candidates = []
            for (boundary, last_uid), previous_labels in labels.items():
                if not start <= boundary < end or last_uid == node.node_uid:
                    continue
                previous = (source if last_uid == source.node_uid
                            else sim.compute_nodes[last_uid])
                compute = sum(self._layer_service(node, layer,
                                                  RequestPhase.Initialization,
                                                  request.token_seq_length)
                              for layer in range(boundary, end))
                period = self._decode_period(node, boundary, end,
                                             sessions[node.node_uid])
                for link in previous.outbound_links.values():
                    if link.node_out.node_uid != node.node_uid:
                        continue
                    for finish, bottleneck, path in previous_labels:
                        arrival = max(finish, link_release[link.link_uid]) + \
                            self._transfer_time(link, request)
                        done = max(arrival, gpu_release.get(node.node_uid,
                                                            sim.current_time)) + compute
                        insert_nondominated(candidates, (
                            done, max(bottleneck, period),
                            path + ((link.link_uid, node.node_uid, boundary, end),)))
            if candidates:
                labels[(end, node.node_uid)] = candidates

        final = []
        for (boundary, last_uid), state_labels in labels.items():
            if boundary != n_layers:
                continue
            previous = sim.compute_nodes[last_uid]
            for link in previous.outbound_links.values():
                if link.node_out.node_uid != sink.node_uid:
                    continue
                for finish, bottleneck, path in state_labels:
                    done = max(finish, link_release[link.link_uid]) + \
                        self._transfer_time(link, request)
                    final.append((done, bottleneck, path, link.link_uid))
        if not final:
            raise RuntimeError("Placement has no source-to-sink layer route")

        # Both ideals come from the current Pareto set; no benchmark-tuned
        # conversion coefficient between first-token delay and TPOT is used.
        ideal_first = min(done - sim.current_time + period
                          for done, period, _, _ in final)
        ideal_period = min(period for _, period, _, _ in final)
        chosen = min(final, key=lambda item: (
            max((item[0] - sim.current_time + item[1]) / ideal_first,
                item[1] / ideal_period),
            item[0] - sim.current_time + item[1], item[1]))
        _, _, path, final_link = chosen
        stages = [PipelineStage(link_uid=link_uid, bandwidth_usage=-1,
                                node_uid=node_uid,
                                layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in path]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=sink.node_uid,
                                    layers_to_infer=None))
        self.routes_assigned += 1
        return stages

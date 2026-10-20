"""A bounded output-length oracle for the fixed-Decode-path V3 scheduler."""

from __future__ import annotations

from collections import Counter

from simulator.event_simulator.request import PipelineStage, RequestPhase

from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler


class LengthOracleGraphDagScheduler(GraphModeledQueueAwareDagScheduler):
    """Route prompts with true remaining output lengths, while retaining KV paths.

    This is deliberately not an omniscient future-arrival oracle.  At a prompt
    decision it sees only the currently live queries and their simulator target
    output lengths.  Each query's Decode requests still reuse its prompt route,
    so no KV migration or per-token rerouting is permitted.
    """

    def _remaining_session_work(self) -> Counter:
        live = self.simulator.query_manager.queries_on_the_fly
        self.session_paths = {uid: path for uid, path in self.session_paths.items()
                              if uid in live}
        work = Counter()
        for query_uid, path in self.session_paths.items():
            query = live[query_uid]
            # next_iteration_idx is 1 immediately after issuing a prompt;
            # already-issued Decode tokens are represented by existing queues.
            remaining = max(0, query.output_seq_length -
                            (query.next_iteration_idx - 1))
            for node_uid in path:
                work[node_uid] += remaining
        return work

    def _route(self, request):
        sim = self.simulator
        source = sim.source_node
        sink = sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        remaining_work = self._remaining_session_work()
        target_output = sim.query_manager.queries_on_the_fly[
            request.base_query_uid].output_seq_length
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
                    node, boundary, end, remaining_work[node.node_uid])
                gpu_wait = max(0.0, gpu_release.get(node.node_uid,
                                                     sim.current_time) - sim.current_time)
                # The current prompt is a new, irrevocably committed session.
                gpu_cost = (prompt + gpu_wait +
                            (remaining_work[node.node_uid] + target_output)
                            * decode_token)
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
            if boundary != n_layers or not self._allow_placement_edge(last_uid, sink.node_uid):
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
                                node_uid=node_uid,
                                layers_to_infer=list(range(first, end)))
                  for link_uid, node_uid, first, end in path]
        stages.append(PipelineStage(link_uid=final_link, bandwidth_usage=-1,
                                    node_uid=sink.node_uid, layers_to_infer=None))
        self.routes_assigned += 1
        return stages

"""Layer-DAG routing and phase-aware batching, independent of Helix flow scheduling."""

from __future__ import annotations

from collections import defaultdict
from math import inf

from simulator.event_simulator.compute_node import ComputeNode
from simulator.event_simulator.coordinator_node import SourceNode
from simulator.event_simulator.request import PipelineStage, RequestPhase
from simulator.event_simulator.network_link import TransmissionType
from simulator.scheduler.base_scheduler import BaseScheduler, ExecutionSchedule, TransmissionSchedule
from experiments.graph_pipeline.model import EventDagModel


class LayerDagScheduler(BaseScheduler):
    def __init__(self, simulator, queue_weight: float = 0.03, session_weight: float = 0.012,
                 decode_priority: bool = True):
        self.simulator = simulator
        self.queue_weight = queue_weight
        self.session_weight = session_weight
        self.decode_priority = decode_priority
        self.session_paths = {}
        self.route_counter = 0
        self.cost_model = EventDagModel(queue_weight, session_weight)

    def _active_sessions(self):
        live = self.simulator.query_manager.queries_on_the_fly
        self.session_paths = {q: p for q, p in self.session_paths.items() if q in live}
        counts = defaultdict(int)
        for path in self.session_paths.values():
            for uid in path:
                counts[uid] += 1
        return counts

    def _route(self, request):
        """Shortest path over states (last node, next uncomputed layer)."""
        simulator = self.simulator
        count = simulator.model_manager.get_num_layers()
        source = simulator.source_node
        sink = simulator.sink_node
        sessions = self._active_sessions()
        nodes = []
        for node in simulator.compute_nodes.values():
            if node.in_vram_model_layers:
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda entry: (entry[2], entry[1], entry[0].node_uid))
        best = {(0, source.node_uid): (0.0, [])}
        for current, start, end in nodes:
            choices = []
            for (next_layer, last_uid), (cost, path) in best.items():
                if start <= next_layer < end and last_uid != current.node_uid:
                    last_node = source if last_uid == source.node_uid else simulator.compute_nodes[last_uid]
                    links = [link for link in last_node.outbound_links.values()
                             if link.node_out.node_uid == current.node_uid]
                    if not links:
                        continue
                    link = min(links, key=lambda item: item.latency +
                               request.token_seq_length * request.activation_size / item.bandwidth)
                    bytes_per_token = request.token_size if last_uid == source.node_uid else request.activation_size
                    transfer = self.cost_model.transfer_cost(link, request.token_seq_length,
                                                             bytes_per_token)
                    stage_cost = self.cost_model.compute_cost(current, next_layer, end,
                                                              request.token_seq_length,
                                                              sessions[current.node_uid])
                    stage = PipelineStage(link_uid=link.link_uid, bandwidth_usage=-1,
                                          node_uid=current.node_uid, layers_to_infer=list(range(next_layer, end)))
                    choices.append((cost + transfer + stage_cost["total_s"], path + [stage]))
            if choices:
                candidate = min(choices, key=lambda item: item[0])
                key = (end, current.node_uid)
                if key not in best or candidate[0] < best[key][0]:
                    best[key] = candidate
        final = []
        for (next_layer, last_uid), (cost, path) in best.items():
            if next_layer != count:
                continue
            last_node = simulator.compute_nodes[last_uid]
            links = [link for link in last_node.outbound_links.values()
                     if link.node_out.node_uid == sink.node_uid]
            if links:
                link = min(links, key=lambda item: item.latency + request.token_size / item.bandwidth)
                final.append((cost + link.latency, path + [PipelineStage(
                    link_uid=link.link_uid, bandwidth_usage=-1,
                    node_uid=sink.node_uid, layers_to_infer=None)]))
        if not final:
            raise RuntimeError("Placement does not contain a source-to-sink layer path")
        path = min(final, key=lambda item: item[0])[1]
        self.session_paths[request.base_query_uid] = [stage.node_uid for stage in path[:-1]]
        return path

    def schedule_transmission(self, node):
        schedules = []
        free_send = node.outbound_available_bandwidth
        free_receive = {link.node_out.node_uid: link.node_out.inbound_available_bandwidth
                        for link in node.outbound_links.values()}
        used_links = set()
        requests = list(node.outbound_request_dict.values())
        if self.decode_priority:
            requests.sort(key=lambda req: (req.phase != RequestPhase.Increment,
                                           req.location_history[0][1], req.request_uid))
        for request in requests:
            if request.phase == RequestPhase.Initialization and not request.pipeline_set:
                if not isinstance(node, SourceNode):
                    raise RuntimeError("Initialization route must be assigned at source")
                request.set_pipeline(self._route(request))
            stage = request.get_next_pipeline_stage()
            link = node.outbound_links[stage.link_uid]
            if link.link_uid in used_links:
                continue
            amount = min(free_send, link.get_available_bandwidth(),
                         free_receive[link.node_out.node_uid])
            if amount <= 1:
                continue
            request.march_pipeline_stage()
            schedules.append(TransmissionSchedule(link_uid=link.link_uid,
                                                  bandwidth_usage=amount, requests=[request],
                                                  transmission_type=TransmissionType.NormalExecution))
            free_send -= amount
            free_receive[link.node_out.node_uid] -= amount
            used_links.add(link.link_uid)
            if free_send <= 1:
                break
        return schedules, []

    def schedule_execution(self, node, executable_requests):
        settings = node.inference_settings
        candidates = list(executable_requests)
        if self.decode_priority:
            candidates.sort(key=lambda req: (req.phase != RequestPhase.Increment,
                                             req.location_history[0][1], req.request_uid))
        selected = []
        prompt_count = prompt_tokens = decode_tokens = decode_context = 0
        for req in candidates:
            if req.phase == RequestPhase.Initialization:
                if (prompt_count + 1 <= settings.prompt_max_requests and
                        prompt_tokens + req.token_seq_length <= settings.prompt_max_tokens):
                    selected.append(req)
                    prompt_count += 1
                    prompt_tokens += req.token_seq_length
            else:
                if (decode_tokens + 1 <= settings.decode_max_tokens and
                        decode_context + req.prev_num_tokens <= settings.decode_max_context):
                    selected.append(req)
                    decode_tokens += 1
                    decode_context += req.prev_num_tokens
        return ExecutionSchedule(node_uid=node.node_uid, requests=selected)

    def schedule_model_loading(self):
        return None

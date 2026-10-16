"""Earliest-finish routing over a queue-aware, layered compatibility DAG.

At the admission of a prompt, the scheduler takes one read-only snapshot of
work already executing, queued, or committed to an existing request's route.
Each GPU and link receives a virtual release time. A DAG dynamic program
propagates the earliest completion time through all legal layer intervals:

    arrival = max(previous_finish, link_release) + transmission_time
    finish  = max(arrival, gpu_release) + prompt_service_time

The transition is FIFO/monotone in previous_finish, so the best arrival at a
(last GPU, layer boundary) state dominates later arrivals. After admission,
decode requests reuse the prompt route to keep their KV cache in place.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import inf

from rcaps.placement.topology import profile_at as interpolate_profile
from simulator.event_simulator.coordinator_node import SourceNode
from simulator.event_simulator.event import EventHandler
from simulator.event_simulator.network_link import TransmissionType
from simulator.event_simulator.request import PipelineStage, RequestLocation, RequestPhase
from simulator.scheduler.base_scheduler import BaseScheduler, ExecutionSchedule, TransmissionSchedule


class QueueDagScheduler(BaseScheduler):
    include_committed = True
    include_session_round = True
    prompt_link_priority = False

    def __init__(self, simulator):
        self.simulator = simulator
        self.service_cache = {}
        self.routes_assigned = 0
        self.session_paths = {}

    def _active_session_counts(self):
        live = self.simulator.query_manager.queries_on_the_fly
        self.session_paths = {uid: path for uid, path in self.session_paths.items()
                              if uid in live}
        counts = Counter()
        for path in self.session_paths.values():
            counts.update(path)
        return counts

    def _layer_service(self, node, layer_id: int, phase: RequestPhase,
                       tokens: int) -> float:
        key = (node.node_uid, layer_id, phase, tokens)
        if key not in self.service_cache:
            profile = node.in_vram_model_layers[layer_id]
            points = (profile.prompt_bs2time if phase == RequestPhase.Initialization
                      else profile.decode_bs2time)
            self.service_cache[key] = interpolate_profile(points, tokens)
        return self.service_cache[key]

    def _request_work(self, node, request, first: int, last: int) -> float:
        next_layer = (request.inference_history[-1].layer_id + 1
                      if request.inference_history else 0)
        first = max(first, next_layer)
        if first >= last:
            return 0.0
        if request.phase == RequestPhase.Initialization:
            return sum(self._layer_service(node, layer, request.phase,
                                           request.token_seq_length)
                       for layer in range(first, last))
        typical = max(1, node.inference_settings.decode_typical_tokens)
        return sum(self._layer_service(node, layer, RequestPhase.Increment,
                                       typical) / typical
                   for layer in range(first, last))

    @staticmethod
    def _transfer_time(link, request) -> float:
        if isinstance(link.node_in, SourceNode) or link.node_out.node_type.name == "Sink":
            payload = request.token_size * request.token_seq_length
        else:
            payload = ((request.token_size + request.activation_size) *
                       request.token_seq_length)
        bandwidth = min(link.bandwidth, link.node_in.outbound_nic_speed,
                        link.node_out.inbound_nic_speed)
        return link.latency + payload / bandwidth

    def _release_snapshot(self):
        """Translate existing batches, queues and committed sends to seconds."""
        sim = self.simulator
        now = sim.current_time
        finish_gpu = {}
        finish_link = {}
        finish_sender = {}
        finish_receiver = {}
        for event_time, event in sim.event_queue.queue:
            if event.event_handler == EventHandler.FinishExecution:
                uid = event.args["node_uid"]
                finish_gpu[uid] = min(finish_gpu.get(uid, inf), event_time)
            elif event.event_handler == EventHandler.FinishSending:
                uid = event.args["link_uid"]
                link = sim.links[uid]
                finish_link[uid] = min(finish_link.get(uid, inf), event_time)
                sender = link.node_in.node_uid
                receiver = link.node_out.node_uid
                finish_sender[sender] = min(finish_sender.get(sender, inf), event_time)
                finish_receiver[receiver] = min(finish_receiver.get(receiver, inf), event_time)

        gpu_work = defaultdict(float)
        for node in sim.compute_nodes.values():
            layers = sorted(node.in_vram_model_layers)
            if not layers:
                continue
            if node.current_inference_batch is not None:
                gpu_work[node.node_uid] += max(0.0, finish_gpu.get(
                    node.node_uid, now + node.current_inference_batch.duration) - now)
            for request in node.inbound_request_queue:
                gpu_work[node.node_uid] += self._request_work(
                    node, request, layers[0], layers[-1] + 1)
            for queue in node.between_layer_queues.values():
                for request in queue:
                    gpu_work[node.node_uid] += self._request_work(
                        node, request, layers[0], layers[-1] + 1)

        # Only requests already issued and holding a fixed pipeline are
        # counted. This is committed work, not an output-length forecast.
        for request in (sim.requests_on_the_fly.values()
                        if self.include_committed else ()):
            if not request.pipeline_set:
                continue
            for stage in request.mini_pipeline:
                if stage.layers_to_infer is None:
                    continue
                if (request.current_location == RequestLocation.ComputeNode and
                        request.current_location_uid == stage.node_uid):
                    continue  # included in batch/queues above
                node = sim.compute_nodes[stage.node_uid]
                gpu_work[node.node_uid] += self._request_work(
                    node, request, stage.layers_to_infer[0],
                    stage.layers_to_infer[-1] + 1)

        # A live KV session will issue another decode token after its current
        # iteration. Reserve one batch-aware decode service round per GPU;
        # this captures persistent occupancy without using output lengths.
        active_sessions = (self._active_session_counts()
                           if self.include_session_round else Counter())
        for uid, count in active_sessions.items():
            node = sim.compute_nodes[uid]
            limit = max(1, min(node.inference_settings.decode_typical_tokens,
                               node.inference_settings.decode_max_tokens))
            layers = sorted(node.in_vram_model_layers)
            while count:
                batch = min(count, limit)
                gpu_work[uid] += sum(self._layer_service(
                    node, layer, RequestPhase.Increment, batch) for layer in layers)
                count -= batch

        link_work = defaultdict(float)
        for node in (sim.source_node, *sim.compute_nodes.values()):
            for request in node.outbound_request_dict.values():
                if not request.pipeline_set:
                    continue
                stage = request.get_next_pipeline_stage()
                link = node.outbound_links[stage.link_uid]
                link_work[link.link_uid] += self._transfer_time(link, request)

        gpu_release = {uid: now + work for uid, work in gpu_work.items()}
        link_release = {}
        for link in sim.links.values():
            wait = 0.0
            if link.available_bandwidth <= 1:
                wait = max(wait, finish_link.get(link.link_uid, now) - now)
            if link.node_in.outbound_available_bandwidth <= 1:
                wait = max(wait, finish_sender.get(link.node_in.node_uid, now) - now)
            if link.node_out.inbound_available_bandwidth <= 1:
                wait = max(wait, finish_receiver.get(link.node_out.node_uid, now) - now)
            link_release[link.link_uid] = now + wait + link_work[link.link_uid]
        return gpu_release, link_release

    def _route(self, request):
        sim = self.simulator
        source = sim.source_node
        sink = sim.sink_node
        n_layers = sim.model_manager.get_num_layers()
        gpu_release, link_release = self._release_snapshot()
        nodes = []
        for node in sim.compute_nodes.values():
            if node.in_vram_model_layers:
                layers = sorted(node.in_vram_model_layers)
                nodes.append((node, layers[0], layers[-1] + 1))
        nodes.sort(key=lambda entry: (entry[2], entry[1], entry[0].node_uid))
        best = {(0, source.node_uid): (sim.current_time, ())}
        for node, start, end in nodes:
            winner = None
            for (boundary, last_uid), (finish, path) in best.items():
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
                    item = (done, path + ((link.link_uid, node.node_uid, boundary, end),))
                    if winner is None or item[0] < winner[0]:
                        winner = item
            if winner is not None:
                key = (end, node.node_uid)
                if key not in best or winner[0] < best[key][0]:
                    best[key] = winner
        winner = None
        for (boundary, last_uid), (finish, path) in best.items():
            if boundary != n_layers:
                continue
            previous = sim.compute_nodes[last_uid]
            for link in previous.outbound_links.values():
                if link.node_out.node_uid != sink.node_uid:
                    continue
                done = max(finish, link_release[link.link_uid]) + self._transfer_time(
                    link, request)
                if winner is None or done < winner[0]:
                    winner = (done, path, link.link_uid)
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

    def schedule_transmission(self, node):
        schedules = []
        free_send = node.outbound_available_bandwidth
        free_receive = {link.node_out.node_uid: link.node_out.inbound_available_bandwidth
                        for link in node.outbound_links.values()}
        used_links = set()
        requests = list(node.outbound_request_dict.values())
        first_phase = (RequestPhase.Initialization if self.prompt_link_priority
                       else RequestPhase.Increment)
        requests.sort(key=lambda req: (req.phase != first_phase,
                                       req.location_history[0][1], req.request_uid))
        for request in requests:
            if request.phase == RequestPhase.Initialization and not request.pipeline_set:
                if not isinstance(node, SourceNode):
                    raise RuntimeError("Only source may assign a prompt route")
                request.set_pipeline(self._route(request))
                self.session_paths[request.base_query_uid] = [
                    stage.node_uid for stage in request.mini_pipeline[:-1]]
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
        candidates = sorted(executable_requests,
                            key=lambda req: (req.phase != RequestPhase.Increment,
                                             req.location_history[0][1], req.request_uid))
        selected = []
        prompt_count = prompt_tokens = decode_tokens = decode_context = 0
        for request in candidates:
            if request.phase == RequestPhase.Initialization:
                if (prompt_count + 1 <= settings.prompt_max_requests and
                        prompt_tokens + request.token_seq_length <= settings.prompt_max_tokens):
                    selected.append(request)
                    prompt_count += 1
                    prompt_tokens += request.token_seq_length
            elif (decode_tokens + 1 <= settings.decode_max_tokens and
                  decode_context + request.prev_num_tokens <= settings.decode_max_context):
                selected.append(request)
                decode_tokens += 1
                decode_context += request.prev_num_tokens
        return ExecutionSchedule(node_uid=node.node_uid, requests=selected)

    def schedule_model_loading(self):
        return None


class ImmediateFinishQueueDagScheduler(QueueDagScheduler):
    """Earliest finish using only currently executing and queued work."""

    include_committed = False
    include_session_round = False


class ObservedFinishQueueDagScheduler(QueueDagScheduler):
    """Earliest finish with one active-session decode cycle."""

    include_committed = False

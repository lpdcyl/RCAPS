"""Full-lifetime KV admission for the 42-node simulator study.

The Azure Conversation trace has at most 1000 output tokens. That declared
bound is used for every query; the generated output length is never read when
selecting a route. Reservations cover all layers resident on each selected GPU,
including layers skipped by a cross-replica edge.
"""

from __future__ import annotations

from simulator.event_simulator.coordinator_node import SourceNode
from simulator.event_simulator.event import Event, EventDescription, EventHandler
from simulator.event_simulator.request import RequestPhase

from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler

MAX_OUTPUT_TOKENS = 1000


class _KVAdmission:
    def __init__(self, simulator, *args, **kwargs):
        super().__init__(simulator, *args, **kwargs)
        self.kv_admission = {"admitted": 0, "deferred_checks": 0,
                             "cached_deferred_checks": 0,
                             "peak_waiting": 0, "minimum_headroom": None}
        self._routing_request = None
        self._reserved = {}
        self.peak_reserved = {}
        self._session_reservations = {}
        self._capacity_veto = False
        self._reservation_version = 0
        self._blocked_at = None

    def reap_finished(self):
        """Release reservations after the simulator has removed finished KV."""
        live = self.simulator.query_manager.queries_on_the_fly
        released = False
        for uid in list(self._session_reservations):
            if uid in live:
                continue
            for node_uid, amount in self._session_reservations.pop(uid).items():
                self._reserved[node_uid] -= amount
                assert self._reserved[node_uid] >= 0
            self.session_paths.pop(uid, None)
            released = True
        if released:
            self._reservation_version += 1
        return released

    def _allow_placement_edge(self, left_uid, right_uid):
        if not super()._allow_placement_edge(left_uid, right_uid):
            return False
        node = self.simulator.compute_nodes.get(right_uid)
        if node is None:
            return True
        needed = (self._routing_request.token_seq_length + MAX_OUTPUT_TOKENS) * len(node.in_vram_model_layers)
        headroom = node.kv_cache.max_capacity - self._reserved.get(right_uid, 0)
        if headroom < needed:
            self._capacity_veto = True
            return False
        return True

    def _admit(self, request):
        self.reap_finished()
        blocked_key = (request.request_uid, self._reservation_version)
        if self._blocked_at == blocked_key:
            self.kv_admission["cached_deferred_checks"] += 1
            return False
        self._routing_request = request
        self._capacity_veto = False
        try:
            route = self._route(request)
        except RuntimeError as error:
            if not self._capacity_veto or "source-to-sink layer route" not in str(error):
                raise
            self.kv_admission["deferred_checks"] += 1
            self._blocked_at = blocked_key
            return False
        finally:
            self._routing_request = None
        request.set_pipeline(route)
        path = [stage.node_uid for stage in route[:-1]]
        self.session_paths[request.base_query_uid] = path
        reservation = {uid: (request.token_seq_length + MAX_OUTPUT_TOKENS) *
                       len(self.simulator.compute_nodes[uid].in_vram_model_layers)
                       for uid in set(path)}
        assert request.base_query_uid not in self._session_reservations
        self._session_reservations[request.base_query_uid] = reservation
        self._reservation_version += 1
        for uid, amount in reservation.items():
            self._reserved[uid] = self._reserved.get(uid, 0) + amount
            assert self._reserved[uid] <= self.simulator.compute_nodes[uid].kv_cache.max_capacity
            self.peak_reserved[uid] = max(self.peak_reserved.get(uid, 0), self._reserved[uid])
        self.kv_admission["admitted"] += 1
        headrooms = [self.simulator.compute_nodes[uid].kv_cache.max_capacity -
                     self._reserved[uid]
                     for uid in set(path)]
        if headrooms:
            low = min(headrooms)
            previous = self.kv_admission["minimum_headroom"]
            self.kv_admission["minimum_headroom"] = low if previous is None else min(previous, low)
        return True

    def _retry_waiting(self, node):
        pending = sorted((request for request in node.outbound_request_dict.values()
                          if request.phase == RequestPhase.Initialization and not request.pipeline_set),
                         key=lambda request: (request.location_history[0][1], request.request_uid))
        blocked = False
        for request in pending:
            if not self._admit(request):
                blocked = True
                break
        return blocked

    def schedule_transmission(self, node):
        if not isinstance(node, SourceNode):
            return super().schedule_transmission(node)
        blocked = self._retry_waiting(node)
        if not blocked:
            return super().schedule_transmission(node)
        waiting = {uid: request for uid, request in node.outbound_request_dict.items()
                   if request.phase == RequestPhase.Initialization and not request.pipeline_set}
        self.kv_admission["peak_waiting"] = max(self.kv_admission["peak_waiting"], len(waiting))
        for uid in waiting:
            del node.outbound_request_dict[uid]
        try:
            return super().schedule_transmission(node)
        finally:
            node.outbound_request_dict.update(waiting)


def install_completion_wakeup(simulator, scheduler):
    """Wake deferred prompts exactly when a completed query frees its KV."""
    original = simulator.handle_gather_finished

    def gathered(event):
        result = original(event)
        if scheduler.reap_finished() and any(
            request.phase == RequestPhase.Initialization and not request.pipeline_set
            for request in simulator.source_node.outbound_request_dict.values()
        ):
            source = simulator.source_node
            description = EventDescription(source.entity_name, simulator.current_time,
                                           "Retry deferred KV admission")
            wakeup = Event(simulator.get_next_event_uid(), simulator.current_time,
                           EventHandler.StartTransmission, {"node": source},
                           event.description, description)
            simulator.event_queue.put((wakeup.event_time, wakeup))
        return result

    simulator.handle_gather_finished = gathered


class KVAdmittedV3(_KVAdmission, RecordedV3Scheduler):
    pass


class KVAdmittedGated(_KVAdmission, SlowLinkGatedScheduler):
    pass

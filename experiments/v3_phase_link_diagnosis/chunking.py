"""Fixed-size Prompt activation transfer chunks as a causal control.

This is a network serialization intervention, not chunked prefill compute.
The request is delivered only after all activation bytes are sent and one
unchanged propagation latency has elapsed. The already-selected route stays
fixed. Between chunks, the ordinary V3 scheduler can start ready Decodes.
"""

from __future__ import annotations

from simulator.event_simulator.base_node import NodeType
from simulator.event_simulator.event import Event, EventDescription, EventHandler
from simulator.event_simulator.request import RequestPhase


class PromptTransferChunkHook:
    def __init__(self, chunk_bytes=1_048_576):
        if chunk_bytes <= 0:
            raise ValueError("chunk_bytes must be positive")
        self.chunk_bytes = chunk_bytes
        self.simulator = None
        self.sessions = {}
        self.pending_resume = set()
        self.completed_chunks = 0
        self.paused_chunks = 0
        self.deferred_resumes = 0

    def _event(self, kind, when, node, args, background):
        description = EventDescription(who=node.entity_name, at_when=when,
                                       does_what="Prompt transfer chunk control")
        event = Event(event_uid=self.simulator.get_next_event_uid(),
                      event_time=when, event_handler=kind, args=args,
                      background=background, description=description)
        self.simulator.event_queue.put((when, event))

    def _enqueue_resumes(self, background):
        now = self.simulator.current_time
        for key, session in list(self.sessions.items()):
            if not session["paused"] or key in self.pending_resume:
                continue
            self.pending_resume.add(key)
            self._event(EventHandler.StartTransmission, now, session["link"].node_in,
                        {"_resume_prompt_chunk": key}, background)

    def install(self, simulator, beginning, ending):
        self.simulator = simulator
        for link in simulator.links.values():
            if (link.node_in_type != NodeType.Compute or
                    link.node_out_type != NodeType.Compute):
                continue
            original_calculate = link.calculate_transmission_time
            def calculate(requests, planned_bandwidth, _original=original_calculate,
                          _link=link):
                if len(requests) == 1 and requests[0].phase == RequestPhase.Initialization:
                    request = requests[0]
                    size = (request.token_size + request.activation_size) * request.token_seq_length
                    assert planned_bandwidth <= _link.available_bandwidth
                    return _link.latency + min(self.chunk_bytes, size) / planned_bandwidth
                return _original(requests, planned_bandwidth)
            link.calculate_transmission_time = calculate

            original_start = link.start_sending
            def start(requests, bandwidth_requirement, transmission_type,
                      _original=original_start, _link=link):
                obj = _original(requests, bandwidth_requirement, transmission_type)
                if len(requests) == 1 and requests[0].phase == RequestPhase.Initialization:
                    request = requests[0]
                    total = (request.token_size + request.activation_size) * request.token_seq_length
                    if total > self.chunk_bytes:
                        key = (_link.link_uid, obj.get_handle())
                        assert key not in self.sessions
                        self.sessions[key] = {"link": _link, "bandwidth": bandwidth_requirement,
                                              "remaining": total - self.chunk_bytes,
                                              "paused": False, "total_bytes": total,
                                              "sent_bytes": self.chunk_bytes}
                return obj
            link.start_sending = start

        original_handle = simulator.handle_event
        def handle(event):
            now = event.event_time
            if event.event_handler == EventHandler.StartTransmission and \
                    "_resume_prompt_chunk" in event.args:
                if now < simulator.current_time:
                    raise AssertionError("Chunk event went backward")
                simulator.current_time = now
                key = event.args["_resume_prompt_chunk"]
                self.pending_resume.discard(key)
                session = self.sessions.get(key)
                if session is None or not session["paused"]:
                    return
                link = session["link"]
                bandwidth = session["bandwidth"]
                if link.get_available_bandwidth() < bandwidth:
                    self.deferred_resumes += 1
                    return
                if link.check_availability(bandwidth).name != "Available":
                    self.deferred_resumes += 1
                    return
                link.available_bandwidth -= bandwidth
                link.node_in.outbound_available_bandwidth -= bandwidth
                link.node_out.inbound_available_bandwidth -= bandwidth
                session["paused"] = False
                chunk = min(self.chunk_bytes, session["remaining"])
                session["remaining"] -= chunk
                session["sent_bytes"] += chunk
                send_end = now + chunk / bandwidth
                self._event(EventHandler.FinishSending, send_end, link.node_in,
                            {"transmission_node": link.node_in,
                             "transmission_object_handle": key[1],
                             "link_uid": key[0], "send_end_time": send_end},
                            event.description)
                return

            if event.event_handler == EventHandler.FinishSending:
                key = (event.args["link_uid"], event.args["transmission_object_handle"])
                session = self.sessions.get(key)
                if session is not None and session["remaining"] > 0:
                    if now < simulator.current_time or session["paused"]:
                        raise AssertionError("Invalid Prompt chunk state")
                    simulator.current_time = now
                    link = session["link"]
                    bandwidth = session["bandwidth"]
                    link.available_bandwidth += bandwidth
                    link.node_in.outbound_available_bandwidth += bandwidth
                    link.node_out.inbound_available_bandwidth += bandwidth
                    session["paused"] = True
                    self.completed_chunks += 1
                    self.paused_chunks += 1
                    # Ordinary V3 Decode scheduling gets the first opportunity.
                    self._event(EventHandler.StartTransmission, now, link.node_in,
                                {"node": link.node_in}, event.description)
                    self._enqueue_resumes(event.description)
                    return
                result = original_handle(event)
                if session is not None:
                    if abs(session["sent_bytes"] - session["total_bytes"]) > 1e-5:
                        raise AssertionError("Prompt chunk byte conservation failed")
                    self.completed_chunks += 1
                    del self.sessions[key]
                self._enqueue_resumes(event.description)
                return result

            return original_handle(event)
        simulator.handle_event = handle

    def summary(self, query_samples):
        return {"treatment": "prompt_chunk_1MiB",
                "chunk_bytes": self.chunk_bytes,
                "completed_chunks": self.completed_chunks,
                "paused_chunks": self.paused_chunks,
                "deferred_resumes": self.deferred_resumes,
                "unfinished_sessions_at_window_end": len(self.sessions)}

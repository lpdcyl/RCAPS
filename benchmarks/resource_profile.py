"""Passive fixed-window GPU and network accounting for bottleneck diagnosis.

Waiting is measured from eligibility to actual execution/dispatch. Outbound
waiting includes scheduler decisions as well as bandwidth contention; it must
not be described as pure link-queue time.
"""

from __future__ import annotations

from collections import defaultdict

from simulator.event_simulator.network_link import TransmissionType


class ResourceProfile:
    def __init__(self, simulator, beginning: float, ending: float):
        self.simulator = simulator
        self.beginning = beginning
        self.ending = ending
        self.gpu_ready = {}
        self.outbound_ready = {}
        self.gpu_wait_s = defaultdict(float)
        self.gpu_wait_count = defaultdict(int)
        self.gpu_busy_s = defaultdict(float)
        self.outbound_wait_s = defaultdict(float)
        self.outbound_wait_count = defaultdict(int)
        self.link_dispatch_wait_s = defaultdict(float)
        self.link_dispatch_wait_count = defaultdict(int)
        self.link_occupied_s = defaultdict(float)
        self.link_service_request_s = defaultdict(float)
        self.link_propagation_request_s = defaultdict(float)
        self.link_request_count = defaultdict(int)

    def overlap(self, start: float, duration: float) -> float:
        return max(0.0, min(start + duration, self.ending) -
                   max(start, self.beginning))

    def install(self) -> None:
        simulator = self.simulator
        original_issue = simulator.source_node.issue_request
        source_label = simulator.source_node.entity_name

        def issue_request(*args, **kwargs):
            result = original_issue(*args, **kwargs)
            request = kwargs.get("request", args[0] if args else None)
            self.outbound_ready[(simulator.source_node.node_uid,
                                 request.request_uid)] = simulator.current_time
            return result

        simulator.source_node.issue_request = issue_request
        for node in simulator.compute_nodes.values():
            label = node.entity_name
            original_receive = node.receive_request
            original_start = node.start_execution
            original_finish = node.finish_execution

            def receive_request(*args, _original=original_receive, _node=node,
                                **kwargs):
                result = _original(*args, **kwargs)
                request = kwargs.get("request", args[0] if args else None)
                self.gpu_ready[(_node.node_uid, request.request_uid)] = simulator.current_time
                return result

            def start_execution(*args, _original=original_start, _node=node,
                                _label=label, **kwargs):
                batch = _original(*args, **kwargs)
                now = simulator.current_time
                self.gpu_busy_s[_label] += self.overlap(now, batch.duration)
                for request in batch.requests:
                    ready = self.gpu_ready.pop((_node.node_uid, request.request_uid))
                    self.gpu_wait_s[_label] += self.overlap(ready, now - ready)
                    self.gpu_wait_count[_label] += 1
                return batch

            def finish_execution(*args, _original=original_finish, _node=node,
                                 **kwargs):
                layer = _node.current_layer_id
                batch, trigger = _original(*args, **kwargs)
                for request in batch.requests:
                    key = (_node.node_uid, request.request_uid)
                    if trigger:
                        self.outbound_ready[key] = simulator.current_time
                    else:
                        self.gpu_ready[key] = simulator.current_time
                return batch, trigger

            node.receive_request = receive_request
            node.start_execution = start_execution
            node.finish_execution = finish_execution

        for link in simulator.links.values():
            original_send = link.start_sending
            label = f"{link.node_in.entity_name}->{link.node_out.entity_name}"

            def start_sending(*args, _original=original_send, _link=link,
                              _label=label, **kwargs):
                transmission = _original(*args, **kwargs)
                now = simulator.current_time
                service = transmission.duration - _link.latency
                self.link_occupied_s[_label] += (
                    self.overlap(now, service) *
                    transmission.bandwidth_usage / _link.bandwidth)
                if transmission.transmission_type == TransmissionType.NormalExecution:
                    for request in transmission.requests:
                        key = (_link.node_in.node_uid, request.request_uid)
                        ready = self.outbound_ready.pop(key)
                        waited = self.overlap(ready, now - ready)
                        sender = _link.node_in.entity_name
                        self.outbound_wait_s[sender] += waited
                        self.outbound_wait_count[sender] += 1
                        self.link_dispatch_wait_s[_label] += waited
                        self.link_dispatch_wait_count[_label] += 1
                        self.link_service_request_s[_label] += self.overlap(now, service)
                        self.link_propagation_request_s[_label] += self.overlap(
                            now + service, _link.latency)
                        self.link_request_count[_label] += 1
                return transmission

            link.start_sending = start_sending

    def summary(self) -> dict:
        # Count waiting that is still outstanding at the fixed-window boundary.
        for (node_uid, _), ready in self.gpu_ready.items():
            label = self.simulator.compute_nodes[node_uid].entity_name
            self.gpu_wait_s[label] += self.overlap(ready, self.ending - ready)
        for (node_uid, _), ready in self.outbound_ready.items():
            node = (self.simulator.source_node if node_uid ==
                    self.simulator.source_node.node_uid else
                    self.simulator.compute_nodes[node_uid])
            self.outbound_wait_s[node.entity_name] += self.overlap(
                ready, self.ending - ready)
        window = self.ending - self.beginning
        return {
            "gpu_busy_fraction": {k: v / window for k, v in sorted(self.gpu_busy_s.items())},
            "gpu_queue_request_s": dict(sorted(self.gpu_wait_s.items())),
            "gpu_queue_exits": dict(sorted(self.gpu_wait_count.items())),
            "gpu_queued_at_end": len(self.gpu_ready),
            "outbound_wait_request_s": dict(sorted(self.outbound_wait_s.items())),
            "outbound_wait_exits": dict(sorted(self.outbound_wait_count.items())),
            "outbound_queued_at_end": len(self.outbound_ready),
            "link_dispatch_wait_request_s": dict(sorted(self.link_dispatch_wait_s.items())),
            "link_occupied_fraction": {
                k: v / window for k, v in sorted(self.link_occupied_s.items())},
            "link_service_request_s": dict(sorted(self.link_service_request_s.items())),
            "link_propagation_request_s": dict(sorted(self.link_propagation_request_s.items())),
            "link_request_count": dict(sorted(self.link_request_count.items())),
        }

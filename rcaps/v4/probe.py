"""Passive per-layer batching and chunk-aware network accounting.

Prompt-overlap measures overlapping resource occupancy, not causal attribution
of all queueing delay. All busy durations are clipped to the measurement window.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict

from simulator.event_simulator.request import RequestPhase


class IntervalUnion:
    def __init__(self):
        self.starts, self.ends = [], []

    def add(self, start, end):
        if self.ends and start <= self.ends[-1]:
            self.ends[-1] = max(self.ends[-1], end)
        else:
            self.starts.append(start)
            self.ends.append(end)

    def overlap(self, start, end):
        i = bisect_right(self.ends, start)
        return sum(max(0., min(b, end) - max(a, start))
                   for a, b in zip(self.starts[i:], self.ends[i:]) if a < end)


class MechanismProbe:
    def __init__(self, chunk_hook=None):
        self.chunk_hook = chunk_hook
        self.ready = {}
        self.gpu = defaultdict(Counter)
        self.batches = defaultdict(Counter)
        self.links = defaultdict(Counter)
        self.prompt = defaultdict(IntervalUnion)

    def overlap(self, start, end):
        return max(0., min(end, self.end) - max(start, self.begin))

    @staticmethod
    def kind(request):
        return "prompt" if request.phase == RequestPhase.Initialization else "decode"

    def segment(self, link, obj, start, end):
        label = f"{link.node_in.entity_name}->{link.node_out.entity_name}"
        stats = self.links[label]
        kind = self.kind(obj.requests[0])
        duration = self.overlap(start, end)
        stats["occupied_s"] += duration * obj.bandwidth_usage / link.bandwidth
        stats["service_request_s"] += duration * len(obj.requests)
        stats[f"{kind}_occupied_s"] += duration * obj.bandwidth_usage / link.bandwidth
        stats[f"{kind}_bytes_in_window"] += duration * obj.bandwidth_usage
        stats[f"{kind}_segments"] += 1
        stats[f"{kind}_max_segment_s"] = max(stats[f"{kind}_max_segment_s"], end - start)
        if kind == "prompt":
            for resource in (("link", link.link_uid), ("send", link.node_in.node_uid),
                             ("receive", link.node_out.node_uid)):
                self.prompt[resource].add(start, end)

    def install(self, simulator, beginning, ending):
        self.simulator, self.begin, self.end = simulator, beginning, ending
        if self.chunk_hook is not None:
            self.chunk_hook.install(simulator, beginning, ending)
            self.chunk_hook.segment_observer = self.segment
        original_issue = simulator.source_node.issue_request
        def issue(*args, **kwargs):
            result = original_issue(*args, **kwargs)
            req = kwargs.get("request", args[0] if args else None)
            self.ready[simulator.source_node.node_uid, req.request_uid] = simulator.current_time
            return result
        simulator.source_node.issue_request = issue
        for node in simulator.compute_nodes.values():
            original_start, original_finish = node.start_execution, node.finish_execution
            def execute(requests, _original=original_start, _node=node):
                batch = _original(requests)
                now = simulator.current_time
                clipped = self.overlap(now, now + batch.duration)
                if not clipped:
                    return batch
                p = sum(r.token_seq_length for r in batch.requests if self.kind(r) == "prompt")
                d = sum(r.token_seq_length for r in batch.requests if self.kind(r) == "decode")
                stats = self.gpu[_node.entity_name]
                stats["busy_s"] += clipped
                stats["layer_executions"] += 1
                stats["prompt_layer_tokens"] += p
                stats["decode_layer_tokens"] += d
                if d:
                    self.batches[_node.entity_name][d] += 1
                # Homogeneous executions permit exact phase attribution including
                # CPU-buffer overhead. Mixed batches are reported separately.
                phase = "mixed" if p and d else "prompt" if p else "decode"
                stats[f"{phase}_busy_s"] += clipped
                return batch
            def finish(*args, _original=original_finish, _node=node, **kwargs):
                batch, trigger = _original(*args, **kwargs)
                if trigger:
                    for req in batch.requests:
                        self.ready[_node.node_uid, req.request_uid] = simulator.current_time
                return batch, trigger
            node.start_execution, node.finish_execution = execute, finish
        for link in simulator.links.values():
            original_start, original_finish = link.start_sending, link.finish_sending
            def send(requests, bandwidth_requirement, transmission_type,
                     _original=original_start, _link=link):
                obj = _original(requests, bandwidth_requirement, transmission_type)
                now = simulator.current_time
                label = f"{_link.node_in.entity_name}->{_link.node_out.entity_name}"
                stats = self.links[label]
                stats["capacity_Bps"] = _link.bandwidth
                for req in requests:
                    ready = self.ready.pop((_link.node_in.node_uid, req.request_uid), now)
                    kind = self.kind(req)
                    start = max(ready, self.begin)
                    end = min(now, self.end)
                    stats[f"{kind}_messages"] += 1
                    stats[f"{kind}_wait_s"] += max(0., end - start)
                    if kind == "decode" and end > start:
                        stats["decode_wait_prompt_same_link_s"] += self.prompt[
                            "link", _link.link_uid].overlap(start, end)
                        stats["decode_wait_prompt_sender_nic_s"] += self.prompt[
                            "send", _link.node_in.node_uid].overlap(start, end)
                        stats["decode_wait_prompt_receiver_nic_s"] += self.prompt[
                            "receive", _link.node_out.node_uid].overlap(start, end)
                self.segment(_link, obj, now, now + obj.duration - _link.latency)
                return obj
            def finish_send(transmission_object_handle, _original=original_finish, _link=link):
                obj = _original(transmission_object_handle)
                label = f"{_link.node_in.entity_name}->{_link.node_out.entity_name}"
                now = simulator.current_time
                self.links[label]["propagation_request_s"] += (
                    self.overlap(now, now + _link.latency) * len(obj.requests))
                return obj
            link.start_sending, link.finish_sending = send, finish_send

    def summary(self, query_samples):
        window = self.end - self.begin
        gpu = {}
        for label, stats in sorted(self.gpu.items()):
            histogram = self.batches[label]
            tokens = sum(k * v for k, v in histogram.items())
            gpu[label] = dict(stats, decode_batch_histogram=dict(sorted(histogram.items())),
                              token_weighted_decode_batch=(sum(k*k*v for k,v in histogram.items()) / tokens
                                                           if tokens else None),
                              singleton_execution_fraction=(histogram[1] / sum(histogram.values())
                                                            if histogram else None))
        result = {"schema": "v4_chunk_aware_v1", "gpu": gpu,
                  "links": {k: dict(v) for k, v in sorted(self.links.items())},
                  "notes": "NIC overlaps may overlap each other; do not sum them. Mixed GPU busy is separate.",
                  "corrected_network_accounting": {
                      "link_occupied_fraction": {k: v["occupied_s"] / window for k, v in self.links.items()},
                      "link_service_request_s": {k: v["service_request_s"] for k, v in self.links.items()},
                      "link_propagation_request_s": {k: v["propagation_request_s"] for k, v in self.links.items()}}}
        if self.chunk_hook is not None:
            result["chunking"] = self.chunk_hook.summary(query_samples)
        return result

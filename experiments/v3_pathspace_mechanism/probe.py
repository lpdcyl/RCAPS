"""Read-only path-space diagnostics attached to a fixed-window simulator."""

from __future__ import annotations

from collections import defaultdict

from experiments.v3_phase_link_diagnosis.probe import PhaseLinkProbe
from simulator.event_simulator.request import RequestPhase


class PathSpaceProbe(PhaseLinkProbe):
    def __init__(self):
        super().__init__(raw_path=None, treatment="baseline")
        self.kv_samples = defaultdict(list)
        self.decode_batch_weighted = defaultdict(float)
        self.decode_tokens = defaultdict(int)
        self.sample_times = []
        self.next_sample = None

    def _sample_through(self, horizon: float) -> None:
        while self.next_sample is not None and self.next_sample <= min(horizon, self.end):
            self.sample_times.append(self.next_sample - self.begin)
            for uid, node in self.simulator.compute_nodes.items():
                # A query owns one KV session even when it occupies many layers.
                sessions = set()
                if node.kv_cache is not None:
                    for layer_sessions in node.kv_cache.kv_cache.values():
                        sessions.update(layer_sessions)
                self.kv_samples[uid].append(len(sessions))
            self.next_sample += 10.0

    def install(self, simulator, beginning, ending):
        super().install(simulator, beginning, ending)
        self.next_sample = beginning + 10.0
        original_next_event = simulator.simulate_next_event

        def next_event():
            if not simulator.event_queue.empty():
                event_time = simulator.event_queue.queue[0][0]
                self._sample_through(event_time)
            return original_next_event()

        simulator.simulate_next_event = next_event
        original_simulate = simulator.simulate

        def simulate(*args, **kwargs):
            result = original_simulate(*args, **kwargs)
            self._sample_through(simulator.current_time)
            return result

        simulator.simulate = simulate
        for node in simulator.compute_nodes.values():
            original_exec = node.start_execution

            def start_execution(requests, _original=original_exec, _node=node):
                batch = _original(requests)
                if self.begin <= simulator.current_time < self.end:
                    decode_tokens = sum(request.token_seq_length for request in batch.requests
                                        if request.phase == RequestPhase.Increment)
                    if decode_tokens:
                        self.decode_batch_weighted[_node.node_uid] += len(batch.requests) * decode_tokens
                        self.decode_tokens[_node.node_uid] += decode_tokens
                return batch

            node.start_execution = start_execution

    def summary(self, query_samples):
        result = super().summary(query_samples)
        result["path_space"] = {
            "kv_sample_interval_s": 10,
            "kv_sample_times_s": self.sample_times,
            "gpu_kv_sessions": {
                str(uid): {
                    "mean": sum(values) / len(values) if values else None,
                    "max": max(values) if values else None,
                    "samples": len(values),
                }
                for uid, values in sorted(self.kv_samples.items())
            },
            "gpu_decode_batch": {
                str(uid): {
                    "token_weighted_mean": self.decode_batch_weighted[uid] / tokens,
                    "decode_tokens": tokens,
                }
                for uid, tokens in sorted(self.decode_tokens.items()) if tokens
            },
        }
        return result

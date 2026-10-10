"""Streaming fixed-window metrics that avoid retaining finished requests."""

from __future__ import annotations

from collections import Counter
from statistics import mean

from simulator.event_simulator.request import RequestPhase


class WindowAccumulator:
    def __init__(self, record_queries=False):
        self.output_count = 0
        self.completed_count = 0
        self.finished_total = 0
        self.finished_by_start = 0
        self.first_tokens = []
        self.tpots = []
        self.e2es = []
        self.paper_prompt_latencies = []
        self.paper_decode_latencies = []
        self.route_counts = Counter()
        self.route_latencies = {}
        self.compacted_until = {}
        self.record_queries = record_queries
        self.query_samples = {}

    def _observe_query(self, query, beginning, ending, finish=None):
        route_key = None
        if query.inference_history:
            route = query.inference_history[0].path
            route_key = "-".join(str(stage.node_uid) for stage in route[:-1])
            self.route_counts[route_key] += 1
        if not beginning <= query.creation_time < ending:
            return
        decode_ends = [item.end_time for item in query.inference_history[1:]
                       if item.request_phase == RequestPhase.Increment and
                       item.end_time < ending]
        if decode_ends:
            self.first_tokens.append(decode_ends[0] - query.creation_time)
            if route_key is not None:
                self.route_latencies.setdefault(route_key, {"ttft": [], "tpot": []})[
                    "ttft"].append(self.first_tokens[-1])
        if len(decode_ends) >= 2:
            self.tpots.append(mean(b - a for a, b in zip(decode_ends, decode_ends[1:])))
            if route_key is not None:
                self.route_latencies.setdefault(route_key, {"ttft": [], "tpot": []})[
                    "tpot"].append(self.tpots[-1])
        if finish is not None and beginning <= finish < ending:
            self.e2es.append(finish - query.creation_time)
        if self.record_queries:
            self.query_samples[str(query.query_uid)] = {
                "arrival_s": query.creation_time - beginning,
                "input_tokens": query.input_seq_length,
                "output_tokens": query.output_seq_length,
                "ttft_s": decode_ends[0] - query.creation_time if decode_ends else None,
                "tpot_s": (mean(b - a for a, b in zip(decode_ends, decode_ends[1:]))
                           if len(decode_ends) >= 2 else None),
                "completed": finish is not None and beginning <= finish < ending,
            }

    def collect(self, simulator, beginning, ending):
        # The simulator keeps every processed Event for its optional debug
        # history. Event UIDs are monotone, and the scheduler never consults
        # this history, so a fixed-window run can release these references.
        # Otherwise each Event retains requests and copied pipeline stages,
        # making long checkpoints grow without bound.
        simulator.previous_events_list.clear()
        simulator.previous_events_dict.clear()
        for finish, request in simulator.finished_requests.values():
            if beginning <= finish < ending:
                request_latency = (request.location_history[-1][1] -
                                   request.location_history[0][1])
                if request.phase == RequestPhase.Initialization:
                    self.paper_prompt_latencies.append(request_latency)
                elif request.phase == RequestPhase.Increment:
                    self.paper_decode_latencies.append(request_latency)
            if (request.phase == RequestPhase.Increment and
                    beginning <= finish < ending):
                self.output_count += request.token_seq_length
        simulator.finished_requests.clear()
        manager = simulator.query_manager
        for finish, query in manager.finished_queries.values():
            self.finished_total += 1
            if finish <= beginning:
                self.finished_by_start += 1
            if beginning <= finish < ending:
                self.completed_count += 1
            self._observe_query(query, beginning, ending, finish)
            self.compacted_until.pop(query.query_uid, None)
        manager.finished_queries.clear()
        for query in manager.queries_on_the_fly.values():
            first = max(1, self.compacted_until.get(query.query_uid, 1))
            for item in query.inference_history[first:]:
                item.path = []  # decode iterations reuse the prompt path
            self.compacted_until[query.query_uid] = len(query.inference_history)

    def observe_active(self, simulator, beginning, ending):
        for query in simulator.query_manager.queries_on_the_fly.values():
            self._observe_query(query, beginning, ending)

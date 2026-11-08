"""Capacity-safe FIFO admission for the HexGen simulator adaptation.

The baseline keeps each query on one fixed pipeline.  A query is released
from the source queue only when every stage can hold its worst-case KV length.
The reservation lasts through the query's final decode iteration.  This is a
conservative, deterministic admission rule; it does not change the trace or
count queued arrivals as completed.
"""

from __future__ import annotations

from simulator.event_simulator.coordinator_node import SourceNode
from simulator.scheduler.naive_scheduler import NaiveScheduler


class CapacitySafeScheduler(NaiveScheduler):
    def __init__(self, simulator) -> None:
        self.simulator = simulator
        self.reserved_tokens: dict[int, int] = {}
        self.kv_budget_tokens: int | None = None
        self.deferred_dispatches = 0
        self.oversize_queries: set[int] = set()
        self.max_reserved_tokens = 0

    def _budget(self) -> int:
        if self.kv_budget_tokens is None:
            stage_budgets = []
            for node in self.simulator.compute_nodes.values():
                cache = node.kv_cache
                if cache is not None and cache.layer_ids:
                    stage_budgets.append(cache.max_capacity // len(cache.layer_ids))
            if not stage_budgets:
                raise RuntimeError("HexGen pipeline has no KV-bearing stage")
            self.kv_budget_tokens = min(stage_budgets)
        return self.kv_budget_tokens

    def schedule_transmission(self, node):
        if not isinstance(node, SourceNode):
            return super().schedule_transmission(node)
        active = self.simulator.query_manager.queries_on_the_fly
        self.reserved_tokens = {uid: length for uid, length in self.reserved_tokens.items()
                                if uid in active}
        budget = self._budget()
        available = budget - sum(self.reserved_tokens.values())
        chosen = None
        for request in node.outbound_request_dict.values():
            if request.base_query_uid in self.reserved_tokens:
                chosen = request
                break
        if chosen is None:
            for request in node.outbound_request_dict.values():
                query = active[request.base_query_uid]
                demand = query.input_seq_length + query.output_seq_length
                if demand > budget:
                    self.oversize_queries.add(query.query_uid)
                if demand <= available:
                    chosen = request
                    break
        if chosen is None:
            if node.outbound_request_dict:
                self.deferred_dispatches += 1
            return [], []
        original = node.outbound_request_dict
        try:
            node.outbound_request_dict = {chosen.request_uid: chosen}
            schedules, reschedule = super().schedule_transmission(node)
        finally:
            node.outbound_request_dict = original
        sent = [request for schedule in schedules for request in schedule.requests]
        if sent:
            if len(sent) != 1 or sent[0] is not chosen:
                raise RuntimeError("Unexpected HexGen source dispatch")
            query = active[chosen.base_query_uid]
            if query.query_uid not in self.reserved_tokens:
                self.reserved_tokens[query.query_uid] = (
                    query.input_seq_length + query.output_seq_length)
            self.max_reserved_tokens = max(self.max_reserved_tokens,
                                           sum(self.reserved_tokens.values()))
        return schedules, reschedule

"""Static V3 routing: retain the graph and service costs, zero live state."""

from __future__ import annotations

from collections import Counter

from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler


class StaticGraphDagScheduler(GraphModeledQueueAwareDagScheduler):
    """Use V3's routing, Decode and transfer logic without live queue/KV prices."""

    def _release_snapshot(self):
        now = self.simulator.current_time
        return {}, {uid: now for uid in self.simulator.links}

    def _active_session_counts(self):
        return Counter()

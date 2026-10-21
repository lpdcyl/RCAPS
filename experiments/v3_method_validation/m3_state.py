"""State-factor adapters for frozen V3 routing and decode semantics."""

from __future__ import annotations

from collections import Counter

from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler


class QueueOnly(GraphModeledQueueAwareDagScheduler):
    """Current executing/queued GPU work, without dynamic link or KV pricing."""

    include_committed = False
    include_session_round = False

    def _active_session_counts(self):
        return Counter()

    def _release_snapshot(self):
        gpu, _ = super()._release_snapshot()
        return gpu, {uid: self.simulator.current_time for uid in self.simulator.links}


class ObservedEFT(GraphModeledQueueAwareDagScheduler):
    """Existing earliest-finish rule with observed GPU/link queues only."""

    include_committed = False
    include_session_round = False

    def _active_session_counts(self):
        return Counter()


class FullNoSession(GraphModeledQueueAwareDagScheduler):
    """Full committed-work model without live Decode session burden."""

    include_session_round = False

    def _active_session_counts(self):
        return Counter()


class FullNoLink(GraphModeledQueueAwareDagScheduler):
    """Full GPU and KV state without dynamic link/NIC release times."""

    def _release_snapshot(self):
        gpu, _ = super()._release_snapshot()
        return gpu, {uid: self.simulator.current_time for uid in self.simulator.links}


VARIANTS = {
    "queue_only": QueueOnly,
    "observed_eft": ObservedEFT,
    "full_no_session": FullNoSession,
    "full_no_link": FullNoLink,
    "full": GraphModeledQueueAwareDagScheduler,
}

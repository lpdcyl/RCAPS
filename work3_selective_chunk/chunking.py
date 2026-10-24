"""Restrict the existing Prompt transfer chunk hook to physical slow links."""

from __future__ import annotations

from experiments.v3_phase_link_diagnosis.chunking import PromptTransferChunkHook
from simulator.event_simulator.base_node import NodeType


class SlowLinkPromptTransferChunkHook(PromptTransferChunkHook):
    def __init__(self, chunk_bytes: int, slow_link_threshold_Bps: float):
        super().__init__(chunk_bytes)
        self.slow_link_threshold_Bps = slow_link_threshold_Bps
        self.eligible_link_uids = []

    def install(self, simulator, beginning, ending):
        # The frozen hook instruments links during install and retains each Link
        # object in its closures. No event is executed while this temporary view
        # is installed; the complete simulator graph is restored immediately.
        original_links = simulator.links
        selected = {uid: link for uid, link in original_links.items()
                    if link.node_in_type == NodeType.Compute
                    and link.node_out_type == NodeType.Compute
                    and link.bandwidth <= self.slow_link_threshold_Bps}
        self.eligible_link_uids = sorted(selected)
        try:
            simulator.links = selected
            super().install(simulator, beginning, ending)
        finally:
            simulator.links = original_links
        if simulator.links is not original_links:
            raise AssertionError("Physical link graph was not restored")

    def summary(self, query_samples):
        result = super().summary(query_samples)
        result.update({"treatment": "slow_link_prompt_chunk_1MiB",
                       "slow_link_threshold_Bps": self.slow_link_threshold_Bps,
                       "eligible_link_uids": self.eligible_link_uids})
        return result

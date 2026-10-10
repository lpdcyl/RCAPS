"""Queue-aware shortest paths constrained by placement graph corridors."""

from __future__ import annotations

import json
from configparser import ConfigParser
from pathlib import Path

from experiments.queue_dag.experimental.scheduler_pareto import FirstTokenQueueDagScheduler


class CorridorQueueDagScheduler(FirstTokenQueueDagScheduler):
    """Preserve the path ensembles produced by capacity-constrained partitioning.

    The offline partition gives disjoint branch membership plus shared GPUs.
    Online, each branch is a layered compatibility DAG: shortcuts are allowed
    within a branch, while a request cannot switch branch midway. The route
    minimizes predicted first-token completion from the current queue state.
    """

    include_committed = False

    def __init__(self, simulator, solution: Path):
        super().__init__(simulator)
        config = ConfigParser()
        config.read(solution, encoding="utf-8")
        offset = int(config["Settings"]["offset"])
        partition = json.loads((solution.parent / "placement.json").read_text(
            encoding="utf-8"))
        shared = {partition["shared"] + offset}
        self.corridors = [shared | {node + offset for node in branch}
                          for branch in partition["branches"]]
        self.corridor_choices = [0 for _ in self.corridors]

    def edge_allowed(self, previous, node):
        # A foreign GPU may be used as an isolated bridge, provided the
        # route returns to the chosen partition branch at the next hop.
        return (previous.node_uid in self.branch_nodes or
                node.node_uid in self.branch_nodes)

    def _route(self, request):
        previous_count = self.routes_assigned
        choices = []
        for index, corridor in enumerate(self.corridors):
            self.branch_nodes = corridor
            self.allowed_final_nodes = corridor
            try:
                stages = super()._route(request)
            except RuntimeError:
                continue
            prompt, decode = self.last_route_score
            choices.append((prompt + decode, prompt, decode, index, stages))
        del self.branch_nodes
        del self.allowed_final_nodes
        if not choices:
            raise RuntimeError("No source-to-sink route in any placement corridor")
        _, _, _, index, stages = min(choices, key=lambda item: item[:4])
        self.corridor_choices[index] += 1
        self.routes_assigned = previous_count + 1
        return stages

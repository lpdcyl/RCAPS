"""M3 adapter that checks transitions against the deployed M1 execution DAG."""

from __future__ import annotations

from .resource_graph import from_simulator
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


class GraphModeledQueueAwareDagScheduler(QueueAwareDagScheduler):
    def __init__(self, simulator):
        super().__init__(simulator)
        self.execution_dag = None

    def _allow_placement_edge(self, left_uid: int, right_uid: int) -> bool:
        if self.execution_dag is None:
            self.execution_dag = from_simulator(self.simulator)
        left = ("source" if left_uid == self.simulator.source_node.node_uid
                else left_uid)
        right = ("sink" if right_uid == self.simulator.sink_node.node_uid
                 else right_uid)
        return (left, right) in self.execution_dag.edge_set

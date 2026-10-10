"""Registry of development policies used by historical ablations.

The paper's final scheduler lives in ``scheduler_final.py``. Keeping these
alternatives here makes the normal evaluation entry point easy to inspect.
"""

from __future__ import annotations

from pathlib import Path

from experiments.queue_dag.routing_dag import (
    ImmediateFinishQueueDagScheduler,
    ObservedFinishQueueDagScheduler,
    QueueDagScheduler,
)
from experiments.queue_dag.scheduler_final import CoalescedQueueDagScheduler
from experiments.queue_dag.scheduler_queue_cost import (
    AdaptiveBatchWorkloadQueueDagScheduler,
    AgeProtectedWorkloadQueueDagScheduler,
    CorrectedSerialWorkloadQueueDagScheduler,
    PromptLinkWorkloadQueueDagScheduler,
    SerialWorkloadQueueDagScheduler,
    WorkloadQueueDagScheduler,
)
from .scheduler_bottleneck import BottleneckParetoQueueDagScheduler
from .scheduler_corridor import CorridorQueueDagScheduler
from .scheduler_decode import DecodeFirstQueueDagScheduler
from .scheduler_pareto import (
    FirstTokenQueueDagScheduler,
    ImmediateQueueDagScheduler,
    ObservedQueueDagScheduler,
    ParetoQueueDagScheduler,
)


POLICY_NAMES = (
    "finish", "decode", "pareto", "first_token", "observed", "immediate",
    "finish_immediate", "finish_observed", "corridor", "workload",
    "workload_serial", "workload_prompt_link", "workload_age",
    "workload_adaptive", "workload_serial_corrected", "bottleneck_pareto",
    "coalesced",
)


def scheduler_for(name: str, solution: Path):
    """Return the scheduler factory for a named development experiment."""
    policies = {
        "finish": QueueDagScheduler,
        "decode": DecodeFirstQueueDagScheduler,
        "pareto": ParetoQueueDagScheduler,
        "first_token": FirstTokenQueueDagScheduler,
        "observed": ObservedQueueDagScheduler,
        "immediate": ImmediateQueueDagScheduler,
        "finish_immediate": ImmediateFinishQueueDagScheduler,
        "finish_observed": ObservedFinishQueueDagScheduler,
        "corridor": lambda simulator: CorridorQueueDagScheduler(simulator, solution),
        "workload": WorkloadQueueDagScheduler,
        "workload_serial": SerialWorkloadQueueDagScheduler,
        "workload_prompt_link": PromptLinkWorkloadQueueDagScheduler,
        "workload_age": AgeProtectedWorkloadQueueDagScheduler,
        "workload_adaptive": AdaptiveBatchWorkloadQueueDagScheduler,
        "workload_serial_corrected": CorrectedSerialWorkloadQueueDagScheduler,
        "bottleneck_pareto": BottleneckParetoQueueDagScheduler,
        "coalesced": CoalescedQueueDagScheduler,
    }
    return policies[name]

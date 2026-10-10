"""Single-component scheduling ablations on the unchanged RCAPS placement."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .method import layout
from .scheduling.scheduler_final import QueueAwareDagScheduler
from .scheduling.scheduler_queue_cost import CorrectedSerialWorkloadQueueDagScheduler


class NoQueueWaitScheduler(QueueAwareDagScheduler):
    """Remove only the current GPU/link release-time terms from routing."""

    def _release_snapshot(self):
        now = self.simulator.current_time
        return {}, {uid: now for uid in self.simulator.links}


class NoSessionCostScheduler(QueueAwareDagScheduler):
    """Remove only the active-KV-session service term from routing."""

    def _active_session_counts(self):
        return Counter()


SCHEDULERS = {
    "rcaps_no_coalesce": CorrectedSerialWorkloadQueueDagScheduler,
    "rcaps_no_queue": NoQueueWaitScheduler,
    "rcaps_no_session": NoSessionCostScheduler,
}
LAYOUT_VARIANTS = {
    "rcaps_capacity": {"single": "single_capacity", "multi": "multi_capacity"},
    "rcaps_coarse": {"single": "single_coarse", "multi": "multi_coarse"},
    "rcaps_full_search": {"single": "single_full_search", "multi": "multi_full_search"},
    "rcaps_static_no_graph": {"single": "single_static_no_graph",
                              "multi": "multi_static_no_graph"},
    # In the single cluster canonical mode makes no accepted move; it is
    # byte-equivalent to rcaps_coarse and needs no duplicate simulation.
    "rcaps_alt_demand": {"multi": "multi_ensemble"},
}


def variant_layout(variant: str, scenario: str, root: Path) -> tuple[Path, Path]:
    if variant in LAYOUT_VARIANTS:
        if scenario not in LAYOUT_VARIANTS[variant]:
            raise ValueError(f"{variant} is not a distinct layout for {scenario}")
        directory = root / "rcaps" / "variant_layouts" / LAYOUT_VARIANTS[variant][scenario]
        return directory / "solution.ini", directory / "simulator_cluster.ini"
    return layout(scenario, root)


def evaluate(variant: str, scenario: str, offered: float, duration: int,
             warmup: int, seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    scheduler = SCHEDULERS.get(variant, QueueAwareDagScheduler)
    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, scheduler_factory=scheduler,
               compact=True, record_query_samples=True)

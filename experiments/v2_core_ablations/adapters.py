"""Experiment-only V2 evaluator, structure, and routing alternatives."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


MODEL_METHODS = {
    "rcaps_v2_model_compute": "compute_only",
    "rcaps_v2_model_static": "compute_comm",
    "rcaps_v2_model_event": "event_dag",
}
FIXED_BRANCHES = "rcaps_v2_fixed_branches"
STATIC_DAG = "rcaps_v2_static_dag"
QUEUE_DAG = "rcaps_v2_queue_dag"


class StaticCostDagScheduler(QueueAwareDagScheduler):
    """Full legal DAG and V2 transfers, with no dynamic path-cost inputs."""

    def _release_snapshot(self):
        now = self.simulator.current_time
        return {}, {uid: now for uid in self.simulator.links}

    def _active_session_counts(self):
        return Counter()


class QueueOnlyDagScheduler(QueueAwareDagScheduler):
    """V2 unfinished-work path cost without active KV-session price."""

    def _active_session_counts(self):
        return Counter()


def modeling_layout(method: str, scenario: str, root: Path) -> tuple[Path, Path]:
    directory = (root / "experiments" / "v2_core_ablations" / "layouts" /
                 "modeling" / scenario / MODEL_METHODS[method])
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def fixed_branches_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "experiments" / "v2_core_ablations" / "layouts" / "fixed_branches" / scenario
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def v2_layout(scenario: str, root: Path) -> tuple[Path, Path]:
    directory = root / "rcaps" / "v2_layouts" / f"{scenario}_adaptive"
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path,
             scheduler: type = QueueAwareDagScheduler) -> dict:
    from benchmarks.fixed_window import run

    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, profile_resources=True,
               scheduler_factory=scheduler, compact=True,
               record_query_samples=True)


def evaluate_static_dag(scenario: str, offered: float, duration: int,
                        warmup: int, seed: int, solution: Path,
                        sim_cluster: Path) -> dict:
    return evaluate(scenario, offered, duration, warmup, seed,
                    solution, sim_cluster, StaticCostDagScheduler)


def evaluate_queue_dag(scenario: str, offered: float, duration: int,
                       warmup: int, seed: int, solution: Path,
                       sim_cluster: Path) -> dict:
    return evaluate(scenario, offered, duration, warmup, seed,
                    solution, sim_cluster, QueueOnlyDagScheduler)

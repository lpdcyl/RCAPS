"""RCAPS V3 main-method adapter.

V3 combines the graph-only M1, unrestricted at-most-two-boundary M2,
and the queue-aware DAG scheduler (M3).
"""

from __future__ import annotations

from pathlib import Path


NAME = "rcaps_v3"
DESCRIPTION = "Graph-only M1, adaptive multistage M2, queue-aware DAG M3"
SCENARIOS = ("single", "multi", "C2", "C3", "C4", "C5")


def layout(scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown V3 resource pool: {scenario}")
    directory = root / "rcaps" / "v3_layouts" / scenario
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path) -> dict:
    if scenario not in ("single", "multi"):
        raise ValueError("The shared benchmark runner supports C1 single/multi only")
    from benchmarks.fixed_window import run
    from .v3.scheduler import GraphModeledQueueAwareDagScheduler

    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, profile_resources=True,
               scheduler_factory=GraphModeledQueueAwareDagScheduler,
               compact=True, record_query_samples=True)

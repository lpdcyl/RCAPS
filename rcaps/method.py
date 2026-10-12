"""Historical V1 two-suffix adapter, retained for comparison with V2."""

from __future__ import annotations

from pathlib import Path


NAME = "rcaps"
DESCRIPTION = "V1 shared-prefix/two-suffix placement and DAG scheduling"


def layout(scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario not in ("single", "multi"):
        raise ValueError(f"Unknown scenario: {scenario}")
    directory = root / "rcaps" / "layouts" / scenario
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run
    from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, scheduler_factory=QueueAwareDagScheduler,
               compact=True, record_query_samples=True)

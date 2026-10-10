"""V2 adaptive-placement methods with the unchanged V1 online scheduler."""

from __future__ import annotations

from pathlib import Path

def layout(variant: str, scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario not in ("single", "multi"):
        raise ValueError(f"Unknown scenario: {scenario}")
    if variant not in ("rcaps_v2", "rcaps_v2_fixed_structure"):
        raise ValueError(f"Unknown V2 variant: {variant}")
    suffix = "adaptive" if variant == "rcaps_v2" else "fixed"
    directory = root / "rcaps" / "v2_layouts" / f"{scenario}_{suffix}"
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run
    from .scheduling.scheduler_final import QueueAwareDagScheduler

    return run(scenario, "queue_dag", offered, duration, warmup, seed,
               solution, sim_cluster, profile_resources=True,
               scheduler_factory=QueueAwareDagScheduler, compact=True,
               record_query_samples=True)

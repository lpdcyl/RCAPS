"""Original Helix placement and max-flow scheduling baseline."""

from __future__ import annotations

from pathlib import Path


NAME = "helix"
DESCRIPTION = "Original Helix ILP placement and max-flow scheduler"


def layout(scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario == "single":
        directory = root / "artifact_evaluation" / "single_cluster" / "layout_llama70b" / "ilp"
    elif scenario == "multi":
        directory = root / "artifact_evaluation" / "distributed_clusters" / "layout_llama70b" / "ilp"
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    return directory / "ilp_sol.ini", directory / "simulator_cluster.ini"


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    return run(scenario, "helix", offered, duration, warmup, seed,
               solution, sim_cluster, compact=True, record_query_samples=True)

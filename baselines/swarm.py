"""Helix artifact's Swarm placement and online scheduler under the common window."""

from __future__ import annotations

from pathlib import Path

NAME = "swarm"
DESCRIPTION = "Helix artifact Swarm placement and original online scheduler"


def layout(scenario: str, root: Path) -> tuple[Path, Path]:
    if scenario == "single":
        directory = root / "artifact_evaluation" / "single_cluster" / "layout_llama70b" / "swarm"
    elif scenario == "multi":
        directory = root / "artifact_evaluation" / "distributed_clusters" / "layout_llama70b" / "swarm"
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    return directory / "swarm_sol.ini", directory / "simulator_cluster.ini"


def evaluate(scenario: str, offered: float, duration: int, warmup: int,
             seed: int, solution: Path, sim_cluster: Path) -> dict:
    from benchmarks.fixed_window import run

    result = run(scenario, NAME, offered, duration, warmup, seed,
                 solution, sim_cluster, compact=True, record_query_samples=True)
    return result

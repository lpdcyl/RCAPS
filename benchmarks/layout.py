"""Common simulator layouts and model-loading helper for every method."""

from __future__ import annotations

import ast
import math
from configparser import ConfigParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MACHINES = {"A100": 4, "L4": 8, "T4": 12}


class _NullLogger:
    """Avoid retaining simulator event logs during long measurements."""

    def add_log(self, **_kwargs):
        return None


def scenario(name: str) -> tuple[Path, Path, Path, Path]:
    if name == "single":
        base = ROOT / "examples" / "simulation"
        return (base / "config" / "single24.ini",
                base / "config" / "machine_profile.ini",
                base / "layouts" / "ilp" / "ilp_sol.ini",
                base / "layouts" / "ilp" / "simulator_cluster.ini")
    if name == "multi":
        base = ROOT / "artifact_evaluation" / "distributed_clusters"
        return (base / "config" / "3cluster24.ini",
                base / "config" / "machine_profiles.ini",
                base / "layout_llama70b" / "ilp" / "ilp_sol.ini",
                base / "layout_llama70b" / "ilp" / "simulator_cluster.ini")
    raise ValueError(f"Unknown scenario: {name}")


def load_graph_layout(simulator, solution: Path) -> float:
    """Load a contiguous layer assignment into the common simulator."""
    config = ConfigParser()
    if not config.read(solution):
        raise FileNotFoundError(solution)
    params = simulator.model_manager.get_model_params()
    max_load = 0.0
    for name, layers_text in config["Solution"].items():
        layers = ast.literal_eval(layers_text)
        if not layers:
            continue
        if layers != list(range(layers[0], layers[-1] + 1)):
            raise ValueError(f"Non-contiguous layers on {name}")
        node = simulator.name_2_compute_node[name]
        load_seconds = sum(params[layers[0]:layers[-1] + 1]) / node.disk_speed
        max_load = max(max_load, load_seconds)
        simulator.issue_command_load_model(load_time=0, node_uid=node.node_uid,
                                           new_layers=layers, request_uids_to_wait=[])
    start = math.ceil(max_load) + 1
    simulator.simulate(until=start)
    return start

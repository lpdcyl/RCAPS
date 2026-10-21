"""Physical GPU topology and model profiles used by V3 placement."""

from __future__ import annotations

import ast
from collections import Counter
from configparser import ConfigParser
from pathlib import Path

from simulator.event_simulator.utils import MilliSec, Sec, gbps, kbps, mbps
from simulator.model_manager.model_manager import ModelManager, ModelName


UNITS = {"kbps": kbps, "mbps": mbps, "gbps": gbps,
         "MilliSec": MilliSec, "Sec": Sec}


def profile_at(points: dict[int, float], size: int) -> float:
    sizes = sorted(points)
    if size < sizes[0] or size > sizes[-1]:
        raise ValueError(f"Batch size {size} outside profile range {sizes[0]}..{sizes[-1]}")
    if size in points:
        return points[size]
    lo = max(value for value in sizes if value < size)
    hi = min(value for value in sizes if value > size)
    return points[lo] + (points[hi] - points[lo]) * (size - lo) / (hi - lo)


class TopologyModel:
    """Deterministic hardware attributes; no request or event prediction."""

    def __init__(self, cluster_file: Path, *, prompt_tokens: int = 1000,
                 decode_batch: int = 8,
                 model_name: ModelName = ModelName.LLaMa70B):
        self.cluster_file = Path(cluster_file)
        self.config = ConfigParser()
        if not self.config.read(self.cluster_file):
            raise FileNotFoundError(self.cluster_file)
        count = ast.literal_eval(self.config["NodeNames"]["total_compute_nodes"])
        self.types = {node: self.config[f"ComputeNode-{node}"]["type"]
                      for node in range(count)}
        self.machine_counts = dict(Counter(self.types.values()))
        self.manager = ModelManager(model_name, self.machine_counts)
        self.layers = self.manager.get_num_layers()
        self.capacity = {node: self.manager.get_max_num_layers(kind)
                         for node, kind in self.types.items()}
        self.profiles = {kind: self.manager.get_profiling_results(kind)
                         for kind in set(self.types.values())}
        self.prompt_tokens = prompt_tokens
        self.decode_batch = decode_batch
        self._links: dict[tuple[str, str], tuple[float, float]] = {}

    def link(self, left: str | int, right: str | int) -> tuple[float, float]:
        key = (str(left), str(right))
        if key in self._links:
            return self._links[key]
        name = f"Link-{left}-{right}"
        if name not in self.config:
            name = f"Link-{right}-{left}"
        if name not in self.config:
            raise ValueError(f"No link {left} -> {right}")
        values = self.config[name]
        latency = float(eval(values["latency"], {"__builtins__": {}}, UNITS))
        bandwidth = float(eval(values["bandwidth"], {"__builtins__": {}}, UNITS))
        if latency < 0 or bandwidth <= 0:
            raise ValueError(f"Invalid link {name}")
        self._links[key] = (latency, bandwidth)
        return self._links[key]

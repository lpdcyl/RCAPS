"""Profiled model and physical-network graphs for placement decisions."""

from __future__ import annotations

import ast
from collections import Counter
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from simulator.event_simulator.utils import MilliSec, Sec, gbps, kbps, mbps
from simulator.model_manager.model_manager import ModelManager, ModelName

from .event_graph import interleaved_workload_graph


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


@dataclass(frozen=True)
class GraphMetrics:
    ttft_s: float
    tpot_s: float
    bottleneck_s: float
    critical_resources: frozenset[str]
    branch_ttft_s: tuple[float, ...]
    branch_tpot_s: tuple[float, ...]
    bottleneck_resource: str


class TopologyModel:
    def __init__(self, cluster_file: Path, *, prompt_tokens: int = 1000,
                 decode_batch: int = 8):
        self.cluster_file = Path(cluster_file)
        self.config = ConfigParser()
        if not self.config.read(self.cluster_file):
            raise FileNotFoundError(self.cluster_file)
        count = ast.literal_eval(self.config["NodeNames"]["total_compute_nodes"])
        self.types = {node: self.config[f"ComputeNode-{node}"]["type"]
                      for node in range(count)}
        self.machine_counts = dict(Counter(self.types.values()))
        self.manager = ModelManager(ModelName.LLaMa70B, self.machine_counts)
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

    def intervals(self, state: dict) -> dict[int, tuple[int, int]]:
        shared = state["shared"]
        common = state["shared_length"]
        if not 1 <= common <= self.capacity[shared]:
            raise ValueError("Invalid shared prefix")
        spans = {shared: (0, common)}
        used = {shared}
        for path in state["paths"]:
            position = common
            for node in path:
                if node in used:
                    raise ValueError(f"GPU {node} appears in multiple stages")
                used.add(node)
                length = state["lengths"][node]
                if not 1 <= length <= self.capacity[node]:
                    raise ValueError(f"Invalid layer count on GPU {node}")
                spans[node] = (position, position + length)
                position += length
            if position != self.layers:
                raise ValueError(f"Branch ends at layer {position}, expected {self.layers}")
        return spans

    def _stages(self, state: dict, path: list[int]) -> list[dict]:
        stages: list[dict] = []
        previous: str | int = "source"
        for node in [state["shared"], *path, "sink"]:
            latency, bandwidth = self.link(previous, node)
            token_size = self.manager.get_model_token_size()
            activation = self.manager.get_model_activation_size()
            if node == "sink":
                prefill_s = decode_s = 0.0
                payload = token_size
                prefill_items = self.prompt_tokens
            else:
                length = state["shared_length"] if node == state["shared"] else state["lengths"][node]
                profile = self.profiles[self.types[node]]
                prefill_s = length * profile_at(profile.prompt_bs2time, self.prompt_tokens)
                decode_s = length * profile_at(profile.decode_bs2time, self.decode_batch)
                payload = token_size if previous == "source" else token_size + activation
                prefill_items = self.prompt_tokens
            stages.append({"device": str(node), "prefill_s": prefill_s,
                           "decode_s": decode_s, "incoming_link": f"{previous}->{node}",
                           "incoming_latency_s": latency,
                           "incoming_bytes_per_s": bandwidth,
                           "payload_bytes": payload, "prefill_items": prefill_items})
            previous = node
        return stages

    def measure(self, state: dict, *, demand_mode: str = "ensemble") -> GraphMetrics:
        self.intervals(state)
        pipelines = [self._stages(state, path) for path in state["paths"]]
        # Two concurrent requests per branch expose queue edges on the shared
        # prefix and on each branch. Their stagger is explicit and fixed across
        # all placement candidates, so no future arrival information is used.
        request_pipelines = [pipelines[0], pipelines[1], pipelines[0], pipelines[1]]
        arrivals = [0.0, 0.05, 0.10, 0.15]
        graph, first_events, final_events = interleaved_workload_graph(
            request_pipelines, prompt_tokens=self.prompt_tokens,
            generated_tokens=8, arrivals_s=arrivals)
        first_paths = [graph.critical_path(event) for event in first_events]
        final_paths = [graph.critical_path(event) for event in final_events]
        ttfts = [path.completion_s - arrival
                 for path, arrival in zip(first_paths, arrivals)]
        tpots = [(last.completion_s - first.completion_s) / 7
                 for first, last in zip(first_paths, final_paths)]
        critical: set[str] = set()
        for index, path in enumerate(final_paths):
            if ttfts[index] < max(ttfts) - 1e-9 and tpots[index] < max(tpots) - 1e-9:
                continue
            for event_name in path.events:
                event = graph.events[event_name]
                if event.resource is not None and event.duration_s > 0:
                    critical.add(event.resource)
        if demand_mode == "ensemble":
            # Traffic may stitch across branches in the exported compatibility
            # graph; flow marginals expose shared downstream GPUs.
            from .path_ensemble import measure as path_ensemble_measure
            ensemble = path_ensemble_measure(self, state)
            demand = {f"gpu:{node}": work for node, work in
                      ensemble.gpu_demand_s.items()}
            demand.update({f"link:{edge}": work for edge, work in
                           ensemble.link_demand_s.items()})
        elif demand_mode == "canonical":
            demand: dict[str, float] = {}
            for stages in pipelines:
                for stage in stages:
                    link_resource = f"link:{stage['incoming_link']}"
                    link_load = (stage["payload_bytes"] /
                                 stage["incoming_bytes_per_s"])
                    demand[link_resource] = demand.get(link_resource, 0.0) + link_load
                    if stage["device"] != "sink":
                        compute_resource = f"gpu:{stage['device']}"
                        service = max(stage["prefill_s"] / self.prompt_tokens,
                                      stage["decode_s"] / self.decode_batch)
                        demand[compute_resource] = (
                            demand.get(compute_resource, 0.0) + service)
        else:
            raise ValueError(f"Unknown demand mode: {demand_mode}")
        bottleneck = max(demand, key=demand.get)
        return GraphMetrics(max(ttfts), max(tpots), demand[bottleneck],
                            frozenset(critical),
                            (max(ttfts[0], ttfts[2]), max(ttfts[1], ttfts[3])),
                            (max(tpots[0], tpots[2]), max(tpots[1], tpots[3])),
                            bottleneck)

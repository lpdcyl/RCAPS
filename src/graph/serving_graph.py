"""Fixed-placement Helix-style logical serving graph construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

import networkx as nx

from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
    GPUNode,
)
from src.utils.config import (
    bandwidth_mbps_to_activation_tokens_per_second,
    bandwidth_mbps_to_tokens_per_second,
)


SOURCE = "source"
SINK = "sink"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Model dimensions and per-layer simulation parameters."""

    name: str
    num_layers: int
    token_bytes: float
    activation_bytes_per_token: float
    layer_compute_units_per_token: tuple[float, ...]
    layer_memory_gb: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.num_layers <= 0:
            raise ValueError("Model num_layers must be positive")
        if self.token_bytes <= 0 or self.activation_bytes_per_token <= 0:
            raise ValueError("Token and activation sizes must be positive")
        if len(self.layer_compute_units_per_token) != self.num_layers:
            raise ValueError("Layer compute profile length must equal num_layers")
        if len(self.layer_memory_gb) != self.num_layers:
            raise ValueError("Layer memory profile length must equal num_layers")
        if any(value <= 0 for value in self.layer_compute_units_per_token):
            raise ValueError("Every layer compute cost must be positive")
        if any(value < 0 for value in self.layer_memory_gb):
            raise ValueError("Layer memory costs cannot be negative")


@dataclass(frozen=True, slots=True)
class LayerInterval:
    """A half-open layer interval ``[start_layer, end_layer)``."""

    start_layer: int
    end_layer: int

    def __post_init__(self) -> None:
        if self.start_layer < 0:
            raise ValueError("start_layer cannot be negative")
        if self.end_layer <= self.start_layer:
            raise ValueError("Layer interval must be non-empty")

    @property
    def layer_count(self) -> int:
        """Return the number of layers in the interval."""

        return self.end_layer - self.start_layer


@dataclass(frozen=True, slots=True)
class LayerPlacement:
    """A fixed mapping from every GPU id to one continuous layer interval."""

    name: str
    intervals: Mapping[str, LayerInterval]

    def validate(self, topology: ClusterTopology, model: ModelProfile) -> None:
        """Validate GPU coverage, model bounds, memory, and full-path possibility."""

        expected = set(topology.gpus)
        actual = set(self.intervals)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(f"Placement GPU mismatch; missing={missing}, extra={extra}")

        for gpu_id, interval in self.intervals.items():
            if interval.end_layer > model.num_layers:
                raise ValueError(
                    f"Placement for {gpu_id} ends beyond layer {model.num_layers}"
                )
            required_memory = sum(
                model.layer_memory_gb[
                    interval.start_layer : interval.end_layer
                ]
            )
            if required_memory > topology.gpus[gpu_id].memory_gb + 1e-12:
                raise ValueError(
                    f"Placement for {gpu_id} requires {required_memory} GB but "
                    f"only {topology.gpus[gpu_id].memory_gb} GB is available"
                )

        if not any(i.start_layer == 0 for i in self.intervals.values()):
            raise ValueError("Placement contains no GPU holding the first layer")
        if not any(i.end_layer == model.num_layers for i in self.intervals.values()):
            raise ValueError("Placement contains no GPU holding the last layer")


class MissingThroughputProfileError(LookupError):
    """Raised when no profiled throughput exists for a GPU type/layer count."""


@runtime_checkable
class ThroughputProvider(Protocol):
    """Compute a GPU's inference throughput for a placed interval."""

    @property
    def description(self) -> str:
        """Human-readable provider description."""

    def throughput(
        self,
        gpu: GPUNode,
        start_layer: int,
        end_layer: int,
        model: ModelProfile,
    ) -> float:
        """Return inference throughput in token/s."""


@dataclass(frozen=True, slots=True)
class AnalyticalThroughputProvider:
    """Simulator analytical approximation; this is not Helix profiling."""

    @property
    def description(self) -> str:
        return "Simulator analytical approximation"

    def throughput(
        self,
        gpu: GPUNode,
        start_layer: int,
        end_layer: int,
        model: ModelProfile,
    ) -> float:
        work = sum(model.layer_compute_units_per_token[start_layer:end_layer])
        if work <= 0:
            raise ValueError("Placed interval must have positive compute work")
        return gpu.effective_compute_units_per_second / work


@dataclass(frozen=True, slots=True)
class ProfiledThroughputProvider:
    """Helix-style lookup of profiled throughput by GPU type and layer count."""

    profiles: Mapping[str, Mapping[int, float]]

    @property
    def description(self) -> str:
        return "Profiled throughput by GPU type and layer count"

    def throughput(
        self,
        gpu: GPUNode,
        start_layer: int,
        end_layer: int,
        model: ModelProfile,
    ) -> float:
        del model
        layer_count = end_layer - start_layer
        try:
            throughput = float(self.profiles[gpu.gpu_type][layer_count])
        except KeyError as exc:
            raise MissingThroughputProfileError(
                f"Missing throughput profile for GPU type {gpu.gpu_type!r} "
                f"with {layer_count} layers"
            ) from exc
        if throughput <= 0:
            raise ValueError("Profiled throughput must be positive")
        return throughput


@dataclass(slots=True)
class ServingGraph:
    """A NetworkX capacity graph produced from a fixed placement."""

    graph: nx.DiGraph
    placement: LayerPlacement
    throughput_model: str


def gpu_in_node(gpu_id: str) -> str:
    return f"{gpu_id}_in"


def gpu_out_node(gpu_id: str) -> str:
    return f"{gpu_id}_out"


def _add_capacity_edge(
    graph: nx.DiGraph,
    source: str,
    target: str,
    capacity: float,
    edge_type: str,
) -> None:
    if capacity <= 0:
        raise ValueError(f"Edge {source}->{target} must have positive capacity")
    graph.add_edge(source, target, capacity=float(capacity), edge_type=edge_type)


def build_serving_graph(
    topology: ClusterTopology,
    model: ModelProfile,
    placement: LayerPlacement,
    throughput_provider: ThroughputProvider,
    *,
    allow_partial_inference: bool = False,
) -> ServingGraph:
    """Construct a strict-boundary logical graph for a fixed placement.

    Phase 1 intentionally supports only ``end_i == start_j``. Partial inference
    belongs to a later phase and is rejected explicitly here.
    """

    if allow_partial_inference:
        raise NotImplementedError("Phase 1 does not implement partial inference")
    placement.validate(topology, model)
    graph = nx.DiGraph()
    graph.add_nodes_from((SOURCE, SINK))

    for gpu_id, gpu in topology.gpus.items():
        interval = placement.intervals[gpu_id]
        compute_capacity = throughput_provider.throughput(
            gpu, interval.start_layer, interval.end_layer, model
        )
        _add_capacity_edge(
            graph,
            gpu_in_node(gpu_id),
            gpu_out_node(gpu_id),
            compute_capacity,
            "compute",
        )

    for link in topology.links:
        if link.source == COORDINATOR_SOURCE:
            interval = placement.intervals.get(link.target)
            if interval is not None and interval.start_layer == 0:
                capacity = bandwidth_mbps_to_tokens_per_second(
                    link.bandwidth_mbps, model.token_bytes
                )
                _add_capacity_edge(
                    graph,
                    SOURCE,
                    gpu_in_node(link.target),
                    capacity,
                    "coordinator_input",
                )
            continue

        if link.target == COORDINATOR_SINK:
            interval = placement.intervals.get(link.source)
            if interval is not None and interval.end_layer == model.num_layers:
                capacity = bandwidth_mbps_to_tokens_per_second(
                    link.bandwidth_mbps, model.token_bytes
                )
                _add_capacity_edge(
                    graph,
                    gpu_out_node(link.source),
                    SINK,
                    capacity,
                    "coordinator_output",
                )
            continue

        source_interval = placement.intervals.get(link.source)
        target_interval = placement.intervals.get(link.target)
        if source_interval is None or target_interval is None:
            continue
        if source_interval.end_layer != target_interval.start_layer:
            continue
        capacity = bandwidth_mbps_to_activation_tokens_per_second(
            link.bandwidth_mbps, model.activation_bytes_per_token
        )
        _add_capacity_edge(
            graph,
            gpu_out_node(link.source),
            gpu_in_node(link.target),
            capacity,
            "network",
        )

    if not nx.has_path(graph, SOURCE, SINK):
        raise ValueError(
            f"Placement {placement.name!r} produces no complete source-to-sink path"
        )
    return ServingGraph(
        graph=graph,
        placement=placement,
        throughput_model=throughput_provider.description,
    )

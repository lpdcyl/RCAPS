"""Physical resources and layer-compatible execution edges, without a score.

The physical graph can contain cycles. A placement's execution graph cannot:
every GPU-to-GPU edge advances the completed model-layer boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any


NodeId = int | str


@dataclass(frozen=True)
class GpuResource:
    kind: str
    capacity_layers: int
    profile: Any = None


@dataclass(frozen=True)
class PhysicalLink:
    latency_s: float
    bandwidth_bytes_per_s: float


@dataclass(frozen=True)
class ResourceGraph:
    gpus: dict[NodeId, GpuResource]
    links: dict[tuple[NodeId, NodeId], PhysicalLink]
    layers: int
    token_bytes: float | None = None
    activation_bytes: float | None = None
    prompt_tokens: int | None = None
    decode_batch: int | None = None

    def link(self, left: NodeId, right: NodeId) -> PhysicalLink:
        try:
            return self.links[left, right]
        except KeyError as error:
            raise ValueError(f"No physical link {left} -> {right}") from error


@lru_cache(maxsize=16)
def from_topology(model) -> ResourceGraph:
    """Copy the placement topology's deterministic hardware/profile data."""
    gpus = {node: GpuResource(kind, model.capacity[node], model.profiles[kind])
            for node, kind in model.types.items()}
    links = {}
    for left in ("source", *gpus):
        for right in (*gpus, "sink"):
            if left == right or left == "source" and right == "sink":
                continue
            if (f"Link-{left}-{right}" not in model.config and
                    f"Link-{right}-{left}" not in model.config):
                continue
            latency, bandwidth = model.link(left, right)
            links[left, right] = PhysicalLink(latency, bandwidth)
    return ResourceGraph(gpus, links, model.layers,
                         model.manager.get_model_token_size(),
                         model.manager.get_model_activation_size(),
                         model.prompt_tokens, model.decode_batch)


@dataclass(frozen=True)
class LayerCompatibilityDag:
    spans: dict[NodeId, tuple[int, int]]
    edges: tuple[tuple[NodeId, NodeId], ...]
    layers: int

    @property
    def edge_set(self) -> frozenset[tuple[NodeId, NodeId]]:
        return frozenset(self.edges)

    def path_count(self) -> int:
        """Count complete routes by layer order without enumerating paths."""
        count: dict[NodeId, int] = {"sink": 1}
        outgoing: dict[NodeId, list[NodeId]] = {}
        for left, right in self.edges:
            outgoing.setdefault(left, []).append(right)
        for node in sorted(self.spans, key=lambda item: self.spans[item][1],
                           reverse=True):
            count[node] = sum(count.get(right, 0)
                              for right in outgoing.get(node, ()))
        return sum(count.get(right, 0) for right in outgoing.get("source", ()))


def layer_dag(resources: ResourceGraph,
              spans: dict[NodeId, tuple[int, int]],
              entries: tuple[NodeId, ...]) -> LayerCompatibilityDag:
    """Construct the exact layer-compatible edges exported to the simulator."""
    for node, (start, end) in spans.items():
        if node not in resources.gpus or not 0 <= start < end <= resources.layers:
            raise ValueError(f"Invalid layer span for GPU {node}")
        if end - start > resources.gpus[node].capacity_layers:
            raise ValueError(f"GPU {node} exceeds its layer capacity")
    edges: list[tuple[NodeId, NodeId]] = []
    for entry in entries:
        if entry not in spans or spans[entry][0] != 0:
            raise ValueError(f"Invalid source entry {entry}")
        resources.link("source", entry)
        edges.append(("source", entry))
    for left, (_, boundary) in spans.items():
        for right, (start, end) in spans.items():
            if (left != right and start <= boundary < end and
                    (left, right) in resources.links):
                edges.append((left, right))
        if boundary == resources.layers and (left, "sink") in resources.links:
            edges.append((left, "sink"))
    dag = LayerCompatibilityDag(dict(spans), tuple(edges), resources.layers)
    if len(dag.edge_set) != len(dag.edges) or dag.path_count() == 0:
        raise ValueError("No unique complete layer-compatible route")
    return dag


def from_simulator(simulator) -> LayerCompatibilityDag:
    """Read M3's deployed layers and physical links through the same builder."""
    spans = {}
    gpus = {}
    for node in simulator.compute_nodes.values():
        loaded = sorted(node.in_vram_model_layers)
        if not loaded:
            continue
        if loaded != list(range(loaded[0], loaded[-1] + 1)):
            raise ValueError(f"Noncontiguous runtime layers on GPU {node.node_uid}")
        spans[node.node_uid] = (loaded[0], loaded[-1] + 1)
        gpus[node.node_uid] = GpuResource(
            node.machine_type,
            simulator.model_manager.get_max_num_layers(node.machine_type))
    links = {(link.node_in.node_uid, link.node_out.node_uid):
             PhysicalLink(link.latency, link.bandwidth)
             for link in simulator.links.values()}
    entries = tuple(node for node, (start, _) in spans.items()
                    if start == 0 and
                    (simulator.source_node.node_uid, node) in links)
    # Runtime UIDs are simulator-local; use the same source/sink symbols as M1.
    normalized_links = {}
    for (left, right), value in links.items():
        source = "source" if left == simulator.source_node.node_uid else left
        sink = "sink" if right == simulator.sink_node.node_uid else right
        normalized_links[source, sink] = value
    resources = ResourceGraph(gpus, normalized_links,
                              simulator.model_manager.get_num_layers())
    return layer_dag(resources, spans, entries)

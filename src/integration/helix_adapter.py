"""Minimal, explicit carbon-to-Helix mapping helpers.

This module is intentionally an adapter, not a scheduler.  It translates
already-computed Helix placement/pipeline objects into the carbon package's
immutable graph types and refuses to invent missing region or capacity data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from src.graph.serving_graph import LayerInterval, LayerPlacement
from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
    GPUNode,
    NetworkLink,
)


class HelixAdapterError(ValueError):
    """Raised when a Helix object cannot be mapped without guessing."""


def default_gpu_id(node_uid: int) -> str:
    """Stable, collision-free carbon id for a Helix compute-node uid."""

    return f"helix-node-{int(node_uid)}"


def layer_intervals_from_helix_nodes(
    compute_nodes: Iterable[Any],
    *,
    gpu_id_for_node: Callable[[Any], str] | None = None,
) -> tuple[dict[str, LayerInterval], dict[int, str]]:
    """Read contiguous loaded-layer intervals from Helix compute nodes."""

    id_fn = gpu_id_for_node or (lambda node: default_gpu_id(node.node_uid))
    intervals: dict[str, LayerInterval] = {}
    node_to_gpu: dict[int, str] = {}
    for node in sorted(compute_nodes, key=lambda item: int(item.node_uid)):
        layers = sorted(int(layer) for layer in getattr(node, "in_vram_model_layers", {}))
        if not layers:
            continue
        expected = list(range(layers[0], layers[-1] + 1))
        if layers != expected:
            raise HelixAdapterError(f"Helix node {node.node_uid} does not hold a contiguous layer interval")
        gpu_id = str(id_fn(node))
        if gpu_id in intervals:
            raise HelixAdapterError(f"duplicate carbon GPU id {gpu_id!r}")
        intervals[gpu_id] = LayerInterval(layers[0], layers[-1] + 1)
        node_to_gpu[int(node.node_uid)] = gpu_id
    if not intervals:
        raise HelixAdapterError("no loaded Helix compute-node layers found")
    return intervals, node_to_gpu


def layer_placement_from_helix(
    compute_nodes: Iterable[Any],
    *,
    name: str = "helix_loaded",
    gpu_id_for_node: Callable[[Any], str] | None = None,
) -> tuple[LayerPlacement, dict[int, str]]:
    """Return a carbon ``LayerPlacement`` plus the Helix node mapping."""

    intervals, node_to_gpu = layer_intervals_from_helix_nodes(
        compute_nodes, gpu_id_for_node=gpu_id_for_node
    )
    return LayerPlacement(name, intervals), node_to_gpu


def topology_from_helix(
    *,
    compute_nodes: Iterable[Any],
    links: Iterable[Any],
    region_by_node_uid: Mapping[int, str],
    effective_compute_units_by_node_uid: Mapping[int, float],
    gpu_id_for_node: Callable[[Any], str] | None = None,
) -> tuple[ClusterTopology, dict[int, str]]:
    """Build carbon topology from explicit Helix metadata.

    Region and effective compute capacity are required because the original
    Helix INI files do not contain carbon regions or the carbon model's compute
    units.  Link bandwidth is converted from Helix bytes/second to Mbps.
    """

    nodes = sorted(list(compute_nodes), key=lambda item: int(item.node_uid))
    id_fn = gpu_id_for_node or (lambda node: default_gpu_id(node.node_uid))
    node_to_gpu: dict[int, str] = {}
    gpus: list[GPUNode] = []
    for node in nodes:
        uid = int(node.node_uid)
        if uid not in region_by_node_uid or uid not in effective_compute_units_by_node_uid:
            raise HelixAdapterError(f"missing explicit carbon metadata for Helix node {uid}")
        gpu_id = str(id_fn(node))
        node_to_gpu[uid] = gpu_id
        gpus.append(
            GPUNode(
                gpu_id=gpu_id,
                region=str(region_by_node_uid[uid]),
                gpu_type=str(node.machine_type),
                memory_gb=float(node.vram_size) / 1_000_000_000,
                effective_compute_units_per_second=float(effective_compute_units_by_node_uid[uid]),
            )
        )

    def endpoint(node: Any) -> str:
        uid = int(node.node_uid)
        if getattr(node, "node_type", None).name == "Source":
            return COORDINATOR_SOURCE
        if getattr(node, "node_type", None).name == "Sink":
            return COORDINATOR_SINK
        if uid not in node_to_gpu:
            raise HelixAdapterError(f"link references unknown Helix node {uid}")
        return node_to_gpu[uid]

    carbon_links = []
    for link in links:
        # Helix stores bandwidth in bytes/second; carbon topology uses Mbps.
        bandwidth_mbps = float(link.bandwidth) * 8.0 / 1_000_000.0
        carbon_links.append(NetworkLink(endpoint(link.node_in), endpoint(link.node_out), bandwidth_mbps))
    return ClusterTopology.from_iterables(gpus, carbon_links), node_to_gpu


@dataclass(frozen=True, slots=True)
class RouteMapping:
    """A request's explicit Helix pipeline represented by stable ids."""

    link_uids: tuple[int, ...]
    node_uids: tuple[int, ...]
    layer_intervals: tuple[LayerInterval | None, ...]


def route_from_helix_pipeline(pipeline: Iterable[Any]) -> RouteMapping:
    """Extract link/node/layer mapping from ``PipelineStage`` objects."""

    stages = list(pipeline)
    if not stages:
        raise HelixAdapterError("Helix pipeline is empty")
    link_uids: list[int] = []
    node_uids: list[int] = []
    intervals: list[LayerInterval | None] = []
    for stage in stages:
        link_uids.append(int(stage.link_uid))
        node_uids.append(int(stage.node_uid))
        layers = getattr(stage, "layers_to_infer", None)
        if layers is None:
            intervals.append(None)
            continue
        layer_ids = sorted(int(layer) for layer in layers)
        if not layer_ids or layer_ids != list(range(layer_ids[0], layer_ids[-1] + 1)):
            raise HelixAdapterError("Helix pipeline stage layers are not contiguous")
        intervals.append(LayerInterval(layer_ids[0], layer_ids[-1] + 1))
    return RouteMapping(tuple(link_uids), tuple(node_uids), tuple(intervals))


def helix_node_uids_for_placement(
    placement: LayerPlacement, node_to_gpu: Mapping[int, str]
) -> dict[int, LayerInterval]:
    """Invert a carbon placement back to Helix node uids without guessing."""

    result: dict[int, LayerInterval] = {}
    for node_uid, gpu_id in sorted(node_to_gpu.items()):
        if gpu_id in placement.intervals:
            result[int(node_uid)] = placement.intervals[gpu_id]
    if not result:
        raise HelixAdapterError("placement contains none of the mapped Helix nodes")
    return result

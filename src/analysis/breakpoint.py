"""Deterministic signatures and adjacent-point breakpoint detection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Sequence

from src.graph.serving_graph import LayerPlacement, ServingGraph


PlacementSignature = tuple[tuple[str, int, int], ...]


@dataclass(frozen=True, slots=True)
class RoutingBreakpoint:
    """An interval whose fixed-placement route changes materially."""

    left_ci_ratio: float
    right_ci_ratio: float
    placement: PlacementSignature
    flow_l1_change: float


@dataclass(frozen=True, slots=True)
class PlacementBreakpoint:
    """An interval whose carbon-optimal placement changes."""

    left_ci_ratio: float
    right_ci_ratio: float
    old_placement: PlacementSignature
    new_placement: PlacementSignature
    migration_layer_count: int
    graph_edge_change: float


def placement_signature(placement: LayerPlacement) -> PlacementSignature:
    """Return a stable placement signature ordered by GPU id."""

    return tuple(
        (gpu_id, interval.start_layer, interval.end_layer)
        for gpu_id, interval in sorted(placement.intervals.items())
    )


def serialize_placement_signature(signature: PlacementSignature) -> str:
    """Serialize a placement signature as parseable compact JSON."""

    return json.dumps(signature, separators=(",", ":"))


def logical_edge_set(serving_graph: ServingGraph) -> frozenset[tuple[str, str, str]]:
    """Return non-compute logical edges used to compare serving graphs."""

    return frozenset(
        (source, target, str(data["edge_type"]))
        for source, target, data in serving_graph.graph.edges(data=True)
        if data["edge_type"] != "compute"
    )


def graph_change(
    old_edges: frozenset[tuple[str, str, str]],
    new_edges: frozenset[tuple[str, str, str]],
) -> float:
    """Return one minus Jaccard similarity for two logical edge sets."""

    union = old_edges | new_edges
    if not union:
        return 0.0
    return 1.0 - len(old_edges & new_edges) / len(union)


def migration_layer_count(
    old: PlacementSignature, new: PlacementSignature
) -> int:
    """Count per-GPU layer membership changes between two placements."""

    old_map = {gpu_id: set(range(start, end)) for gpu_id, start, end in old}
    new_map = {gpu_id: set(range(start, end)) for gpu_id, start, end in new}
    return sum(
        len(old_map.get(gpu_id, set()) ^ new_map.get(gpu_id, set()))
        for gpu_id in old_map.keys() | new_map.keys()
    )


def _flow_l1_change(
    left: Mapping[str, float], right: Mapping[str, float]
) -> float:
    return sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in left.keys() | right.keys())


def detect_routing_breakpoints(
    ci_ratios: Sequence[float],
    placements: Sequence[PlacementSignature],
    flow_vectors: Sequence[Mapping[str, float]],
    *,
    tolerance: float = 1e-6,
) -> tuple[RoutingBreakpoint, ...]:
    """Detect adjacent fixed-placement path-flow changes above tolerance."""

    if not (len(ci_ratios) == len(placements) == len(flow_vectors)):
        raise ValueError("Routing breakpoint inputs must have equal lengths")
    points: list[RoutingBreakpoint] = []
    for index in range(1, len(ci_ratios)):
        if placements[index - 1] != placements[index]:
            continue
        change = _flow_l1_change(flow_vectors[index - 1], flow_vectors[index])
        if change > tolerance:
            points.append(
                RoutingBreakpoint(
                    float(ci_ratios[index - 1]),
                    float(ci_ratios[index]),
                    placements[index],
                    change,
                )
            )
    return tuple(points)


def detect_placement_breakpoints(
    ci_ratios: Sequence[float],
    placements: Sequence[PlacementSignature],
    edge_sets: Sequence[frozenset[tuple[str, str, str]]] | None = None,
) -> tuple[PlacementBreakpoint, ...]:
    """Detect adjacent canonical placement transitions."""

    if len(ci_ratios) != len(placements):
        raise ValueError("Placement breakpoint inputs must have equal lengths")
    if edge_sets is not None and len(edge_sets) != len(placements):
        raise ValueError("edge_sets must align with placements")
    points: list[PlacementBreakpoint] = []
    for index in range(1, len(ci_ratios)):
        old = placements[index - 1]
        new = placements[index]
        if old == new:
            continue
        edge_delta = (
            0.0
            if edge_sets is None
            else graph_change(edge_sets[index - 1], edge_sets[index])
        )
        points.append(
            PlacementBreakpoint(
                float(ci_ratios[index - 1]),
                float(ci_ratios[index]),
                old,
                new,
                migration_layer_count(old, new),
                edge_delta,
            )
        )
    return tuple(points)

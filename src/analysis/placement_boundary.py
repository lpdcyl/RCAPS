"""Cost-curve validation for apparent carbon-placement transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.analysis.breakpoint import PlacementBreakpoint, PlacementSignature
from src.graph.serving_graph import LayerInterval, LayerPlacement


PlacementCostEvaluator = Callable[[LayerPlacement, float], float]


@dataclass(frozen=True, slots=True)
class ValidatedPlacementBoundary:
    """Three-point fixed-placement comparison around one signature switch."""

    left_ci_ratio: float
    mid_ci_ratio: float
    right_ci_ratio: float
    old_placement: PlacementSignature
    new_placement: PlacementSignature
    old_cost_left: float
    new_cost_left: float
    old_cost_mid: float
    new_cost_mid: float
    old_cost_right: float
    new_cost_right: float
    delta_left: float
    delta_mid: float
    delta_right: float
    cost_crossing: bool
    degenerate: bool
    migration_layer_count: int
    graph_edge_change: float

    @property
    def validated(self) -> bool:
        """A scientific boundary must cross and be materially separated."""

        return self.cost_crossing and not self.degenerate


def placement_from_signature(
    signature: PlacementSignature, *, name: str = "candidate"
) -> LayerPlacement:
    """Reconstruct a fixed placement from its stable signature."""

    return LayerPlacement(
        name,
        {
            gpu_id: LayerInterval(start_layer, end_layer)
            for gpu_id, start_layer, end_layer in signature
        },
    )


def _relative_difference(old_cost: float, new_cost: float) -> float:
    scale = max(abs(old_cost), abs(new_cost), 1e-30)
    return abs(old_cost - new_cost) / scale


def validate_placement_boundary(
    transition: PlacementBreakpoint,
    evaluate_cost: PlacementCostEvaluator,
    *,
    degeneracy_tolerance: float = 1e-4,
) -> ValidatedPlacementBoundary:
    """Evaluate both fixed placements at the left, midpoint, and right CI.

    ``evaluate_cost`` receives a reconstructed placement and a CI ratio.  A
    signature switch is material only when the signed fixed-placement cost
    difference crosses zero and the two endpoint separations are not both
    below ``degeneracy_tolerance``.
    """

    if degeneracy_tolerance < 0:
        raise ValueError("degeneracy_tolerance must be non-negative")
    left = float(transition.left_ci_ratio)
    right = float(transition.right_ci_ratio)
    if right <= left:
        raise ValueError("Boundary CI ratios must be strictly increasing")
    mid = (left + right) / 2.0
    old = placement_from_signature(transition.old_placement, name="old")
    new = placement_from_signature(transition.new_placement, name="new")
    old_left = float(evaluate_cost(old, left))
    new_left = float(evaluate_cost(new, left))
    old_mid = float(evaluate_cost(old, mid))
    new_mid = float(evaluate_cost(new, mid))
    old_right = float(evaluate_cost(old, right))
    new_right = float(evaluate_cost(new, right))
    delta_left = old_left - new_left
    delta_mid = old_mid - new_mid
    delta_right = old_right - new_right
    crossing = delta_left * delta_right < 0.0
    degenerate = (
        _relative_difference(old_left, new_left) < degeneracy_tolerance
        and _relative_difference(old_right, new_right) < degeneracy_tolerance
    )
    return ValidatedPlacementBoundary(
        left,
        mid,
        right,
        transition.old_placement,
        transition.new_placement,
        old_left,
        new_left,
        old_mid,
        new_mid,
        old_right,
        new_right,
        delta_left,
        delta_mid,
        delta_right,
        crossing,
        degenerate,
        transition.migration_layer_count,
        transition.graph_edge_change,
    )

"""Operational definition of routing sufficiency."""

from __future__ import annotations


def routing_gap(
    routing_carbon: float,
    joint_carbon: float,
    *,
    tolerance: float = 1e-10,
) -> float:
    """Return the relative carbon benefit of joint placement over routing."""

    if routing_carbon <= 0:
        raise ValueError("routing_carbon must be positive")
    if joint_carbon < 0:
        raise ValueError("joint_carbon cannot be negative")
    gap = (routing_carbon - joint_carbon) / routing_carbon
    if gap < -tolerance:
        raise ValueError(
            "Joint placement carbon cannot exceed routing-only carbon: "
            f"routing={routing_carbon}, joint={joint_carbon}"
        )
    return max(0.0, gap)


def is_routing_sufficient(gap: float, epsilon: float) -> bool:
    """Return whether a routing gap falls within the configured tolerance."""

    if gap < 0:
        raise ValueError("routing gap cannot be negative")
    if not 0 <= epsilon < 1:
        raise ValueError("epsilon must be in [0, 1)")
    return gap <= epsilon

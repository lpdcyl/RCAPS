import pytest

from src.analysis.routing_gap import is_routing_sufficient, routing_gap


def test_routing_gap_and_threshold() -> None:
    gap = routing_gap(100.0, 96.0)
    assert gap == pytest.approx(0.04)
    assert not is_routing_sufficient(gap, 0.03)
    assert is_routing_sufficient(gap, 0.05)


def test_joint_carbon_cannot_be_materially_worse() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        routing_gap(100.0, 101.0)

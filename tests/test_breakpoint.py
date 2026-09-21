from src.analysis.breakpoint import (
    detect_placement_breakpoints,
    detect_routing_breakpoints,
)


def _signature(label: str):
    offset = {"A": 0, "B": 1, "C": 2}[label]
    return (("g1", offset, offset + 1),)


def test_detects_two_placement_breakpoints() -> None:
    placements = [_signature(label) for label in "AAABBC"]
    points = detect_placement_breakpoints([1, 2, 3, 4, 5, 6], placements)
    assert [(point.left_ci_ratio, point.right_ci_ratio) for point in points] == [
        (3.0, 4.0),
        (5.0, 6.0),
    ]


def test_routing_breakpoint_ignores_numerical_noise() -> None:
    placement = _signature("A")
    points = detect_routing_breakpoints(
        [1.0, 2.0, 3.0],
        [placement] * 3,
        [{"p1": 1.0}, {"p1": 1.0 - 1e-9}, {"p1": 0.5, "p2": 0.5}],
        tolerance=1e-6,
    )
    assert len(points) == 1
    assert points[0].left_ci_ratio == 2.0
    assert points[0].right_ci_ratio == 3.0

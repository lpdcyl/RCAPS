"""Register one primary method and any number of baseline adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from baselines import helix
from rcaps import method as rcaps_v1
from rcaps import v2_method


@dataclass(frozen=True)
class MethodSpec:
    name: str
    description: str
    role: str
    layout: Callable[[str, Path], tuple[Path, Path]]
    evaluate: Callable[[str, float, int, int, int, Path, Path], dict]


MAIN_METHOD = v2_method.NAME
METHODS = {
    MAIN_METHOD: MethodSpec(
        MAIN_METHOD, "V2 adaptive shared-stem and replicated-suffix placement",
        "main", lambda scenario, root: v2_method.layout(MAIN_METHOD, scenario, root),
        v2_method.evaluate),
    helix.NAME: MethodSpec(helix.NAME, helix.DESCRIPTION, "baseline",
                           helix.layout, helix.evaluate),
    rcaps_v1.NAME: MethodSpec(
        rcaps_v1.NAME, rcaps_v1.DESCRIPTION, "comparison",
        rcaps_v1.layout, rcaps_v1.evaluate),
    "rcaps_v2_fixed_structure": MethodSpec(
        "rcaps_v2_fixed_structure",
        "V2 search constrained to a one-GPU stem and two suffixes", "ablation",
        lambda scenario, root: v2_method.layout(
            "rcaps_v2_fixed_structure", scenario, root),
        v2_method.evaluate),
}

DEFAULT_METHODS = [name for name, spec in METHODS.items()
                   if spec.role in ("main", "baseline")]


def register_baseline(spec: MethodSpec) -> None:
    """Add a baseline adapter without changing the benchmark runner."""
    if spec.role != "baseline" or spec.name in METHODS:
        raise ValueError(f"Invalid or duplicate baseline: {spec.name}")
    METHODS[spec.name] = spec

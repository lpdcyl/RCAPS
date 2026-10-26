"""Register RCAPS V3 as the research method and external serving baselines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from baselines import helix, separate, swarm
from rcaps import v3_method, v4_method


@dataclass(frozen=True)
class MethodSpec:
    name: str
    description: str
    role: str
    layout: Callable[[str, Path], tuple[Path, Path]]
    evaluate: Callable[[str, float, int, int, int, Path, Path], dict]


MAIN_METHOD = v4_method.NAME
METHODS = {
    MAIN_METHOD: MethodSpec(
        MAIN_METHOD, v4_method.DESCRIPTION, "main", v4_method.layout,
        v4_method.evaluate),
    v3_method.NAME: MethodSpec(v3_method.NAME, v3_method.DESCRIPTION, "baseline",
                             v3_method.layout, v3_method.evaluate),
    helix.NAME: MethodSpec(helix.NAME, helix.DESCRIPTION, "baseline",
                           helix.layout, helix.evaluate),
    swarm.NAME: MethodSpec(swarm.NAME, swarm.DESCRIPTION, "comparison",
                           swarm.layout, swarm.evaluate),
    separate.NAME: MethodSpec(separate.NAME, separate.DESCRIPTION, "comparison",
                              separate.layout, separate.evaluate),
}

DEFAULT_METHODS = [MAIN_METHOD, helix.NAME]


def register_baseline(spec: MethodSpec) -> None:
    """Add an external baseline without changing the V3 benchmark runner."""
    if spec.role != "baseline" or spec.name in METHODS:
        raise ValueError(f"Invalid or duplicate baseline: {spec.name}")
    METHODS[spec.name] = spec

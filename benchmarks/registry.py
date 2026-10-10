"""Register one primary method and any number of baseline adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from baselines import helix
from rcaps import ablations
from rcaps import method as rcaps


@dataclass(frozen=True)
class MethodSpec:
    name: str
    description: str
    role: str
    layout: Callable[[str, Path], tuple[Path, Path]]
    evaluate: Callable[[str, float, int, int, int, Path, Path], dict]


MAIN_METHOD = rcaps.NAME
METHODS = {
    rcaps.NAME: MethodSpec(rcaps.NAME, rcaps.DESCRIPTION, "main",
                           rcaps.layout, rcaps.evaluate),
    helix.NAME: MethodSpec(helix.NAME, helix.DESCRIPTION, "baseline",
                           helix.layout, helix.evaluate),
}
for name in (*ablations.SCHEDULERS, *ablations.LAYOUT_VARIANTS):
    kind = "scheduling" if name in ablations.SCHEDULERS else "placement"
    METHODS[name] = MethodSpec(
        name, f"RCAPS {kind} ablation: {name}", "ablation",
        lambda scenario, root, _name=name:
            ablations.variant_layout(_name, scenario, root),
        lambda scenario, offered, duration, warmup, seed, solution, cluster,
        _name=name: ablations.evaluate(_name, scenario, offered, duration,
                                        warmup, seed, solution, cluster),
    )

DEFAULT_METHODS = [name for name, spec in METHODS.items()
                   if spec.role in ("main", "baseline")]


def register_baseline(spec: MethodSpec) -> None:
    """Add a baseline adapter without changing the benchmark runner."""
    if spec.role != "baseline" or spec.name in METHODS:
        raise ValueError(f"Invalid or duplicate baseline: {spec.name}")
    METHODS[spec.name] = spec

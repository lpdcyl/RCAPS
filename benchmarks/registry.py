"""Register one primary method and any number of baseline adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from baselines import helix, separate, swarm
from rcaps import method as rcaps_v1
from rcaps import v2_method, v3_method
from experiments.v2_method_ablation import adapters as v2_ablation
from experiments.v2_core_ablations import adapters as v2_core
from experiments.v2_method_comparisons import adapters as v2_comparisons


@dataclass(frozen=True)
class MethodSpec:
    name: str
    description: str
    role: str
    layout: Callable[[str, Path], tuple[Path, Path]]
    evaluate: Callable[[str, float, int, int, int, Path, Path], dict]


MAIN_METHOD = v3_method.NAME
METHODS = {
    MAIN_METHOD: MethodSpec(
        MAIN_METHOD, v3_method.DESCRIPTION, "main", v3_method.layout,
        v3_method.evaluate),
    helix.NAME: MethodSpec(helix.NAME, helix.DESCRIPTION, "baseline",
                           helix.layout, helix.evaluate),
    swarm.NAME: MethodSpec(swarm.NAME, swarm.DESCRIPTION, "comparison",
                          swarm.layout, swarm.evaluate),
    separate.NAME: MethodSpec(separate.NAME, separate.DESCRIPTION, "comparison",
                             separate.layout, separate.evaluate),
    rcaps_v1.NAME: MethodSpec(
        rcaps_v1.NAME, rcaps_v1.DESCRIPTION, "comparison",
        rcaps_v1.layout, rcaps_v1.evaluate),
    v2_method.NAME: MethodSpec(
        v2_method.NAME, "Frozen V2 event-DAG placement and queue-aware routing",
        "comparison",
        lambda scenario, root: v2_method.layout(v2_method.NAME, scenario, root),
        v2_method.evaluate),
    "rcaps_v2_fixed_structure": MethodSpec(
        "rcaps_v2_fixed_structure",
        "V2 search constrained to a one-GPU stem and two suffixes", "ablation",
        lambda scenario, root: v2_method.layout(
            "rcaps_v2_fixed_structure", scenario, root),
        v2_method.evaluate),
    v2_ablation.NAME_CAPACITY: MethodSpec(
        v2_ablation.NAME_CAPACITY,
        "V2 adaptive structure selected with capacity and connectivity only",
        "ablation", v2_ablation.capacity_layout,
        v2_ablation.evaluate_capacity),
    v2_ablation.NAME_STATIC: MethodSpec(
        v2_ablation.NAME_STATIC,
        "V2 placement with static legal-path rotation and serial transfers",
        "ablation", v2_ablation.static_layout,
        v2_ablation.evaluate_static),
    v2_ablation.NAME_BASE: MethodSpec(
        v2_ablation.NAME_BASE,
        "Capacity-only fixed structure with capacity-safe static legal paths",
        "ablation", v2_ablation.base_layout,
        v2_ablation.evaluate_safe_static),
    v2_ablation.NAME_A: MethodSpec(
        v2_ablation.NAME_A,
        "Resource-aware fixed V2 structure with capacity-safe static legal paths",
        "ablation", v2_ablation.fixed_static_layout,
        v2_ablation.evaluate_safe_static),
    v2_ablation.NAME_AB: MethodSpec(
        v2_ablation.NAME_AB,
        "Adaptive V2 layout with capacity-safe static legal paths",
        "ablation", v2_ablation.adaptive_safe_static_layout,
        v2_ablation.evaluate_safe_static),
    **{
        name: MethodSpec(
            name, f"V2 common candidate pool selected by {evaluator}", "ablation",
            lambda scenario, root, method=name: v2_core.modeling_layout(method, scenario, root),
            v2_core.evaluate)
        for name, evaluator in v2_core.MODEL_METHODS.items()
    },
    v2_core.FIXED_BRANCHES: MethodSpec(
        v2_core.FIXED_BRANCHES, "V2 event-DAG search constrained to two suffixes",
        "ablation", v2_core.fixed_branches_layout, v2_core.evaluate),
    v2_core.STATIC_DAG: MethodSpec(
        v2_core.STATIC_DAG, "Static-cost legal DAG routing with V2 transfer batching",
        "ablation", v2_core.v2_layout, v2_core.evaluate_static_dag),
    v2_core.QUEUE_DAG: MethodSpec(
        v2_core.QUEUE_DAG, "Queue-only legal DAG routing with V2 transfer batching",
        "ablation", v2_core.v2_layout, v2_core.evaluate_queue_dag),
    v2_comparisons.STATIC_RESOURCE: MethodSpec(
        v2_comparisons.STATIC_RESOURCE,
        "Complete static heterogeneous resource model with V2 adaptive search",
        "ablation", v2_comparisons.static_resource_layout,
        v2_comparisons.evaluate_placement),
    v2_comparisons.BEAM_SEARCH: MethodSpec(
        v2_comparisons.BEAM_SEARCH,
        "Bounded beam placement using the full V2 event-DAG evaluator",
        "ablation", v2_comparisons.beam_layout,
        v2_comparisons.evaluate_placement),
    v2_comparisons.LIVE_PIPELINE: MethodSpec(
        v2_comparisons.LIVE_PIPELINE,
        "Live workload-aware complete-pipeline routing with serial transfers",
        "ablation", v2_comparisons.v2_layout,
        v2_comparisons.evaluate_pipeline),
}

DEFAULT_METHODS = [name for name, spec in METHODS.items()
                   if spec.role in ("main", "baseline")]


def register_baseline(spec: MethodSpec) -> None:
    """Add a baseline adapter without changing the benchmark runner."""
    if spec.role != "baseline" or spec.name in METHODS:
        raise ValueError(f"Invalid or duplicate baseline: {spec.name}")
    METHODS[spec.name] = spec

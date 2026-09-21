"""Carbon-Bottleneck-Guided Placement (CBGP) local boundary search."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

from src.analysis.breakpoint import PlacementSignature, placement_signature
from src.analysis.carbon_bottleneck import (
    CarbonBottleneckReport,
    analyze_carbon_bottlenecks,
)
from src.carbon.config import CBGPConfig
from src.carbon.model import (
    CarbonCostModel,
    CarbonIntensityInput,
    EnergyProvider,
    resolve_ci_snapshot,
)
from src.graph.serving_graph import (
    LayerInterval,
    LayerPlacement,
    MissingThroughputProfileError,
    ModelProfile,
    ThroughputProvider,
    build_serving_graph,
)
from src.graph.topology import ClusterTopology
from src.optimizer.carbon_flow import CarbonFlowResult, solve_carbon_aware_flow
from src.optimizer.maxflow import solve_max_flow


@dataclass(frozen=True, slots=True)
class CBGPIteration:
    """Diagnostics for one deterministic local-search iteration."""

    index: int
    bottleneck_report: CarbonBottleneckReport
    generated_candidates: int
    feasible_candidates: int
    evaluated_candidates: int
    equivalent_candidates: int
    best_relative_improvement: float
    accepted_placement_signature: PlacementSignature | None


@dataclass(frozen=True, slots=True)
class CBGPResult:
    """Validated result and search-efficiency diagnostics for CBGP."""

    initial_placement: LayerPlacement
    placement: LayerPlacement
    initial_flow: CarbonFlowResult
    flow: CarbonFlowResult
    iterations: tuple[CBGPIteration, ...]
    candidate_count: int
    feasible_candidate_count: int
    optimization_calls: int
    runtime_seconds: float
    placement_changed: bool
    termination_reason: str
    visited_placement_count: int


@dataclass(frozen=True, slots=True)
class _CandidateEvaluation:
    placement: LayerPlacement
    flow: CarbonFlowResult


def _candidate_directions(preferred_recipient: str | None, source: str) -> tuple[int, int]:
    if preferred_recipient == source:
        return (1, -1)
    if preferred_recipient is not None:
        return (-1, 1)
    return (-1, 1)


def generate_local_boundary_candidates(
    placement: LayerPlacement,
    report: CarbonBottleneckReport,
    topology: ClusterTopology,
    model: ModelProfile,
    *,
    max_boundary_shift: int,
    throughput_provider: ThroughputProvider | None = None,
    bottleneck_guided: bool = True,
    visited_signatures: Iterable[PlacementSignature] = (),
) -> tuple[LayerPlacement, ...]:
    """Generate memory-valid pair and coordinated-cut boundary shifts."""

    if max_boundary_shift <= 0:
        raise ValueError("max_boundary_shift must be positive")
    visited = set(visited_signatures)
    candidates: dict[PlacementSignature, LayerPlacement] = {}
    signals = tuple(
        value
        for value in report.boundary_signals
        if value.bottleneck_relevant or not bottleneck_guided
    )

    def add_candidate(
        intervals: dict[str, LayerInterval],
        name: str,
        changed_gpu_ids: Iterable[str],
    ) -> None:
        candidate = LayerPlacement(name, intervals)
        try:
            candidate.validate(topology, model)
            if throughput_provider is not None:
                for gpu_id in sorted(set(changed_gpu_ids)):
                    interval = intervals[gpu_id]
                    throughput_provider.throughput(
                        topology.gpus[gpu_id],
                        interval.start_layer,
                        interval.end_layer,
                        model,
                    )
        except (ValueError, MissingThroughputProfileError):
            return
        signature = placement_signature(candidate)
        if signature in visited or signature in candidates:
            return
        candidates[signature] = candidate

    # A single pair move can temporarily destroy parallel paths.  Moving every
    # interval that shares one active layer cut preserves the cut structure
    # while remaining a one-boundary local operation.
    for old_boundary in sorted({value.boundary_layer for value in signals}):
        sources = sorted(
            gpu_id
            for gpu_id, interval in placement.intervals.items()
            if interval.end_layer == old_boundary
        )
        targets = sorted(
            gpu_id
            for gpu_id, interval in placement.intervals.items()
            if interval.start_layer == old_boundary
        )
        changed = (*sources, *targets)
        for direction in (-1, 1):
            for distance in range(1, max_boundary_shift + 1):
                boundary = old_boundary + direction * distance
                if any(
                    placement.intervals[gpu_id].start_layer >= boundary
                    for gpu_id in sources
                ) or any(
                    boundary >= placement.intervals[gpu_id].end_layer
                    for gpu_id in targets
                ):
                    continue
                intervals = dict(placement.intervals)
                for gpu_id in sources:
                    interval = intervals[gpu_id]
                    intervals[gpu_id] = LayerInterval(
                        interval.start_layer, boundary
                    )
                for gpu_id in targets:
                    interval = intervals[gpu_id]
                    intervals[gpu_id] = LayerInterval(
                        boundary, interval.end_layer
                    )
                add_candidate(
                    intervals,
                    f"{placement.name}_cbgp_cut_{old_boundary}_{boundary}",
                    changed,
                )

    for signal in signals:
        source = signal.source_gpu_id
        target = signal.target_gpu_id
        source_interval = placement.intervals[source]
        target_interval = placement.intervals[target]
        for direction in _candidate_directions(
            signal.preferred_recipient_gpu_id, source
        ):
            for distance in range(1, max_boundary_shift + 1):
                boundary = signal.boundary_layer + direction * distance
                if not (
                    source_interval.start_layer < boundary
                    < target_interval.end_layer
                ):
                    continue
                intervals = dict(placement.intervals)
                intervals[source] = LayerInterval(
                    source_interval.start_layer, boundary
                )
                intervals[target] = LayerInterval(
                    boundary, target_interval.end_layer
                )
                add_candidate(
                    intervals,
                    f"{placement.name}_cbgp_{source}_{target}_{boundary}",
                    (source, target),
                )
    return tuple(candidates.values())


def solve_cbgp(
    topology: ClusterTopology,
    model: ModelProfile,
    throughput_provider: ThroughputProvider,
    energy_provider: EnergyProvider,
    carbon_intensity_by_region: CarbonIntensityInput,
    initial_placement: LayerPlacement,
    throughput_target: float,
    config: CBGPConfig,
    *,
    phase: str,
    batch_size: int,
    timestamp: float | None = None,
    bottleneck_guided: bool = True,
) -> CBGPResult:
    """Run deterministic greedy CBGP using one frozen CI snapshot."""

    if throughput_target <= 0.0:
        raise ValueError("throughput_target must be positive")
    start = perf_counter()
    ci_snapshot = resolve_ci_snapshot(
        carbon_intensity_by_region,
        (gpu.region for gpu in topology.gpus.values()),
        timestamp,
    )

    def evaluate(placement: LayerPlacement, *, check_feasibility: bool) -> _CandidateEvaluation | None:
        try:
            serving = build_serving_graph(
                topology, model, placement, throughput_provider
            )
        except (ValueError, MissingThroughputProfileError):
            return None
        if check_feasibility:
            maximum = solve_max_flow(serving, tolerance=config.solver_tolerance)
            if maximum.max_flow_value + config.solver_tolerance < throughput_target:
                return None
        carbon_model = CarbonCostModel.build(
            topology,
            model,
            placement,
            energy_provider,
            ci_snapshot,
            phase=phase,
            batch_size=batch_size,
        )
        flow = solve_carbon_aware_flow(
            serving,
            carbon_model,
            throughput_target,
            tolerance=config.solver_tolerance,
        )
        return _CandidateEvaluation(placement, flow)

    initial = evaluate(initial_placement, check_feasibility=True)
    if initial is None:
        raise ValueError("Initial placement cannot meet the throughput target")
    current = initial
    optimization_calls = 1
    total_candidates = 0
    total_feasible = 0
    visited = {placement_signature(initial_placement)}
    iteration_records: list[CBGPIteration] = []
    termination_reason = "max_iterations"

    for iteration_index in range(1, config.max_iterations + 1):
        serving = build_serving_graph(
            topology, model, current.placement, throughput_provider
        )
        carbon_model = CarbonCostModel.build(
            topology,
            model,
            current.placement,
            energy_provider,
            ci_snapshot,
            phase=phase,
            batch_size=batch_size,
        )
        report = analyze_carbon_bottlenecks(
            serving,
            carbon_model,
            current.flow,
            utilization_threshold=config.bottleneck_utilization_threshold,
            tolerance=config.solver_tolerance,
        )
        candidates = generate_local_boundary_candidates(
            current.placement,
            report,
            topology,
            model,
            max_boundary_shift=config.max_boundary_shift,
            throughput_provider=throughput_provider,
            bottleneck_guided=bottleneck_guided,
            visited_signatures=visited,
        )
        total_candidates += len(candidates)
        if not candidates:
            iteration_records.append(
                CBGPIteration(
                    iteration_index,
                    report,
                    0,
                    0,
                    0,
                    0,
                    0.0,
                    None,
                )
            )
            termination_reason = "no_unvisited_candidates"
            break

        evaluations: list[_CandidateEvaluation] = []
        equivalent = 0
        current_carbon = current.flow.metrics.carbon_g_per_second
        for candidate in candidates:
            evaluated = evaluate(candidate, check_feasibility=True)
            if evaluated is None:
                continue
            total_feasible += 1
            optimization_calls += 1
            evaluations.append(evaluated)
            if (
                abs(evaluated.flow.metrics.carbon_g_per_second - current_carbon)
                <= config.solver_tolerance
            ):
                equivalent += 1

        if not evaluations:
            iteration_records.append(
                CBGPIteration(
                    iteration_index,
                    report,
                    len(candidates),
                    0,
                    0,
                    0,
                    0.0,
                    None,
                )
            )
            termination_reason = "no_throughput_feasible_candidates"
            break

        best = min(
            evaluations,
            key=lambda value: (
                value.flow.metrics.carbon_g_per_second,
                placement_signature(value.placement),
            ),
        )
        absolute_improvement = (
            current_carbon - best.flow.metrics.carbon_g_per_second
        )
        relative_improvement = (
            absolute_improvement / current_carbon
            if current_carbon > config.solver_tolerance
            else 0.0
        )
        accept = (
            absolute_improvement > config.solver_tolerance
            and relative_improvement >= config.min_relative_improvement
        )
        accepted_signature = placement_signature(best.placement) if accept else None
        iteration_records.append(
            CBGPIteration(
                iteration_index,
                report,
                len(candidates),
                len(evaluations),
                len(evaluations),
                equivalent,
                relative_improvement,
                accepted_signature,
            )
        )
        if not accept:
            termination_reason = "improvement_below_threshold"
            break
        current = best
        visited.add(accepted_signature)

    runtime = perf_counter() - start
    return CBGPResult(
        initial_placement=initial_placement,
        placement=current.placement,
        initial_flow=initial.flow,
        flow=current.flow,
        iterations=tuple(iteration_records),
        candidate_count=total_candidates,
        feasible_candidate_count=total_feasible,
        optimization_calls=optimization_calls,
        runtime_seconds=runtime,
        placement_changed=(
            placement_signature(current.placement)
            != placement_signature(initial_placement)
        ),
        termination_reason=termination_reason,
        visited_placement_count=len(visited),
    )

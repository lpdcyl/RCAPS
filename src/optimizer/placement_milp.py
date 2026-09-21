"""MILP optimizers for strict-boundary Helix-style layer placement."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter
from typing import Mapping

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, OptimizeResult, milp
from scipy.sparse import coo_matrix

from src.carbon.model import (
    CarbonCostModel,
    CarbonIntensityInput,
    EnergyProvider,
    operational_carbon_g,
    resolve_ci_snapshot,
)
from src.graph.serving_graph import (
    AnalyticalThroughputProvider,
    LayerInterval,
    LayerPlacement,
    MissingThroughputProfileError,
    ModelProfile,
    ProfiledThroughputProvider,
    ThroughputProvider,
    build_serving_graph,
)
from src.graph.topology import (
    COORDINATOR_SINK,
    COORDINATOR_SOURCE,
    ClusterTopology,
)
from src.optimizer.carbon_flow import CarbonFlowResult, solve_carbon_aware_flow
from src.optimizer.maxflow import solve_max_flow
from src.utils.config import (
    bandwidth_mbps_to_activation_tokens_per_second,
    bandwidth_mbps_to_tokens_per_second,
)


PhysicalEdge = tuple[str, str]
OBJECTIVE_SCALE = 1_000_000_000.0


class PlacementOptimizationError(RuntimeError):
    """Raised when a placement MILP fails or disagrees with graph validation."""


@dataclass(frozen=True, slots=True)
class PlacementMILPResult:
    """Validated throughput-optimal placement and solver diagnostics."""

    placement: LayerPlacement
    milp_throughput: float
    validated_max_flow: float
    solver_time_seconds: float
    solver_status: str
    optimality_gap: float | None
    active_flow_edges: Mapping[PhysicalEdge, float]
    selected_layer_counts: Mapping[str, int]
    start_layers: Mapping[str, int]
    end_layers: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class CarbonPlacementMILPResult:
    """Validated joint placement-and-routing minimum-carbon solution."""

    placement: LayerPlacement
    throughput_target: float
    achieved_throughput: float
    carbon_g_per_second: float
    carbon_g_per_1000_tokens: float
    milp_carbon_g_per_second: float
    solver_time_seconds: float
    solver_status: str
    optimality_gap: float | None
    active_flow_edges: Mapping[PhysicalEdge, float]
    selected_layer_counts: Mapping[str, int]
    start_layers: Mapping[str, int]
    end_layers: Mapping[str, int]
    validated_flow: CarbonFlowResult


@dataclass(slots=True)
class _MILPBuilder:
    names: list[str]
    lower: list[float]
    upper: list[float]
    integrality: list[int]
    rows: list[dict[int, float]]
    row_lower: list[float]
    row_upper: list[float]

    @classmethod
    def create(cls) -> "_MILPBuilder":
        return cls([], [], [], [], [], [], [])

    def variable(
        self, name: str, lower: float, upper: float, *, integer: bool = False
    ) -> int:
        index = len(self.names)
        self.names.append(name)
        self.lower.append(lower)
        self.upper.append(upper)
        self.integrality.append(1 if integer else 0)
        return index

    def constraint(
        self, coefficients: Mapping[int, float], lower: float, upper: float
    ) -> None:
        self.rows.append(dict(coefficients))
        self.row_lower.append(lower)
        self.row_upper.append(upper)

    def solve(
        self,
        objective: np.ndarray,
        *,
        mip_rel_gap: float = 0.0,
        time_limit_seconds: float | None = None,
    ) -> tuple[OptimizeResult, float]:
        if mip_rel_gap < 0.0:
            raise ValueError("mip_rel_gap cannot be negative")
        if time_limit_seconds is not None and time_limit_seconds <= 0.0:
            raise ValueError("time_limit_seconds must be positive when supplied")
        row_indices: list[int] = []
        column_indices: list[int] = []
        values: list[float] = []
        for row_index, row in enumerate(self.rows):
            for column_index, value in row.items():
                if value:
                    row_indices.append(row_index)
                    column_indices.append(column_index)
                    values.append(value)
        matrix = coo_matrix(
            (values, (row_indices, column_indices)),
            shape=(len(self.rows), len(self.names)),
        ).tocsr()
        constraints = LinearConstraint(
            matrix,
            np.asarray(self.row_lower, dtype=float),
            np.asarray(self.row_upper, dtype=float),
        )
        start = perf_counter()
        options = {"presolve": True, "mip_rel_gap": float(mip_rel_gap)}
        if time_limit_seconds is not None:
            options["time_limit"] = float(time_limit_seconds)
        solution = milp(
            c=objective,
            integrality=np.asarray(self.integrality, dtype=int),
            bounds=Bounds(
                np.asarray(self.lower, dtype=float),
                np.asarray(self.upper, dtype=float),
            ),
            constraints=constraints,
            options=options,
        )
        return solution, perf_counter() - start


@dataclass(frozen=True, slots=True)
class _PlacementVariables:
    starts: Mapping[str, int]
    layer_choices: Mapping[tuple[str, int], int]
    edge_enabled: Mapping[PhysicalEdge, int]
    flows: Mapping[PhysicalEdge, int]
    allowed_layer_counts: Mapping[str, tuple[int, ...]]
    throughputs: Mapping[tuple[str, int], float]
    capacities: Mapping[PhysicalEdge, float]


def _require_homogeneous_layers(model: ModelProfile) -> tuple[float, float]:
    compute = np.asarray(model.layer_compute_units_per_token, dtype=float)
    memory = np.asarray(model.layer_memory_gb, dtype=float)
    if not np.allclose(compute, compute[0], rtol=0.0, atol=1e-12):
        raise NotImplementedError(
            "Placement MILP currently supports homogeneous layer compute only"
        )
    if not np.allclose(memory, memory[0], rtol=0.0, atol=1e-12):
        raise NotImplementedError(
            "Placement MILP currently supports homogeneous layer memory only"
        )
    return float(compute[0]), float(memory[0])


def _allowed_layer_counts(
    topology: ClusterTopology,
    model: ModelProfile,
    throughput_provider: ThroughputProvider,
) -> tuple[dict[str, tuple[int, ...]], dict[tuple[str, int], float]]:
    _, memory_per_layer = _require_homogeneous_layers(model)
    allowed: dict[str, tuple[int, ...]] = {}
    throughputs: dict[tuple[str, int], float] = {}
    for gpu_id in sorted(topology.gpus):
        gpu = topology.gpus[gpu_id]
        memory_limit = (
            model.num_layers
            if memory_per_layer == 0
            else min(model.num_layers, int((gpu.memory_gb + 1e-12) // memory_per_layer))
        )
        if isinstance(throughput_provider, ProfiledThroughputProvider):
            candidates = sorted(
                count
                for count in throughput_provider.profiles.get(gpu.gpu_type, {})
                if 1 <= count <= memory_limit
            )
        else:
            candidates = list(range(1, memory_limit + 1))
        valid: list[int] = []
        for layer_count in candidates:
            try:
                throughput = throughput_provider.throughput(
                    gpu, 0, layer_count, model
                )
            except MissingThroughputProfileError:
                continue
            if throughput > 0:
                valid.append(layer_count)
                throughputs[(gpu_id, layer_count)] = float(throughput)
        if not valid:
            raise PlacementOptimizationError(
                f"GPU {gpu_id!r} has no memory-feasible throughput profile"
            )
        allowed[gpu_id] = tuple(valid)
    return allowed, throughputs


def _physical_capacity(
    edge: PhysicalEdge, topology: ClusterTopology, model: ModelProfile
) -> float:
    link = topology.get_link(*edge)
    if link is None:
        raise PlacementOptimizationError(f"Missing physical link {edge}")
    if edge[0] == COORDINATOR_SOURCE or edge[1] == COORDINATOR_SINK:
        return bandwidth_mbps_to_tokens_per_second(
            link.bandwidth_mbps, model.token_bytes
        )
    return bandwidth_mbps_to_activation_tokens_per_second(
        link.bandwidth_mbps, model.activation_bytes_per_token
    )


def _add_term(row: dict[int, float], index: int, value: float) -> None:
    row[index] = row.get(index, 0.0) + value


def _build_base_model(
    topology: ClusterTopology,
    model: ModelProfile,
    throughput_provider: ThroughputProvider,
) -> tuple[_MILPBuilder, _PlacementVariables]:
    allowed, throughputs = _allowed_layer_counts(
        topology, model, throughput_provider
    )
    builder = _MILPBuilder.create()
    starts = {
        gpu_id: builder.variable(
            f"start[{gpu_id}]", 0.0, float(model.num_layers - 1), integer=True
        )
        for gpu_id in sorted(topology.gpus)
    }
    choices = {
        (gpu_id, count): builder.variable(
            f"layers[{gpu_id},{count}]", 0.0, 1.0, integer=True
        )
        for gpu_id in sorted(topology.gpus)
        for count in allowed[gpu_id]
    }
    capacities = {
        (link.source, link.target): _physical_capacity(
            (link.source, link.target), topology, model
        )
        for link in topology.links
    }
    flows = {
        edge: builder.variable(f"flow[{edge[0]},{edge[1]}]", 0.0, capacity)
        for edge, capacity in capacities.items()
    }
    enabled = {
        edge: builder.variable(
            f"enabled[{edge[0]},{edge[1]}]", 0.0, 1.0, integer=True
        )
        for edge in capacities
    }

    for gpu_id in sorted(topology.gpus):
        builder.constraint(
            {choices[(gpu_id, count)]: 1.0 for count in allowed[gpu_id]},
            1.0,
            1.0,
        )
        end_bound = {starts[gpu_id]: 1.0}
        for count in allowed[gpu_id]:
            _add_term(end_bound, choices[(gpu_id, count)], float(count))
        builder.constraint(end_bound, -np.inf, float(model.num_layers))

    big_m = float(model.num_layers)
    for edge, flow_index in flows.items():
        source, target = edge
        enabled_index = enabled[edge]
        builder.constraint(
            {flow_index: 1.0, enabled_index: -capacities[edge]},
            -np.inf,
            0.0,
        )
        if source == COORDINATOR_SOURCE and target in topology.gpus:
            builder.constraint(
                {starts[target]: 1.0, enabled_index: big_m},
                -np.inf,
                big_m,
            )
        elif target == COORDINATOR_SINK and source in topology.gpus:
            row = {starts[source]: -1.0, enabled_index: big_m}
            for count in allowed[source]:
                _add_term(row, choices[(source, count)], -float(count))
            builder.constraint(row, -np.inf, big_m - model.num_layers)
        elif source in topology.gpus and target in topology.gpus:
            difference = {
                starts[target]: 1.0,
                starts[source]: -1.0,
                enabled_index: big_m,
            }
            for count in allowed[source]:
                _add_term(difference, choices[(source, count)], -float(count))
            builder.constraint(difference, -np.inf, big_m)
            reverse = {index: -value for index, value in difference.items()}
            reverse[enabled_index] = big_m
            builder.constraint(reverse, -np.inf, big_m)
        else:
            raise PlacementOptimizationError(
                f"Unsupported coordinator link direction: {source}->{target}"
            )

    for gpu_id in sorted(topology.gpus):
        conservation: dict[int, float] = {}
        compute: dict[int, float] = {}
        for edge, flow_index in flows.items():
            if edge[1] == gpu_id:
                _add_term(conservation, flow_index, 1.0)
                _add_term(compute, flow_index, 1.0)
            if edge[0] == gpu_id:
                _add_term(conservation, flow_index, -1.0)
        builder.constraint(conservation, 0.0, 0.0)
        for count in allowed[gpu_id]:
            _add_term(
                compute,
                choices[(gpu_id, count)],
                -throughputs[(gpu_id, count)],
            )
        builder.constraint(compute, -np.inf, 0.0)

    return builder, _PlacementVariables(
        starts=starts,
        layer_choices=choices,
        edge_enabled=enabled,
        flows=flows,
        allowed_layer_counts=allowed,
        throughputs=throughputs,
        capacities=capacities,
    )


def _extract_placement(
    solution: OptimizeResult,
    variables: _PlacementVariables,
    *,
    prefix: str,
) -> tuple[LayerPlacement, dict[str, int], dict[str, int], dict[str, int]]:
    if solution.x is None:
        raise PlacementOptimizationError("MILP returned no primal solution")
    starts: dict[str, int] = {}
    counts: dict[str, int] = {}
    ends: dict[str, int] = {}
    intervals: dict[str, LayerInterval] = {}
    for gpu_id in sorted(variables.starts):
        start = int(round(float(solution.x[variables.starts[gpu_id]])))
        selected = max(
            variables.allowed_layer_counts[gpu_id],
            key=lambda count: solution.x[variables.layer_choices[(gpu_id, count)]],
        )
        if solution.x[variables.layer_choices[(gpu_id, selected)]] < 0.5:
            raise PlacementOptimizationError(
                f"MILP did not select a layer count for GPU {gpu_id}"
            )
        end = start + selected
        starts[gpu_id] = start
        counts[gpu_id] = selected
        ends[gpu_id] = end
        intervals[gpu_id] = LayerInterval(start, end)
    signature = ";".join(
        f"{gpu_id}:{starts[gpu_id]}-{ends[gpu_id]}" for gpu_id in sorted(starts)
    )
    digest = sha256(signature.encode("ascii")).hexdigest()[:12]
    return LayerPlacement(f"{prefix}_{digest}", intervals), counts, starts, ends


def _positive_physical_flows(
    solution: OptimizeResult,
    variables: _PlacementVariables,
    tolerance: float,
) -> dict[PhysicalEdge, float]:
    assert solution.x is not None
    return dict(
        sorted(
            (edge, float(solution.x[index]))
            for edge, index in variables.flows.items()
            if solution.x[index] > tolerance
        )
    )


def _optimality_gap(solution: OptimizeResult) -> float | None:
    value = getattr(solution, "mip_gap", None)
    return None if value is None else float(value)


def _require_success(solution: OptimizeResult, label: str) -> None:
    if not solution.success or solution.x is None:
        raise PlacementOptimizationError(f"{label} failed: {solution.message}")


def solve_throughput_optimal_placement(
    topology: ClusterTopology,
    model: ModelProfile,
    throughput_provider: ThroughputProvider,
    *,
    tolerance: float = 1e-6,
) -> PlacementMILPResult:
    """Maximize serving throughput jointly over strict-boundary placements."""

    builder, variables = _build_base_model(topology, model, throughput_provider)
    objective = np.zeros(len(builder.names), dtype=float)
    for edge, index in variables.flows.items():
        if edge[0] == COORDINATOR_SOURCE:
            objective[index] = -1.0
    solution, solver_time = builder.solve(objective)
    _require_success(solution, "Throughput placement MILP")
    placement, counts, starts, ends = _extract_placement(
        solution, variables, prefix="helix"
    )
    placement.validate(topology, model)
    serving = build_serving_graph(topology, model, placement, throughput_provider)
    validated = solve_max_flow(serving, tolerance=tolerance)
    assert solution.x is not None
    milp_throughput = sum(
        float(solution.x[index])
        for edge, index in variables.flows.items()
        if edge[0] == COORDINATOR_SOURCE
    )
    if abs(validated.max_flow_value - milp_throughput) > tolerance:
        raise PlacementOptimizationError(
            "Placement MILP throughput disagrees with reconstructed max-flow: "
            f"milp={milp_throughput}, validated={validated.max_flow_value}"
        )
    return PlacementMILPResult(
        placement=placement,
        milp_throughput=milp_throughput,
        validated_max_flow=validated.max_flow_value,
        solver_time_seconds=solver_time,
        solver_status=str(solution.message),
        optimality_gap=_optimality_gap(solution),
        active_flow_edges=_positive_physical_flows(solution, variables, tolerance),
        selected_layer_counts=dict(sorted(counts.items())),
        start_layers=dict(sorted(starts.items())),
        end_layers=dict(sorted(ends.items())),
    )


def solve_carbon_aware_placement(
    topology: ClusterTopology,
    model: ModelProfile,
    throughput_provider: ThroughputProvider,
    energy_provider: EnergyProvider,
    carbon_intensity_by_region: CarbonIntensityInput,
    throughput_target: float,
    *,
    phase: str,
    batch_size: int,
    tolerance: float = 1e-6,
    timestamp: float | None = None,
    mip_rel_gap: float = 0.0,
    time_limit_seconds: float | None = None,
) -> CarbonPlacementMILPResult:
    """Minimize operational compute carbon over placement and routing."""

    if throughput_target <= 0:
        raise ValueError("throughput_target must be positive")
    ci_snapshot = resolve_ci_snapshot(
        carbon_intensity_by_region,
        (gpu.region for gpu in topology.gpus.values()),
        timestamp,
    )

    builder, variables = _build_base_model(topology, model, throughput_provider)
    flow_by_count: dict[tuple[str, int], int] = {}
    carbon_coefficients: dict[tuple[str, int], float] = {}
    for gpu_id in sorted(topology.gpus):
        gpu = topology.gpus[gpu_id]
        for count in variables.allowed_layer_counts[gpu_id]:
            flow_by_count[(gpu_id, count)] = builder.variable(
                f"gpu_flow[{gpu_id},{count}]",
                0.0,
                variables.throughputs[(gpu_id, count)],
            )
            energy = energy_provider.energy_joules_per_token_for_layer_count(
                gpu, count, phase=phase, batch_size=batch_size
            )
            carbon_coefficients[(gpu_id, count)] = operational_carbon_g(
                energy,
                ci_snapshot[gpu.region],
            )

    for gpu_id in sorted(topology.gpus):
        incoming_equals_profile_flow: dict[int, float] = {}
        for edge, flow_index in variables.flows.items():
            if edge[1] == gpu_id:
                _add_term(incoming_equals_profile_flow, flow_index, 1.0)
        for count in variables.allowed_layer_counts[gpu_id]:
            x_index = flow_by_count[(gpu_id, count)]
            _add_term(incoming_equals_profile_flow, x_index, -1.0)
            builder.constraint(
                {
                    x_index: 1.0,
                    variables.layer_choices[(gpu_id, count)]: -variables.throughputs[
                        (gpu_id, count)
                    ],
                },
                -np.inf,
                0.0,
            )
        builder.constraint(incoming_equals_profile_flow, 0.0, 0.0)

    target_row = {
        index: 1.0
        for edge, index in variables.flows.items()
        if edge[0] == COORDINATOR_SOURCE
    }
    builder.constraint(target_row, throughput_target, throughput_target)
    objective = np.zeros(len(builder.names), dtype=float)
    for key, index in flow_by_count.items():
        objective[index] = carbon_coefficients[key] * OBJECTIVE_SCALE
    solution, solver_time = builder.solve(
        objective,
        mip_rel_gap=mip_rel_gap,
        time_limit_seconds=time_limit_seconds,
    )
    if not solution.success and not (
        time_limit_seconds is not None and solution.x is not None
    ):
        _require_success(solution, "Carbon-aware placement MILP")
    placement, counts, starts, ends = _extract_placement(
        solution, variables, prefix="carbon"
    )
    placement.validate(topology, model)
    serving = build_serving_graph(topology, model, placement, throughput_provider)
    carbon_model = CarbonCostModel.build(
        topology,
        model,
        placement,
        energy_provider,
        ci_snapshot,
        phase=phase,
        batch_size=batch_size,
    )
    validated = solve_carbon_aware_flow(
        serving, carbon_model, throughput_target, tolerance=tolerance
    )
    assert solution.fun is not None and solution.x is not None
    milp_carbon = float(solution.fun) / OBJECTIVE_SCALE
    validated_carbon = validated.metrics.carbon_g_per_second
    carbon_tolerance = max(1e-10, abs(milp_carbon) * 1e-6)
    if time_limit_seconds is None and abs(validated_carbon - milp_carbon) > carbon_tolerance:
        raise PlacementOptimizationError(
            "Carbon placement MILP disagrees with fixed-placement validation: "
            f"milp={milp_carbon}, validated={validated_carbon}"
        )
    return CarbonPlacementMILPResult(
        placement=placement,
        throughput_target=throughput_target,
        achieved_throughput=validated.metrics.throughput,
        carbon_g_per_second=validated_carbon,
        carbon_g_per_1000_tokens=validated.metrics.carbon_g_per_1000_tokens,
        milp_carbon_g_per_second=milp_carbon,
        solver_time_seconds=solver_time,
        solver_status=str(solution.message),
        optimality_gap=_optimality_gap(solution),
        active_flow_edges=_positive_physical_flows(solution, variables, tolerance),
        selected_layer_counts=dict(sorted(counts.items())),
        start_layers=dict(sorted(starts.items())),
        end_layers=dict(sorted(ends.items())),
        validated_flow=validated,
    )

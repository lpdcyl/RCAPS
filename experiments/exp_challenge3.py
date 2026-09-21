"""Synthetic Challenge 3 dynamic scheduling and slow-placement experiments."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Mapping

import numpy as np
import pandas as pd

from experiments.exp_challenge2 import _energy_provider
from experiments.phase35_common import (
    capacity_tokens_to_mbps,
    load_phase35_context,
    scenario_topology,
)
from src.carbon.config import load_cbgp_config
from src.carbon.model import CarbonCostModel
from src.carbon.trace import TraceCIProvider
from src.graph.serving_graph import build_serving_graph
from src.graph.topology import with_cross_region_bandwidth
from src.optimizer.carbon_flow import evaluate_flow_carbon
from src.optimizer.maxflow import solve_max_flow
from src.optimizer.placement_milp import (
    solve_carbon_aware_placement,
    solve_throughput_optimal_placement,
)
from src.scheduler.carbon_flow_scheduler import CarbonFlowScheduler
from src.scheduler.config import Challenge3Config, load_challenge3_config
from src.scheduler.request_dispatcher import DeterministicQuotaDispatcher, Request
from src.scheduler.slow_placement import SlowCBGPController


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results/challenge3"


@dataclass(frozen=True, slots=True)
class Challenge3Outputs:
    points: pd.DataFrame
    trace_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    failure_cases: pd.DataFrame
    runtime_summary: pd.DataFrame
    config_hash: str
    output_dir: Path


def _config_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_traces(config: Challenge3Config, config_dir: Path) -> Mapping[str, TraceCIProvider]:
    return {
        name: TraceCIProvider.from_csv(config_dir.parent / path)
        if not Path(path).is_absolute()
        else TraceCIProvider.from_csv(path)
        for name, path in config.trace_files.items()
    }


def _scaled_flow_edges(serving, max_flow, target):
    scale = target / max_flow.max_flow_value
    return {
        edge: value * scale for edge, value in max_flow.positive_flow_edges.items()
    }


def _static_carbon(
    serving,
    flow_edges,
    carbon_model,
    throughput: float,
):
    return evaluate_flow_carbon(serving, flow_edges, carbon_model, throughput)


def _flow_switch(previous: Mapping[str, float] | None, current: Mapping[str, float]) -> int:
    if previous is None:
        return 0
    return int(previous != current)


def _run_case(
    context,
    config: Challenge3Config,
    cbgp_config,
    trace_name: str,
    trace: TraceCIProvider,
    load_name: str,
    load_factor: float,
    scenario: str,
    network_condition: str,
    capacity: float,
) -> dict[str, object]:
    model = context.phase3.simulation.model
    throughput_provider = context.phase3.throughput_provider
    energy = _energy_provider(context, "baseline")
    topology = with_cross_region_bandwidth(
        scenario_topology(context, scenario),
        capacity_tokens_to_mbps(capacity, model.activation_bytes_per_token),
    )
    helix = solve_throughput_optimal_placement(topology, model, throughput_provider)
    target = load_factor * helix.validated_max_flow
    initial_placement = helix.placement
    initial_serving = build_serving_graph(
        topology, model, initial_placement, throughput_provider
    )
    initial_maxflow = solve_max_flow(initial_serving)
    static_helix_edges = _scaled_flow_edges(initial_serving, initial_maxflow, target)

    t0 = 0.0
    initial_scheduler = CarbonFlowScheduler(
        topology,
        model,
        initial_placement,
        throughput_provider,
        energy,
        trace,
        phase=context.phase3.config.phase,
        batch_size=context.phase3.config.batch_size,
        scheduling_interval_seconds=config.scheduling_interval_seconds,
        solver_tolerance=config.solver_tolerance,
    )
    initial_dynamic = initial_scheduler.schedule(t0, target)
    static_carbon_edges = initial_dynamic.flow_result.metrics.positive_flow_edges

    controller = SlowCBGPController(
        topology,
        model,
        initial_placement,
        throughput_provider,
        energy,
        cbgp_config,
        phase=context.phase3.config.phase,
        batch_size=context.phase3.config.batch_size,
        placement_check_interval_seconds=config.placement_check_interval_seconds,
        persistence_intervals=config.placement_persistence_intervals,
        minimum_dwell_seconds=config.minimum_placement_dwell_seconds,
    )

    static_helix_carbon = 0.0
    static_routing_carbon = 0.0
    dynamic_carbon = 0.0
    dispatch_carbon = 0.0
    slow_cbgp_carbon = 0.0
    oracle_carbon = 0.0
    total_requested = 0.0
    dynamic_served = 0.0
    dispatch_served = 0.0
    oracle_served = 0.0
    static_helix_served = 0.0
    static_routing_served = 0.0
    capacity_violations = 0
    flow_switches = 0
    dispatch_path_switches = 0
    oracle_placement_changes = 0
    oracle_mip_gaps: list[float] = []
    previous_dynamic_paths = None
    previous_dispatch_paths = None
    previous_oracle_signature = None
    joint_runtime = 0.0
    scheduler_runtime = 0.0
    dispatch_runtime = 0.0
    slow_cbgp_runtime = 0.0
    slow_invocations_before = controller.invocation_count
    slow_accepted_before = controller.accepted_count
    intervals = config.trace_duration_intervals

    for interval_index in range(intervals):
        timestamp = interval_index * config.scheduling_interval_seconds
        demand = target
        scheduler = CarbonFlowScheduler(
            topology,
            model,
            controller.current_placement,
            throughput_provider,
            energy,
            trace,
            phase=context.phase3.config.phase,
            batch_size=context.phase3.config.batch_size,
            scheduling_interval_seconds=config.scheduling_interval_seconds,
            solver_tolerance=config.solver_tolerance,
        )
        schedule_start = perf_counter()
        schedule = scheduler.schedule(timestamp, demand)
        scheduler_runtime += perf_counter() - schedule_start
        dynamic_paths = schedule.flow_result.metrics.path_flow_share
        flow_switches += _flow_switch(previous_dynamic_paths, dynamic_paths)
        previous_dynamic_paths = dynamic_paths

        current_costs = CarbonCostModel.build(
            topology,
            model,
            controller.current_placement,
            energy,
            schedule.ci_snapshot,
            phase=context.phase3.config.phase,
            batch_size=context.phase3.config.batch_size,
        )
        initial_costs = CarbonCostModel.build(
            topology,
            model,
            initial_placement,
            energy,
            schedule.ci_snapshot,
            phase=context.phase3.config.phase,
            batch_size=context.phase3.config.batch_size,
        )
        interval = config.scheduling_interval_seconds
        static_helix_metrics = _static_carbon(
            initial_serving,
            static_helix_edges,
            initial_costs,
            target,
        )
        static_routing_metrics = _static_carbon(
            initial_serving,
            static_carbon_edges,
            initial_costs,
            target,
        )
        static_helix_carbon += static_helix_metrics.carbon_g_per_second * interval
        static_routing_carbon += static_routing_metrics.carbon_g_per_second * interval
        dynamic_carbon += schedule.carbon_g_per_second * interval
        static_helix_served += target * interval
        static_routing_served += target * interval
        dynamic_served += schedule.served_throughput * interval

        request_count = int(round(demand * interval / config.request_tokens))
        requests = tuple(
            Request(
                f"{trace_name}:{scenario}:{load_name}:{interval_index}:{index}",
                config.request_tokens,
            )
            for index in range(request_count)
        )
        dispatch_start = perf_counter()
        dispatch = DeterministicQuotaDispatcher(
            schedule.path_quota_tokens_per_second,
            duration_seconds=interval,
            tolerance=config.solver_tolerance,
        ).dispatch_batch(requests)
        dispatch_runtime += perf_counter() - dispatch_start
        dispatch_served += dispatch.accepted_tokens
        if previous_dispatch_paths is not None:
            current_dispatch_paths = tuple(
                decision.path for decision in dispatch.decisions if decision.accepted
            )
            dispatch_path_switches += int(current_dispatch_paths != previous_dispatch_paths)
        previous_dispatch_paths = tuple(
            decision.path for decision in dispatch.decisions if decision.accepted
        )
        if schedule.served_throughput > 0.0:
            dispatch_carbon += (
                schedule.carbon_g_per_second
                * dispatch.accepted_tokens
                / (schedule.served_throughput * interval)
                * interval
            )
        if dispatch.rejected_tokens > 0.0:
            capacity_violations += 1

        slow_cbgp_carbon += schedule.carbon_g_per_second * interval
        slow_start = perf_counter()
        controller.maybe_update(timestamp, schedule)
        slow_cbgp_runtime += perf_counter() - slow_start

        oracle_start = perf_counter()
        oracle = solve_carbon_aware_placement(
            topology,
            model,
            throughput_provider,
            energy,
            schedule.ci_snapshot,
            target,
            phase=context.phase3.config.phase,
            batch_size=context.phase3.config.batch_size,
            tolerance=config.solver_tolerance,
            mip_rel_gap=config.joint_oracle_mip_rel_gap,
            time_limit_seconds=config.joint_oracle_time_limit_seconds,
        )
        joint_runtime += perf_counter() - oracle_start
        oracle_carbon += oracle.carbon_g_per_second * interval
        oracle_served += oracle.achieved_throughput * interval
        if oracle.optimality_gap is not None:
            oracle_mip_gaps.append(float(oracle.optimality_gap))
        oracle_signature = tuple(sorted(oracle.placement.intervals.items()))
        if previous_oracle_signature is not None:
            oracle_placement_changes += int(oracle_signature != previous_oracle_signature)
        previous_oracle_signature = oracle_signature

    duration = intervals * config.scheduling_interval_seconds
    return {
        "trace": trace_name,
        "load_profile": load_name,
        "gpu_scenario": scenario,
        "network_condition": network_condition,
        "network_capacity": capacity,
        "intervals": intervals,
        "duration_seconds": duration,
        "demand_tokens_per_second": target,
        "static_helix_carbon": static_helix_carbon,
        "static_routing_carbon": static_routing_carbon,
        "dynamic_carbon": dynamic_carbon,
        "dynamic_dispatch_carbon": dispatch_carbon,
        "slow_cbgp_carbon": slow_cbgp_carbon,
        "always_replace_oracle_carbon": oracle_carbon,
        "dynamic_reduction_vs_helix": (static_helix_carbon - dynamic_carbon) / static_helix_carbon,
        "dynamic_reduction_vs_static_routing": (
            static_routing_carbon - dynamic_carbon
        )
        / static_routing_carbon,
        "dispatch_reduction_vs_helix": (static_helix_carbon - dispatch_carbon) / static_helix_carbon,
        "slow_cbgp_reduction_vs_helix": (static_helix_carbon - slow_cbgp_carbon) / static_helix_carbon,
        "oracle_reduction_vs_helix": (static_helix_carbon - oracle_carbon) / static_helix_carbon,
        "mean_demand_satisfaction_dynamic": dynamic_served / (target * duration),
        "mean_demand_satisfaction_dispatch": dispatch_served / (target * duration),
        "mean_demand_satisfaction_oracle": oracle_served / (target * duration),
        "capacity_violation_count": capacity_violations,
        "flow_reallocations": flow_switches,
        "dispatch_path_changes": dispatch_path_switches,
        "slow_cbgp_invocations": controller.invocation_count - slow_invocations_before,
        "accepted_placement_changes": controller.accepted_count - slow_accepted_before,
        "always_replace_placement_changes": oracle_placement_changes,
        "oracle_mip_gap_mean": float(np.mean(oracle_mip_gaps)) if oracle_mip_gaps else 0.0,
        "oracle_mip_gap_max": float(max(oracle_mip_gaps, default=0.0)),
        "scheduler_runtime": scheduler_runtime,
        "dispatch_runtime": dispatch_runtime,
        "slow_cbgp_runtime": slow_cbgp_runtime,
        "joint_runtime": joint_runtime,
        "performance_violation": int(
            dynamic_served + config.solver_tolerance < target * duration
        ),
    }


def _run_case_worker(payload: tuple[str, tuple[object, ...]]) -> dict[str, object]:
    """Spawn-safe worker that reconstructs read-only experiment context."""

    config_dir, case = payload
    root = Path(config_dir)
    config = load_challenge3_config(root)
    cbgp_config = load_cbgp_config(root)
    traces = _load_traces(config, root)
    context = load_phase35_context(root)
    trace_name, load_name, load_factor, scenario, condition, capacity = case
    return _run_case(
        context,
        config,
        cbgp_config,
        str(trace_name),
        traces[str(trace_name)],
        str(load_name),
        float(load_factor),
        str(scenario),
        str(condition),
        float(capacity),
    )


def _summaries(points: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trace_summary = points.groupby("trace", sort=True).agg(
        point_count=("trace", "size"),
        mean_dynamic_reduction=("dynamic_reduction_vs_helix", "mean"),
        mean_dynamic_vs_static_routing=("dynamic_reduction_vs_static_routing", "mean"),
        max_dynamic_reduction=("dynamic_reduction_vs_helix", "max"),
        mean_flow_reallocations=("flow_reallocations", "mean"),
    ).reset_index()
    scenario_summary = points.groupby("gpu_scenario", sort=True).agg(
        point_count=("gpu_scenario", "size"),
        mean_dynamic_reduction=("dynamic_reduction_vs_helix", "mean"),
        max_dynamic_reduction=("dynamic_reduction_vs_helix", "max"),
        mean_dynamic_demand_satisfaction=("mean_demand_satisfaction_dynamic", "mean"),
        mean_flow_reallocations=("flow_reallocations", "mean"),
        mean_slow_cbgp_invocations=("slow_cbgp_invocations", "mean"),
    ).reset_index()
    failures = points.loc[
        (points["performance_violation"] > 0)
        | (points["dynamic_reduction_vs_helix"] <= 0.0)
        | (points["capacity_violation_count"] > 0)
    ].copy()
    failures["suspected_reason"] = np.select(
        [
            failures["performance_violation"] > 0,
            failures["capacity_violation_count"] > 0,
        ],
        [
            "Demand exceeds feasible fixed-placement throughput",
            "Dispatch quota or capacity invariant was stressed",
        ],
        default="Dynamic CI did not create a lower-carbon feasible flow",
    )
    failure_columns = [
        "trace",
        "load_profile",
        "gpu_scenario",
        "network_condition",
        "dynamic_reduction_vs_helix",
        "mean_demand_satisfaction_dynamic",
        "flow_reallocations",
        "slow_cbgp_invocations",
        "suspected_reason",
    ]
    runtime_rows = []
    for method, column in (
        ("scheduler", "scheduler_runtime"),
        ("dispatch", "dispatch_runtime"),
        ("slow_cbgp", "slow_cbgp_runtime"),
        ("always_replace_oracle", "joint_runtime"),
    ):
        runtime_rows.append(
            {
                "method": method,
                "measurements": len(points),
                "median_seconds": float(points[column].median()),
                "mean_seconds": float(points[column].mean()),
                "p95_seconds": float(points[column].quantile(0.95)),
                "total_seconds": float(points[column].sum()),
            }
        )
    return (
        trace_summary,
        scenario_summary,
        failures[failure_columns],
        pd.DataFrame(runtime_rows),
    )


def run_challenge3(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    limit_cases: int | None = None,
    workers: int = 1,
) -> Challenge3Outputs:
    root = Path(config_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = load_challenge3_config(root)
    cbgp_config = load_cbgp_config(root)
    config_path = root / "challenge3_scheduler.yaml"
    digest = _config_hash(config_path)
    traces = _load_traces(config, root)
    context = load_phase35_context(root)
    rows: list[dict[str, object]] = []
    cases = [
        (trace_name, load_name, load_factor, scenario, condition, capacity)
        for trace_name in traces
        for load_name, load_factor in config.load_profiles.items()
        for scenario in config.gpu_scenarios
        for condition, capacity in config.network_capacities_tokens_per_second.items()
    ]
    if limit_cases is not None:
        cases = cases[:limit_cases]
    if workers <= 0:
        raise ValueError("workers must be positive")
    if workers == 1:
        rows = [
            _run_case(
                context,
                config,
                cbgp_config,
                str(trace_name),
                traces[str(trace_name)],
                str(load_name),
                float(load_factor),
                str(scenario),
                str(condition),
                float(capacity),
            )
            for trace_name, load_name, load_factor, scenario, condition, capacity in cases
        ]
    else:
        payloads = [(str(root), case) for case in cases]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_run_case_worker, payloads))
    points = pd.DataFrame(rows)
    trace_summary, scenario_summary, failures, runtime_summary = _summaries(points)
    points.to_csv(output / "challenge3_point_results.csv", index=False)
    trace_summary.to_csv(output / "challenge3_trace_summary.csv", index=False)
    scenario_summary.to_csv(output / "challenge3_scenario_summary.csv", index=False)
    failures.to_csv(output / "challenge3_failure_cases.csv", index=False)
    runtime_summary.to_csv(output / "challenge3_runtime_summary.csv", index=False)
    (output / "challenge3_config_hash.txt").write_text(
        f"{digest}  configs/challenge3_scheduler.yaml\n", encoding="utf-8"
    )
    return Challenge3Outputs(
        points,
        trace_summary,
        scenario_summary,
        failures,
        runtime_summary,
        digest,
        output,
    )


def main() -> None:
    outputs = run_challenge3()
    points = outputs.points
    print(f"RUNS={len(points)}")
    print(f"DYNAMIC_IMPROVED={int((points.dynamic_reduction_vs_helix > 0).sum())}")
    print(f"MEAN_REDUCTION={float(points.dynamic_reduction_vs_helix.mean()):.17g}")
    print(f"MAX_REDUCTION={float(points.dynamic_reduction_vs_helix.max()):.17g}")
    print(f"PERFORMANCE_VIOLATIONS={int(points.performance_violation.sum())}")
    print(f"FLOW_REALLOCATIONS={int(points.flow_reallocations.sum())}")
    print(f"SLOW_CBGP_INVOCATIONS={int(points.slow_cbgp_invocations.sum())}")
    print(f"ACCEPTED_PLACEMENTS={int(points.accepted_placement_changes.sum())}")
    print(f"ORACLE_PLACEMENT_CHANGES={int(points.always_replace_placement_changes.sum())}")
    print(f"CONFIG_SHA256={outputs.config_hash}")


if __name__ == "__main__":
    main()

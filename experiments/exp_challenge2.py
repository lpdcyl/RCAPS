"""Frozen-grid Challenge 2 evaluation of CBGP against routing and Oracle."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import perf_counter
import re

import numpy as np
import pandas as pd

from experiments.phase35_common import (
    Phase35Context,
    capacity_tokens_to_mbps,
    energy_provider_for_scenario,
    load_phase35_context,
    scenario_topology,
)
from src.analysis.breakpoint import placement_signature, serialize_placement_signature
from src.analysis.routing_gap import routing_gap
from src.carbon.config import CBGPConfig, load_cbgp_config
from src.carbon.model import CarbonCostModel, EnergyProvider
from src.graph.serving_graph import build_serving_graph
from src.graph.topology import with_cross_region_bandwidth
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.cbgp import CBGPResult, solve_cbgp
from src.optimizer.placement_milp import (
    solve_carbon_aware_placement,
    solve_throughput_optimal_placement,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"
DEFAULT_BASELINE = PROJECT_ROOT / "results/phase1b_phase35_regression/phase35_summary.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results/challenge2"


@dataclass(frozen=True, slots=True)
class Challenge2Outputs:
    points: pd.DataFrame
    threshold_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    failure_cases: pd.DataFrame
    runtime_summary: pd.DataFrame
    output_dir: Path
    config_hash: str


@dataclass(frozen=True, slots=True)
class _RunSpec:
    study: str
    scenario: str
    rho: float
    energy_scenario: str
    capacity_tokens_per_second: float


def _config_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _energy_provider(context: Phase35Context, label: str) -> EnergyProvider:
    if label in {"baseline", "baseline_1.0x"}:
        return context.phase3.energy_provider
    match = re.fullmatch(r"(.+)_([0-9]+(?:\.[0-9]+)?)x", label)
    if match is None:
        raise ValueError(f"Unsupported Phase 3.5 energy scenario: {label!r}")
    return energy_provider_for_scenario(
        context,
        match.group(1),
        float(match.group(2)),
    )


def _run_specs(baseline: pd.DataFrame) -> tuple[_RunSpec, ...]:
    columns = [
        "study",
        "scenario",
        "rho",
        "energy_scenario",
        "capacity_tokens_per_second",
    ]
    unique = baseline[columns].drop_duplicates(keep="first")
    return tuple(
        _RunSpec(
            str(row.study),
            str(row.scenario),
            float(row.rho),
            str(row.energy_scenario),
            float(row.capacity_tokens_per_second),
        )
        for row in unique.itertuples(index=False)
    )


def _matching_rows(baseline: pd.DataFrame, spec: _RunSpec) -> pd.DataFrame:
    mask = (
        (baseline["study"] == spec.study)
        & (baseline["scenario"] == spec.scenario)
        & np.isclose(baseline["rho"], spec.rho)
        & (baseline["energy_scenario"] == spec.energy_scenario)
        & np.isclose(
            baseline["capacity_tokens_per_second"],
            spec.capacity_tokens_per_second,
        )
    )
    return baseline.loc[mask].sort_values("ci_ratio", kind="stable")


def _gap_closed(
    routing_carbon: float,
    cbgp_carbon: float,
    joint_carbon: float,
    routing_gap_value: float,
    routing_sufficient_threshold: float,
) -> float:
    if routing_gap_value <= routing_sufficient_threshold:
        return float("nan")
    denominator = routing_carbon - joint_carbon
    if denominator <= 0.0:
        return float("nan")
    return (routing_carbon - cbgp_carbon) / denominator


def _cbgp_metrics(
    result: CBGPResult,
    routing_carbon: float,
    joint_carbon: float,
    routing_gap_value: float,
    routing_sufficient_threshold: float,
) -> dict[str, object]:
    cbgp_carbon = result.flow.metrics.carbon_g_per_second
    return {
        "cbgp_carbon": cbgp_carbon,
        "cbgp_reduction": (routing_carbon - cbgp_carbon) / routing_carbon,
        "oracle_gap": (cbgp_carbon - joint_carbon) / routing_carbon,
        "gap_closed": _gap_closed(
            routing_carbon,
            cbgp_carbon,
            joint_carbon,
            routing_gap_value,
            routing_sufficient_threshold,
        ),
        "cbgp_runtime": result.runtime_seconds,
        "cbgp_iterations": len(result.iterations),
        "candidate_count": result.candidate_count,
        "feasible_candidate_count": result.feasible_candidate_count,
        "cbgp_optimization_calls": result.optimization_calls,
        "cbgp_placement_signature": serialize_placement_signature(
            placement_signature(result.placement)
        ),
        "placement_changed": result.placement_changed,
        "cbgp_termination_reason": result.termination_reason,
    }


def _run_point(
    context: Phase35Context,
    config: CBGPConfig,
    spec: _RunSpec,
    baseline_row: object,
    topology: object,
    energy_provider: EnergyProvider,
    helix: object,
    helix_serving: object,
) -> dict[str, object]:
    model = context.phase3.simulation.model
    throughput_provider = context.phase3.throughput_provider
    phase = context.phase3.config.phase
    batch_size = context.phase3.config.batch_size
    target = spec.rho * helix.validated_max_flow
    intensities = {
        "A": float(baseline_row.ci_a),
        "B": float(baseline_row.ci_b),
    }

    routing_start = perf_counter()
    routing_costs = CarbonCostModel.build(
        topology,
        model,
        helix.placement,
        energy_provider,
        intensities,
        phase=phase,
        batch_size=batch_size,
    )
    routing = solve_carbon_aware_flow(
        helix_serving,
        routing_costs,
        target,
        tolerance=config.solver_tolerance,
    )
    routing_runtime = perf_counter() - routing_start

    cbgp = solve_cbgp(
        topology,
        model,
        throughput_provider,
        energy_provider,
        intensities,
        helix.placement,
        target,
        config,
        phase=phase,
        batch_size=batch_size,
        bottleneck_guided=True,
    )
    unguided = solve_cbgp(
        topology,
        model,
        throughput_provider,
        energy_provider,
        intensities,
        helix.placement,
        target,
        config,
        phase=phase,
        batch_size=batch_size,
        bottleneck_guided=False,
    )

    joint_start = perf_counter()
    joint = solve_carbon_aware_placement(
        topology,
        model,
        throughput_provider,
        energy_provider,
        intensities,
        target,
        phase=phase,
        batch_size=batch_size,
        tolerance=config.solver_tolerance,
    )
    joint_runtime = perf_counter() - joint_start

    routing_carbon = routing.metrics.carbon_g_per_second
    joint_carbon = joint.carbon_g_per_second
    cbgp_carbon = cbgp.flow.metrics.carbon_g_per_second
    numerical_tolerance = max(1e-9, abs(routing_carbon) * 1e-8)
    if joint_carbon > cbgp_carbon + numerical_tolerance:
        raise AssertionError(
            f"Oracle ordering failed: joint={joint_carbon}, cbgp={cbgp_carbon}"
        )
    if cbgp_carbon > routing_carbon + numerical_tolerance:
        raise AssertionError(
            f"CBGP ordering failed: cbgp={cbgp_carbon}, routing={routing_carbon}"
        )
    if abs(float(baseline_row.routing_carbon) - routing_carbon) > 1e-9:
        raise AssertionError("Routing carbon differs from frozen Phase 1B baseline")
    if abs(float(baseline_row.joint_carbon) - joint_carbon) > 1e-9:
        raise AssertionError("Joint carbon differs from frozen Phase 1B baseline")

    gap = routing_gap(routing_carbon, joint_carbon)
    routing_sufficient_threshold = min(config.placement_gap_thresholds)
    primary_placement_threshold = sorted(config.placement_gap_thresholds)[1]
    cbgp_values = _cbgp_metrics(
        cbgp,
        routing_carbon,
        joint_carbon,
        gap,
        routing_sufficient_threshold,
    )
    unguided_carbon = unguided.flow.metrics.carbon_g_per_second
    row = {
        "study": spec.study,
        "scenario_id": (
            f"{spec.study}:{spec.scenario}:rho={spec.rho}:"
            f"energy={spec.energy_scenario}:capacity={spec.capacity_tokens_per_second}:"
            f"ci={float(baseline_row.ci_a)}"
        ),
        "gpu_scenario": spec.scenario,
        "energy_scenario": spec.energy_scenario,
        "ci_a": float(baseline_row.ci_a),
        "ci_b": float(baseline_row.ci_b),
        "ci_ratio": float(baseline_row.ci_ratio),
        "network_capacity": spec.capacity_tokens_per_second,
        "rho": spec.rho,
        "F_H": helix.validated_max_flow,
        "F_target": target,
        "routing_carbon": routing_carbon,
        "joint_carbon": joint_carbon,
        "routing_gap": gap,
        "routing_runtime": routing_runtime,
        "routing_solver_runtime": routing.solver_time_seconds,
        "joint_runtime": joint_runtime,
        "joint_solver_runtime": joint.solver_time_seconds,
        "initial_placement_signature": serialize_placement_signature(
            placement_signature(helix.placement)
        ),
        "oracle_placement_signature": serialize_placement_signature(
            placement_signature(joint.placement)
        ),
        "routing_sufficient": gap <= routing_sufficient_threshold,
        "placement_necessary": gap >= primary_placement_threshold,
        "unguided_carbon": unguided_carbon,
        "unguided_reduction": (
            routing_carbon - unguided_carbon
        ) / routing_carbon,
        "unguided_gap_closed": _gap_closed(
            routing_carbon,
            unguided_carbon,
            joint_carbon,
            gap,
            routing_sufficient_threshold,
        ),
        "unguided_runtime": unguided.runtime_seconds,
        "unguided_candidate_count": unguided.candidate_count,
        "unguided_optimization_calls": unguided.optimization_calls,
        **cbgp_values,
    }
    for threshold in config.placement_gap_thresholds:
        label = f"{int(round(100 * threshold))}pct"
        row[f"placement_necessary_{label}"] = gap >= threshold
    return row


def _threshold_summary(points: pd.DataFrame, config: CBGPConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for threshold in config.placement_gap_thresholds:
        necessary = points["routing_gap"] >= threshold
        subset = points.loc[necessary]
        rows.append(
            {
                "threshold": threshold,
                "point_count": len(points),
                "routing_sufficient_count": int((~necessary).sum()),
                "placement_necessary_count": int(necessary.sum()),
                "cbgp_improved_count": int(
                    (points["cbgp_reduction"] > config.min_relative_improvement).sum()
                ),
                "mean_carbon_reduction": float(points["cbgp_reduction"].mean()),
                "max_carbon_reduction": float(points["cbgp_reduction"].max()),
                "median_gap_closed_placement_necessary": float(
                    subset["gap_closed"].median()
                ),
                "mean_gap_closed_placement_necessary": float(
                    subset["gap_closed"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def _scenario_summary(points: pd.DataFrame, config: CBGPConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for scenario, frame in points.groupby("gpu_scenario", sort=True):
        necessary = frame.loc[frame["placement_necessary"]]
        rows.append(
            {
                "gpu_scenario": scenario,
                "point_count": len(frame),
                "routing_sufficient_count": int(frame["routing_sufficient"].sum()),
                "placement_necessary_count": int(frame["placement_necessary"].sum()),
                "cbgp_placement_change_count": int(frame["placement_changed"].sum()),
                "cbgp_improved_count": int(
                    (frame["cbgp_reduction"] > config.min_relative_improvement).sum()
                ),
                "mean_carbon_reduction": float(frame["cbgp_reduction"].mean()),
                "max_carbon_reduction": float(frame["cbgp_reduction"].max()),
                "median_gap_closed_placement_necessary": float(
                    necessary["gap_closed"].median()
                ),
                "mean_gap_closed_placement_necessary": float(
                    necessary["gap_closed"].mean()
                ),
                "median_cbgp_runtime": float(frame["cbgp_runtime"].median()),
                "median_joint_runtime": float(frame["joint_runtime"].median()),
                "median_candidate_count": float(frame["candidate_count"].median()),
            }
        )
    return pd.DataFrame(rows)


def _failure_cases(points: pd.DataFrame) -> pd.DataFrame:
    frame = points.loc[
        points["placement_necessary"]
        & (points["gap_closed"].fillna(0.0) < 0.5)
    ].copy()
    reasons = {
        "no_throughput_feasible_candidates": (
            "No local pair/coordinated-cut candidate met the throughput target"
        ),
        "improvement_below_threshold": (
            "Feasible local candidates did not clear the frozen improvement threshold"
        ),
        "no_unvisited_candidates": "Local search exhausted unvisited boundary candidates",
        "max_iterations": "Greedy local search reached its frozen iteration limit",
    }
    frame["suspected_reason"] = frame["cbgp_termination_reason"].map(reasons).fillna(
        "Greedy local boundary search remained below the global Oracle"
    )
    columns = [
        "scenario_id",
        "gpu_scenario",
        "routing_gap",
        "gap_closed",
        "oracle_placement_signature",
        "cbgp_placement_signature",
        "suspected_reason",
    ]
    return frame[columns].sort_values("routing_gap", ascending=False)


def _runtime_summary(points: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, column in (
        ("Routing", "routing_runtime"),
        ("CBGP", "cbgp_runtime"),
        ("Unguided local search", "unguided_runtime"),
        ("Joint MILP Oracle", "joint_runtime"),
    ):
        values = points[column]
        rows.append(
            {
                "method": method,
                "measurements": len(values),
                "median_seconds": float(values.median()),
                "mean_seconds": float(values.mean()),
                "p95_seconds": float(values.quantile(0.95)),
                "total_seconds": float(values.sum()),
            }
        )
    return pd.DataFrame(rows)


def run_challenge2(
    config_dir: str | Path = CONFIG_DIR,
    *,
    baseline_csv: str | Path = DEFAULT_BASELINE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Challenge2Outputs:
    """Run the frozen 930-point Challenge 2 grid and write all tabular outputs."""

    root = Path(config_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config_path = root / "challenge2_cbgp.yaml"
    config = load_cbgp_config(root)
    digest = _config_hash(config_path)
    np.random.seed(config.random_seed)
    baseline = pd.read_csv(baseline_csv)
    context = load_phase35_context(root)
    rows: list[dict[str, object]] = []

    for spec in _run_specs(baseline):
        group = _matching_rows(baseline, spec)
        topology = with_cross_region_bandwidth(
            scenario_topology(context, spec.scenario),
            capacity_tokens_to_mbps(
                spec.capacity_tokens_per_second,
                context.phase3.simulation.model.activation_bytes_per_token,
            ),
        )
        energy_provider = _energy_provider(context, spec.energy_scenario)
        helix = solve_throughput_optimal_placement(
            topology,
            context.phase3.simulation.model,
            context.phase3.throughput_provider,
        )
        if not np.allclose(group["F_H"], helix.validated_max_flow, atol=1e-9):
            raise AssertionError("Helix throughput differs from Phase 1B baseline")
        helix_serving = build_serving_graph(
            topology,
            context.phase3.simulation.model,
            helix.placement,
            context.phase3.throughput_provider,
        )
        for baseline_row in group.itertuples(index=False):
            rows.append(
                _run_point(
                    context,
                    config,
                    spec,
                    baseline_row,
                    topology,
                    energy_provider,
                    helix,
                    helix_serving,
                )
            )

    points = pd.DataFrame(rows)
    if len(points) != len(baseline):
        raise AssertionError(
            f"Challenge 2 point count mismatch: {len(points)} != {len(baseline)}"
        )
    threshold_summary = _threshold_summary(points, config)
    scenario_summary = _scenario_summary(points, config)
    failures = _failure_cases(points)
    runtimes = _runtime_summary(points)

    points.to_csv(output / "challenge2_point_results.csv", index=False)
    threshold_summary.to_csv(output / "challenge2_summary.csv", index=False)
    scenario_summary.to_csv(output / "challenge2_scenario_summary.csv", index=False)
    failures.to_csv(output / "challenge2_failure_cases.csv", index=False)
    runtimes.to_csv(output / "challenge2_runtime_summary.csv", index=False)
    (output / "challenge2_config_hash.txt").write_text(
        f"{digest}  configs/challenge2_cbgp.yaml\n",
        encoding="utf-8",
    )
    return Challenge2Outputs(
        points,
        threshold_summary,
        scenario_summary,
        failures,
        runtimes,
        output,
        digest,
    )


def main() -> None:
    outputs = run_challenge2()
    points = outputs.points
    necessary = points.loc[points["placement_necessary"]]
    print(f"POINTS={len(points)}")
    print(f"ROUTING_SUFFICIENT={int(points.routing_sufficient.sum())}")
    print(f"PLACEMENT_NECESSARY={int(points.placement_necessary.sum())}")
    print(
        "CBGP_IMPROVED="
        f"{int((points.cbgp_reduction > 0.0001).sum())}"
    )
    print(f"MEDIAN_GAP_CLOSED={float(necessary.gap_closed.median()):.17g}")
    print(f"MAX_REDUCTION={float(points.cbgp_reduction.max()):.17g}")
    print(f"CONFIG_SHA256={outputs.config_hash}")


if __name__ == "__main__":
    main()

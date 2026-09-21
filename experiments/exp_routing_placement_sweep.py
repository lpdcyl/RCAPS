"""One-dimensional routing-versus-placement carbon-intensity sweep."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from experiments.phase3_common import (
    carbon_intensities,
    json_edge_mapping,
    json_float_mapping,
    load_phase3_context,
    solve_helix_baseline,
)
from src.analysis.breakpoint import (
    detect_placement_breakpoints,
    detect_routing_breakpoints,
    graph_change,
    logical_edge_set,
    placement_signature,
    serialize_placement_signature,
)
from src.analysis.routing_gap import is_routing_sufficient, routing_gap
from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import build_serving_graph
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.placement_milp import solve_carbon_aware_placement


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


@dataclass(frozen=True, slots=True)
class StrategySweepOutputs:
    summary: pd.DataFrame
    routing_breakpoints: pd.DataFrame
    placement_breakpoints: pd.DataFrame
    summary_csv: Path
    routing_breakpoints_csv: Path
    placement_breakpoints_csv: Path
    transition_figure: Path


def _destination(
    configured: str, output_dir: str | Path | None
) -> Path:
    return (
        PROJECT_ROOT / configured
        if output_dir is None
        else Path(output_dir) / Path(configured).name
    )


def _plot_transitions(
    summary: pd.DataFrame, destination: Path, epsilon: float
) -> None:
    figure, (gap_axis, placement_axis) = plt.subplots(
        2, 1, figsize=(9, 7), sharex=True, height_ratios=(2, 1)
    )
    gap_axis.plot(
        summary["ci_ratio"], summary["routing_gap"], marker="o", color="#0072B2"
    )
    gap_axis.axhline(epsilon, color="#D55E00", linestyle="--", label=f"epsilon={epsilon:.2f}")
    gap_axis.set_ylabel("Routing gap")
    gap_axis.grid(True, alpha=0.25)
    gap_axis.legend(loc="best")

    placement_codes, placement_labels = pd.factorize(
        summary["carbon_placement_signature"], sort=True
    )
    placement_axis.step(
        summary["ci_ratio"], placement_codes, where="mid", color="#009E73"
    )
    placement_axis.scatter(summary["ci_ratio"], placement_codes, color="#009E73", s=18)
    placement_axis.set_yticks(range(len(placement_labels)))
    placement_axis.set_yticklabels([f"P{index}" for index in range(len(placement_labels))])
    placement_axis.set_xlabel("Carbon intensity ratio CI_A / CI_B")
    placement_axis.set_ylabel("Placement")
    placement_axis.grid(True, alpha=0.25)
    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def run_routing_placement_sweep(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
) -> StrategySweepOutputs:
    """Compare routing-only and joint placement at identical throughput."""

    context = load_phase3_context(config_dir)
    config = context.config
    helix = solve_helix_baseline(context)
    helix_signature = placement_signature(helix.placement)
    helix_serving = build_serving_graph(
        context.topology,
        context.simulation.model,
        helix.placement,
        context.throughput_provider,
    )
    target = config.throughput_ratio_rho * helix.validated_max_flow

    rows: list[dict[str, object]] = []
    ratios: list[float] = []
    routing_placements = []
    routing_flows = []
    joint_placements = []
    joint_edge_sets = []
    previous_edges = None
    for sweep_value in config.sweep_values:
        intensities = carbon_intensities(config, sweep_value)
        routing_carbon_model = CarbonCostModel.build(
            context.topology,
            context.simulation.model,
            helix.placement,
            context.energy_provider,
            intensities,
            phase=config.phase,
            batch_size=config.batch_size,
        )
        routing = solve_carbon_aware_flow(
            helix_serving, routing_carbon_model, target
        )
        joint = solve_carbon_aware_placement(
            context.topology,
            context.simulation.model,
            context.throughput_provider,
            context.energy_provider,
            intensities,
            target,
            phase=config.phase,
            batch_size=config.batch_size,
        )
        gap = routing_gap(
            routing.metrics.carbon_g_per_second, joint.carbon_g_per_second
        )
        joint_signature = placement_signature(joint.placement)
        joint_serving = build_serving_graph(
            context.topology,
            context.simulation.model,
            joint.placement,
            context.throughput_provider,
        )
        edges = logical_edge_set(joint_serving)
        edge_delta = 0.0 if previous_edges is None else graph_change(previous_edges, edges)
        previous_edges = edges
        ci_a = float(intensities["A"])
        ci_b = float(intensities["B"])
        ratio = ci_a / ci_b
        ratios.append(ratio)
        routing_placements.append(helix_signature)
        routing_flows.append(routing.metrics.path_flow_share)
        joint_placements.append(joint_signature)
        joint_edge_sets.append(edges)
        rows.append(
            {
                "ci_a": ci_a,
                "ci_b": ci_b,
                "ci_ratio": ratio,
                "F_H": helix.validated_max_flow,
                "rho": config.throughput_ratio_rho,
                "F_target": target,
                "helix_placement_signature": serialize_placement_signature(helix_signature),
                "routing_throughput": routing.metrics.throughput,
                "routing_carbon": routing.metrics.carbon_g_per_second,
                "routing_solver_time": routing.solver_time_seconds,
                "carbon_placement_signature": serialize_placement_signature(joint_signature),
                "joint_throughput": joint.achieved_throughput,
                "joint_carbon": joint.carbon_g_per_second,
                "placement_solver_time": joint.solver_time_seconds,
                "routing_gap": gap,
                "routing_sufficient": is_routing_sufficient(
                    gap, config.routing_gap_epsilon
                ),
                "routing_flow_signature": json_float_mapping(
                    routing.metrics.path_flow_share
                ),
                "joint_flow_signature": json_float_mapping(
                    joint.validated_flow.metrics.path_flow_share
                ),
                "active_edges_routing": json_edge_mapping(
                    routing.metrics.positive_flow_edges
                ),
                "active_edges_joint": json_edge_mapping(
                    joint.validated_flow.metrics.positive_flow_edges
                ),
                "graph_change_from_previous": edge_delta,
            }
        )

    routing_points = detect_routing_breakpoints(
        ratios, routing_placements, routing_flows
    )
    placement_points = detect_placement_breakpoints(
        ratios, joint_placements, joint_edge_sets
    )
    routing_frame = pd.DataFrame(
        [
            {
                "left_ci_ratio": point.left_ci_ratio,
                "right_ci_ratio": point.right_ci_ratio,
                "placement": serialize_placement_signature(point.placement),
                "flow_l1_change": point.flow_l1_change,
            }
            for point in routing_points
        ],
        columns=["left_ci_ratio", "right_ci_ratio", "placement", "flow_l1_change"],
    )
    placement_frame = pd.DataFrame(
        [
            {
                "left_ci_ratio": point.left_ci_ratio,
                "right_ci_ratio": point.right_ci_ratio,
                "old_placement": serialize_placement_signature(point.old_placement),
                "new_placement": serialize_placement_signature(point.new_placement),
                "migration_layer_count": point.migration_layer_count,
                "graph_edge_change": point.graph_edge_change,
            }
            for point in placement_points
        ],
        columns=[
            "left_ci_ratio",
            "right_ci_ratio",
            "old_placement",
            "new_placement",
            "migration_layer_count",
            "graph_edge_change",
        ],
    )
    summary = pd.DataFrame(rows)
    summary_path = _destination(config.strategy_sweep_csv, output_dir)
    routing_path = _destination(config.routing_breakpoints_csv, output_dir)
    placement_path = _destination(config.placement_breakpoints_csv, output_dir)
    figure_path = _destination(config.transition_figure, output_dir)
    for path in (summary_path, routing_path, placement_path, figure_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    routing_frame.to_csv(routing_path, index=False)
    placement_frame.to_csv(placement_path, index=False)
    _plot_transitions(summary, figure_path, config.routing_gap_epsilon)
    return StrategySweepOutputs(
        summary,
        routing_frame,
        placement_frame,
        summary_path,
        routing_path,
        placement_path,
        figure_path,
    )


def main() -> None:
    outputs = run_routing_placement_sweep()
    print("=== Static Routing-Placement Sweep ===")
    print(f"CI points: {len(outputs.summary)}")
    print(f"Routing breakpoints: {len(outputs.routing_breakpoints)}")
    print(f"Placement breakpoints: {len(outputs.placement_breakpoints)}")
    print(f"Maximum routing gap: {outputs.summary['routing_gap'].max():.4%}")
    print(f"CSV: {outputs.summary_csv}")
    print(f"Figure: {outputs.transition_figure}")


if __name__ == "__main__":
    main()

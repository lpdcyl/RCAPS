"""CI-ratio by cross-region-bandwidth adaptation phase diagram."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from experiments.phase3_common import (
    carbon_intensities,
    load_phase3_context,
    solve_helix_baseline,
)
from src.analysis.breakpoint import placement_signature, serialize_placement_signature
from src.analysis.routing_gap import is_routing_sufficient, routing_gap
from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import build_serving_graph
from src.graph.topology import with_cross_region_bandwidth
from src.optimizer.carbon_flow import solve_carbon_aware_flow
from src.optimizer.placement_milp import solve_carbon_aware_placement
from src.utils.config import bandwidth_mbps_to_activation_tokens_per_second


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


@dataclass(frozen=True, slots=True)
class PhaseDiagramOutputs:
    summary: pd.DataFrame
    summary_csv: Path
    figure: Path


def _centers_to_edges(values: np.ndarray) -> np.ndarray:
    if len(values) == 1:
        width = max(abs(values[0]) * 0.1, 0.1)
        return np.asarray([values[0] - width, values[0] + width])
    midpoints = (values[:-1] + values[1:]) / 2.0
    return np.concatenate(
        ([values[0] - (midpoints[0] - values[0])], midpoints, [values[-1] + (values[-1] - midpoints[-1])])
    )


def _plot_phase_diagram(summary: pd.DataFrame, destination: Path) -> None:
    ratios = np.asarray(sorted(summary["ci_ratio"].unique()), dtype=float)
    bandwidths = np.asarray(sorted(summary["bandwidth_mbps"].unique()), dtype=float)
    strategy_code = {
        "infeasible": 0,
        "routing_sufficient": 1,
        "placement_beneficial": 2,
    }
    grid = np.zeros((len(bandwidths), len(ratios)), dtype=int)
    for row in summary.itertuples(index=False):
        y = int(np.where(bandwidths == row.bandwidth_mbps)[0][0])
        x = int(np.where(ratios == row.ci_ratio)[0][0])
        grid[y, x] = strategy_code[row.adaptation_strategy]
    colors = ["#9E9E9E", "#0072B2", "#D55E00"]
    labels = ["Infeasible", "Routing sufficient", "Placement beneficial"]
    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.pcolormesh(
        _centers_to_edges(ratios),
        _centers_to_edges(bandwidths),
        grid,
        cmap=ListedColormap(colors),
        norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3),
        shading="flat",
    )
    axis.set_xlabel("Carbon intensity ratio CI_A / CI_B")
    axis.set_ylabel("Cross-region bandwidth (Mbps)")
    axis.legend(
        handles=[Patch(facecolor=color, label=label) for color, label in zip(colors, labels)],
        loc="best",
    )
    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def run_phase_diagram(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
) -> PhaseDiagramOutputs:
    """Sweep CI and cross-region bandwidth with a per-bandwidth Helix baseline."""

    context = load_phase3_context(config_dir)
    config = context.config
    rows: list[dict[str, object]] = []
    for bandwidth in config.bandwidth_mbps_values:
        topology = with_cross_region_bandwidth(context.topology, bandwidth)
        helix = solve_helix_baseline(context, topology)
        helix_signature = placement_signature(helix.placement)
        target = config.throughput_ratio_rho * helix.validated_max_flow
        helix_serving = build_serving_graph(
            topology,
            context.simulation.model,
            helix.placement,
            context.throughput_provider,
        )
        token_capacity = bandwidth_mbps_to_activation_tokens_per_second(
            bandwidth, context.simulation.model.activation_bytes_per_token
        )
        for sweep_value in config.sweep_values:
            intensities = carbon_intensities(config, sweep_value)
            carbon_model = CarbonCostModel.build(
                topology,
                context.simulation.model,
                helix.placement,
                context.energy_provider,
                intensities,
                phase=config.phase,
                batch_size=config.batch_size,
            )
            routing = solve_carbon_aware_flow(helix_serving, carbon_model, target)
            joint = solve_carbon_aware_placement(
                topology,
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
            sufficient = is_routing_sufficient(gap, config.routing_gap_epsilon)
            ci_a = float(intensities["A"])
            ci_b = float(intensities["B"])
            rows.append(
                {
                    "ci_a": ci_a,
                    "ci_b": ci_b,
                    "ci_ratio": ci_a / ci_b,
                    "bandwidth_mbps": bandwidth,
                    "network_capacity_tokens_per_second": token_capacity,
                    "F_H": helix.validated_max_flow,
                    "F_target": target,
                    "helix_placement_signature": serialize_placement_signature(
                        helix_signature
                    ),
                    "routing_carbon": routing.metrics.carbon_g_per_second,
                    "joint_carbon": joint.carbon_g_per_second,
                    "routing_gap": gap,
                    "adaptation_strategy": (
                        "routing_sufficient" if sufficient else "placement_beneficial"
                    ),
                    "carbon_placement_signature": serialize_placement_signature(
                        placement_signature(joint.placement)
                    ),
                    "routing_solver_time": routing.solver_time_seconds,
                    "placement_solver_time": joint.solver_time_seconds,
                }
            )
    summary = pd.DataFrame(rows)
    csv_path = (
        PROJECT_ROOT / config.phase_diagram_csv
        if output_dir is None
        else Path(output_dir) / Path(config.phase_diagram_csv).name
    )
    figure_path = (
        PROJECT_ROOT / config.phase_diagram_figure
        if output_dir is None
        else Path(output_dir) / Path(config.phase_diagram_figure).name
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(csv_path, index=False)
    _plot_phase_diagram(summary, figure_path)
    return PhaseDiagramOutputs(summary, csv_path, figure_path)


def main() -> None:
    outputs = run_phase_diagram()
    counts = outputs.summary["adaptation_strategy"].value_counts().to_dict()
    print("=== CI x Bandwidth Phase Diagram ===")
    print(f"Points: {len(outputs.summary)}")
    print(f"Strategies: {counts}")
    print(f"CSV: {outputs.summary_csv}")
    print(f"Figure: {outputs.figure}")


if __name__ == "__main__":
    main()

"""Phase 2 carbon-intensity sweep with fixed layer placement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.carbon.config import load_energy_provider, load_phase2_experiment
from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import build_serving_graph
from src.optimizer.carbon_flow import (
    CarbonFlowResult,
    FlowCarbonMetrics,
    scaled_helix_reference_flow,
    solve_carbon_aware_flow,
)
from src.optimizer.maxflow import solve_max_flow
from src.simulator.simulator import load_simulation_inputs, load_topology


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "configs"


@dataclass(frozen=True, slots=True)
class SweepOutputs:
    """In-memory results and persisted artifact paths."""

    summary: pd.DataFrame
    path_flows: pd.DataFrame
    summary_csv: Path
    path_csv: Path
    flow_share_figure: Path


def _path_column(prefix: str, path: str) -> str:
    return f"{prefix}_path_{path.replace('->', '_')}_flow_share"


def _path_rows(
    ci_a: float,
    ci_b: float,
    ci_ratio: float,
    policy: str,
    metrics: FlowCarbonMetrics,
) -> Iterable[dict[str, float | str]]:
    for path, flow in metrics.path_flow_tokens_per_second.items():
        yield {
            "ci_a": ci_a,
            "ci_b": ci_b,
            "ci_ratio": ci_ratio,
            "policy": policy,
            "path": path,
            "flow_tokens_per_second": flow,
            "flow_share": metrics.path_flow_share[path],
        }


def _plot_flow_shares(summary: pd.DataFrame, destination: Path) -> None:
    share_columns = sorted(
        column
        for column in summary.columns
        if column.startswith("carbon_path_") and column.endswith("_flow_share")
    )
    figure, axis = plt.subplots(figsize=(9, 5.5))
    for column in share_columns:
        label = column.removeprefix("carbon_path_").removesuffix("_flow_share")
        axis.plot(summary["ci_ratio"], summary[column], marker="o", label=label)
    axis.set_xlabel("Carbon intensity ratio CI_A / CI_B")
    axis.set_ylabel("Carbon-aware path flow share")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(True, alpha=0.3)
    axis.legend(title="GPU path", bbox_to_anchor=(1.02, 1), loc="upper left")
    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def run_ci_sweep(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
) -> SweepOutputs:
    """Run the configured CI sweep and save reproducible CSV and PNG outputs."""

    config_root = Path(config_dir)
    phase1 = load_simulation_inputs(config_root)
    phase2 = load_phase2_experiment(config_root)
    energy_provider, _ = load_energy_provider(config_root)
    if phase2.placement_name not in phase1.placements:
        raise ValueError(f"Unknown Phase 2 placement: {phase2.placement_name}")

    topology = load_topology(
        config_root, phase2.network_topology_file, phase1.gpus
    )
    placement = phase1.placements[phase2.placement_name]
    serving = build_serving_graph(
        topology,
        phase1.model,
        placement,
        phase1.throughput_provider,
        allow_partial_inference=phase1.allow_partial_inference,
    )
    helix = solve_max_flow(serving)
    target = phase2.throughput_ratio_rho * helix.max_flow_value

    summary_rows: list[dict[str, float | str]] = []
    path_rows: list[dict[str, float | str]] = []
    optimized_results: list[CarbonFlowResult] = []
    for sweep_ci in phase2.sweep_values:
        intensities = dict(phase2.fixed_carbon_intensity)
        intensities[phase2.sweep_region] = sweep_ci
        carbon_model = CarbonCostModel.build(
            topology,
            phase1.model,
            placement,
            energy_provider,
            intensities,
            phase=phase2.phase,
            batch_size=phase2.batch_size,
        )
        reference = scaled_helix_reference_flow(
            serving, helix, carbon_model, target
        )
        optimized = solve_carbon_aware_flow(serving, carbon_model, target)
        optimized_results.append(optimized)

        ci_b = float(intensities["B"])
        ci_a = float(intensities["A"])
        ratio = ci_a / ci_b
        reduction = (
            (reference.carbon_g_per_second - optimized.metrics.carbon_g_per_second)
            / reference.carbon_g_per_second
            * 100.0
        )
        row: dict[str, float | str] = {
            "ci_a": ci_a,
            "ci_b": ci_b,
            "ci_ratio": ratio,
            "placement": placement.name,
            "rho": phase2.throughput_ratio_rho,
            "helix_max_flow": helix.max_flow_value,
            "throughput_target": target,
            "throughput": optimized.metrics.throughput,
            "reference_carbon_g_per_second": reference.carbon_g_per_second,
            "carbon_cost_g_per_second": optimized.metrics.carbon_g_per_second,
            "reference_carbon_g_per_1000_tokens": reference.carbon_g_per_1000_tokens,
            "carbon_g_per_1000_tokens": optimized.metrics.carbon_g_per_1000_tokens,
            "carbon_reduction_percent": reduction,
            "solver_time_seconds": optimized.solver_time_seconds,
            "active_logical_edges": len(serving.graph.edges),
        }
        for path, share in reference.path_flow_share.items():
            row[_path_column("reference", path)] = share
        for path, share in optimized.metrics.path_flow_share.items():
            row[_path_column("carbon", path)] = share
        summary_rows.append(row)
        path_rows.extend(_path_rows(ci_a, ci_b, ratio, "reference", reference))
        path_rows.extend(
            _path_rows(ci_a, ci_b, ratio, "carbon_aware", optimized.metrics)
        )

    summary = pd.DataFrame(summary_rows).fillna(0.0)
    paths = pd.DataFrame(path_rows)
    if output_dir is None:
        summary_path = PROJECT_ROOT / phase2.summary_csv
        path_path = PROJECT_ROOT / phase2.path_csv
        figure_path = PROJECT_ROOT / phase2.flow_share_figure
    else:
        root = Path(output_dir)
        summary_path = root / Path(phase2.summary_csv).name
        path_path = root / Path(phase2.path_csv).name
        figure_path = root / Path(phase2.flow_share_figure).name
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    path_path.parent.mkdir(parents=True, exist_ok=True)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    paths.to_csv(path_path, index=False)
    _plot_flow_shares(summary, figure_path)
    return SweepOutputs(
        summary=summary,
        path_flows=paths,
        summary_csv=summary_path,
        path_csv=path_path,
        flow_share_figure=figure_path,
    )


def main() -> None:
    """CLI entry point for ``python -m experiments.exp_ci_sweep``."""

    outputs = run_ci_sweep()
    summary = outputs.summary
    print("=== Phase 2: Fixed-Placement Carbon-Aware Flow ===")
    print(f"CI points: {len(summary)}")
    print(f"Placement: {summary.iloc[0]['placement']}")
    print(f"Helix max flow: {summary.iloc[0]['helix_max_flow']:.3f} token/s")
    print(f"Throughput target: {summary.iloc[0]['throughput_target']:.3f} token/s")
    for index in sorted({0, len(summary) // 2, len(summary) - 1}):
        row = summary.iloc[index]
        print(
            f"CI_A={row['ci_a']:.0f}, CI_B={row['ci_b']:.0f}, "
            f"ratio={row['ci_ratio']:.2f}, throughput={row['throughput']:.3f}, "
            f"carbon={row['carbon_g_per_1000_tokens']:.6f} g/1000 tokens, "
            f"saving={row['carbon_reduction_percent']:.2f}%"
        )
    print(f"Summary CSV: {outputs.summary_csv}")
    print(f"Path CSV: {outputs.path_csv}")
    print(f"Flow-share figure: {outputs.flow_share_figure}")


if __name__ == "__main__":
    main()

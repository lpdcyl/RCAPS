"""End-to-end staged Phase 3.5 routing-sufficiency experiment suite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments.exp_placement_cost_curves import (
    PlacementCostCurveOutputs,
    run_placement_cost_curves,
)
from experiments.exp_rho_sensitivity import RhoSensitivityOutputs, run_rho_sensitivity
from experiments.phase35_common import (
    CONFIG_DIR,
    Phase35Context,
    SweepRun,
    aggregate_sweep,
    boundary_rows,
    energy_provider_for_scenario,
    load_phase35_context,
    output_path,
    run_ci_sweep,
    scenario_topology,
    validate_run_boundaries,
)


@dataclass(frozen=True, slots=True)
class Phase35Outputs:
    summary: pd.DataFrame
    boundaries: pd.DataFrame
    rho: RhoSensitivityOutputs
    gpu_sensitivity: pd.DataFrame
    network_sensitivity: pd.DataFrame
    energy_sensitivity: pd.DataFrame
    cost_curves: PlacementCostCurveOutputs
    summary_csv: Path
    boundaries_csv: Path
    gpu_csv: Path
    gpu_figure: Path
    network_csv: Path
    network_figure: Path
    energy_csv: Path
    representative_network_scenarios: tuple[str, str]


def _write_gpu_sensitivity(
    context: Phase35Context,
    runs: list[SweepRun],
    output_dir: str | Path | None,
) -> tuple[pd.DataFrame, Path, Path]:
    frame = pd.DataFrame([aggregate_sweep(run) for run in runs])
    csv_path = output_path(context, "gpu_csv", output_dir)
    figure_path = output_path(context, "gpu_figure", output_dir)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    axis.bar(frame["scenario"], 100.0 * frame["max_routing_gap"], color="#0072B2")
    axis.set_xlabel("Synthetic GPU composition scenario")
    axis.set_ylabel("Maximum Routing Gap (%)")
    axis.tick_params(axis="x", rotation=18)
    axis.grid(True, axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    return frame, csv_path, figure_path


def _representative_scenarios(
    context: Phase35Context, gpu_frame: pd.DataFrame
) -> tuple[str, str]:
    asymmetric = gpu_frame[
        gpu_frame["scenario"] != context.config.baseline_scenario
    ].sort_values(["max_routing_gap", "scenario"])
    if asymmetric.empty:
        raise ValueError("Network sensitivity requires asymmetric GPU scenarios")
    small = str(asymmetric.iloc[0]["scenario"])
    large = str(asymmetric.iloc[-1]["scenario"])
    if small == large and len(asymmetric) > 1:
        large = str(asymmetric.iloc[-2]["scenario"])
    return small, large


def _write_network_sensitivity(
    context: Phase35Context,
    runs: list[SweepRun],
    scenarios: tuple[str, str],
    output_dir: str | Path | None,
) -> tuple[pd.DataFrame, Path, Path]:
    frame = pd.concat([run.summary for run in runs], ignore_index=True)
    csv_path = output_path(context, "network_csv", output_dir)
    figure_path = output_path(context, "network_figure", output_dir)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    _plot_network_sensitivity(frame, scenarios, figure_path)
    return frame, csv_path, figure_path


def _centers_to_edges(values: np.ndarray) -> np.ndarray:
    """Convert strictly increasing sample centers to plotting cell edges."""

    if len(values) == 1:
        width = max(abs(float(values[0])) * 0.1, 0.5)
        return np.asarray([values[0] - width, values[0] + width])
    midpoints = (values[:-1] + values[1:]) / 2.0
    return np.concatenate(
        ([values[0] - (midpoints[0] - values[0])], midpoints, [values[-1] + (values[-1] - midpoints[-1])])
    )


def _plot_network_sensitivity(
    frame: pd.DataFrame, scenarios: tuple[str, str], figure_path: Path
) -> None:
    """Render continuous Routing Gap values on their actual sampled grid."""

    figure, axes = plt.subplots(
        1,
        len(scenarios),
        figsize=(7.2 * len(scenarios), 5.2),
        squeeze=False,
        layout="constrained",
    )
    image = None
    maximum = 100.0 * float(frame["routing_gap"].max())
    for axis, scenario in zip(axes[0], scenarios):
        subset = frame[frame["scenario"] == scenario]
        pivot = subset.pivot(
            index="capacity_tokens_per_second", columns="ci_ratio", values="routing_gap"
        ).sort_index()
        ratios = pivot.columns.to_numpy(dtype=float)
        capacities = pivot.index.to_numpy(dtype=float)
        image = axis.pcolormesh(
            _centers_to_edges(ratios),
            _centers_to_edges(capacities),
            100.0 * pivot.to_numpy(),
            cmap="viridis",
            shading="flat",
            vmin=0.0,
            vmax=maximum,
        )
        axis.set_title(scenario)
        axis.set_xlabel("CI_A / CI_B")
        axis.set_ylabel("Cross-region capacity (token/s)")
    if image is not None:
        figure.colorbar(
            image,
            ax=axes.ravel().tolist(),
            label="Routing Gap (%)",
            pad=0.025,
            shrink=0.92,
        )
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)


def _write_energy_sensitivity(
    context: Phase35Context,
    runs: list[SweepRun],
    output_dir: str | Path | None,
) -> tuple[pd.DataFrame, Path]:
    rows = []
    for run in runs:
        row = aggregate_sweep(run)
        validated = run.summary.loc[
            run.summary["validated_cost_crossing"], "ci_ratio"
        ].tolist()
        row["validated_boundary_positions"] = ";".join(
            f"{float(value):.6g}" for value in validated
        )
        row["carbon_placement_signatures"] = int(
            run.summary["carbon_placement"].nunique()
        )
        row["sensitivity_status"] = "synthetic_energy_sensitivity"
        rows.append(row)
    frame = pd.DataFrame(rows)
    csv_path = output_path(context, "energy_csv", output_dir)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    return frame, csv_path


def run_phase35(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
) -> Phase35Outputs:
    """Run Stage A, Stage B, selective Stage C, and OAT energy sensitivity."""

    context = load_phase35_context(config_dir)
    config = context.config
    boundary_records: list[dict[str, object]] = []

    rho_outputs = run_rho_sensitivity(
        config_dir, output_dir=output_dir, context=context
    )
    all_runs: list[SweepRun] = list(rho_outputs.runs)
    boundary_records.extend(rho_outputs.boundaries)
    baseline_run = next(
        run for run in rho_outputs.runs if np.isclose(run.rho, config.baseline_rho)
    )

    gpu_runs: list[SweepRun] = []
    for scenario in config.gpu_scenarios:
        if scenario == config.baseline_scenario:
            run = baseline_run
        else:
            run = run_ci_sweep(
                context,
                study="gpu_sensitivity",
                scenario=scenario,
                rho=config.baseline_rho,
                topology=scenario_topology(context, scenario),
                capacity_tokens_per_second=config.baseline_capacity_tokens_per_second,
            )
            run, boundaries = validate_run_boundaries(context, run)
            all_runs.append(run)
            boundary_records.extend(boundary_rows(run, boundaries))
        gpu_runs.append(run)
    gpu_frame, gpu_csv, gpu_figure = _write_gpu_sensitivity(
        context, gpu_runs, output_dir
    )

    network_scenarios = _representative_scenarios(context, gpu_frame)
    network_runs: list[SweepRun] = []
    for scenario in network_scenarios:
        topology = scenario_topology(context, scenario)
        for capacity in config.network_capacity_tokens_per_second:
            run = run_ci_sweep(
                context,
                study="network_sensitivity",
                scenario=scenario,
                rho=config.baseline_rho,
                topology=topology,
                capacity_tokens_per_second=capacity,
            )
            run, boundaries = validate_run_boundaries(context, run)
            network_runs.append(run)
            all_runs.append(run)
            boundary_records.extend(boundary_rows(run, boundaries))
    network_frame, network_csv, network_figure = _write_network_sensitivity(
        context, network_runs, network_scenarios, output_dir
    )

    energy_runs: list[SweepRun] = []
    baseline_topology = scenario_topology(context, config.baseline_scenario)
    # One common 1.0x control avoids duplicating the identical baseline for each type.
    energy_control = run_ci_sweep(
        context,
        study="energy_sensitivity",
        scenario=config.baseline_scenario,
        rho=config.baseline_rho,
        topology=baseline_topology,
        energy_provider=energy_provider_for_scenario(context, None, 1.0),
        energy_scenario="baseline_1.0x",
        capacity_tokens_per_second=config.baseline_capacity_tokens_per_second,
    )
    energy_control, boundaries = validate_run_boundaries(context, energy_control)
    energy_runs.append(energy_control)
    all_runs.append(energy_control)
    boundary_records.extend(boundary_rows(energy_control, boundaries))
    for gpu_type in config.energy_gpu_types:
        for multiplier in config.energy_multipliers:
            if np.isclose(multiplier, 1.0):
                continue
            label = f"{gpu_type}_{multiplier:.2f}x"
            run = run_ci_sweep(
                context,
                study="energy_sensitivity",
                scenario=config.baseline_scenario,
                rho=config.baseline_rho,
                topology=baseline_topology,
                energy_provider=energy_provider_for_scenario(
                    context, gpu_type, multiplier
                ),
                energy_scenario=label,
                capacity_tokens_per_second=config.baseline_capacity_tokens_per_second,
            )
            run, boundaries = validate_run_boundaries(context, run)
            energy_runs.append(run)
            all_runs.append(run)
            boundary_records.extend(boundary_rows(run, boundaries))
    energy_frame, energy_csv = _write_energy_sensitivity(
        context, energy_runs, output_dir
    )

    cost_curves = run_placement_cost_curves(
        config_dir,
        output_dir=output_dir,
        context=context,
        baseline_run=baseline_run,
    )

    summary = pd.concat([run.summary for run in all_runs], ignore_index=True)
    summary_path = output_path(context, "summary_csv", output_dir)
    boundaries_path = output_path(context, "boundaries_csv", output_dir)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    boundaries_frame = pd.DataFrame(boundary_records)
    boundaries_frame.to_csv(boundaries_path, index=False)
    return Phase35Outputs(
        summary,
        boundaries_frame,
        rho_outputs,
        gpu_frame,
        network_frame,
        energy_frame,
        cost_curves,
        summary_path,
        boundaries_path,
        gpu_csv,
        gpu_figure,
        network_csv,
        network_figure,
        energy_csv,
        network_scenarios,
    )


def main() -> None:
    outputs = run_phase35()
    maximum = outputs.summary.loc[outputs.summary["routing_gap"].idxmax()]
    print("=== Phase 3.5 Routing Sufficiency and Placement Necessity ===")
    print(f"Points: {len(outputs.summary)}")
    print(
        "Maximum Routing Gap: "
        f"{float(maximum['routing_gap']):.4%} "
        f"({maximum['study']}, {maximum['scenario']}, rho={maximum['rho']}, "
        f"energy={maximum['energy_scenario']}, "
        f"capacity={maximum['capacity_tokens_per_second']} token/s, "
        f"CI ratio={maximum['ci_ratio']})"
    )
    print(
        "Validated / degenerate boundaries: "
        f"{int(outputs.boundaries.get('validated_placement_boundary', pd.Series(dtype=bool)).sum())} / "
        f"{int(outputs.boundaries.get('degenerate', pd.Series(dtype=bool)).sum())}"
    )
    print(f"Summary: {outputs.summary_csv}")
    print(f"Boundaries: {outputs.boundaries_csv}")


if __name__ == "__main__":
    main()

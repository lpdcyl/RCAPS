"""Candidate fixed-placement cost curves and their global optimum envelope."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from experiments.phase35_common import (
    CONFIG_DIR,
    Phase35Context,
    SweepRun,
    load_phase35_context,
    output_path,
    run_ci_sweep,
    scenario_topology,
)
from experiments.phase3_common import carbon_intensities
from src.analysis.breakpoint import placement_signature, serialize_placement_signature
from src.carbon.model import CarbonCostModel
from src.graph.serving_graph import LayerPlacement, build_serving_graph
from src.optimizer.carbon_flow import solve_carbon_aware_flow


@dataclass(frozen=True, slots=True)
class PlacementCostCurveOutputs:
    summary: pd.DataFrame
    summary_csv: Path
    figure: Path


def _baseline_run(context: Phase35Context) -> SweepRun:
    config = context.config
    return run_ci_sweep(
        context,
        study="cost_curves",
        scenario=config.baseline_scenario,
        rho=config.baseline_rho,
        topology=scenario_topology(context, config.baseline_scenario),
        capacity_tokens_per_second=config.baseline_capacity_tokens_per_second,
    )


def run_placement_cost_curves(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
    context: Phase35Context | None = None,
    baseline_run: SweepRun | None = None,
) -> PlacementCostCurveOutputs:
    """Evaluate every unique carbon-optimal placement plus Helix over all CI."""

    context = load_phase35_context(config_dir) if context is None else context
    run = _baseline_run(context) if baseline_run is None else baseline_run
    model = context.phase3.simulation.model
    provider = context.phase3.throughput_provider
    phase_config = context.phase3.config
    candidates: dict[tuple[tuple[str, int, int], ...], LayerPlacement] = {
        placement_signature(run.helix.placement): run.helix.placement
    }
    for placement in run.placements:
        candidates.setdefault(placement_signature(placement), placement)
    ordered = sorted(candidates.items())
    helix_signature = placement_signature(run.helix.placement)
    rows: list[dict[str, object]] = []
    target = run.rho * run.helix.validated_max_flow
    for placement_index, (signature, placement) in enumerate(ordered):
        serving = build_serving_graph(run.topology, model, placement, provider)
        for sweep_value in phase_config.sweep_values:
            intensities = carbon_intensities(phase_config, sweep_value)
            carbon = CarbonCostModel.build(
                run.topology,
                model,
                placement,
                run.energy_provider,
                intensities,
                phase=phase_config.phase,
                batch_size=phase_config.batch_size,
            )
            result = solve_carbon_aware_flow(serving, carbon, target)
            rows.append(
                {
                    "placement_id": f"P{placement_index}",
                    "placement_signature": serialize_placement_signature(signature),
                    "is_helix_placement": signature == helix_signature,
                    "ci_a": float(intensities["A"]),
                    "ci_b": float(intensities["B"]),
                    "ci_ratio": float(intensities["A"]) / float(intensities["B"]),
                    "carbon_objective": result.metrics.carbon_g_per_second,
                    "F_target": target,
                }
            )
    frame = pd.DataFrame(rows)
    envelope = frame.groupby("ci_ratio")["carbon_objective"].transform("min")
    frame["global_optimum_envelope"] = envelope
    frame["on_global_optimum_envelope"] = (
        (frame["carbon_objective"] - envelope).abs()
        <= envelope.abs().clip(lower=1e-30) * 1e-8
    )
    csv_path = output_path(context, "cost_curves_csv", output_dir)
    figure_path = output_path(context, "cost_curves_figure", output_dir)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    figure, axis = plt.subplots(figsize=(9, 5.5))
    for placement_id, group in frame.groupby("placement_id", sort=True):
        suffix = " (Helix)" if bool(group["is_helix_placement"].iloc[0]) else ""
        axis.plot(
            group["ci_ratio"],
            group["carbon_objective"],
            linewidth=1.2,
            alpha=0.72,
            label=f"{placement_id}{suffix}",
        )
    envelope_frame = (
        frame[["ci_ratio", "global_optimum_envelope"]]
        .drop_duplicates()
        .sort_values("ci_ratio")
    )
    axis.plot(
        envelope_frame["ci_ratio"],
        envelope_frame["global_optimum_envelope"],
        color="black",
        linewidth=2.8,
        linestyle="--",
        label="Global optimum envelope",
    )
    axis.set_xlabel("Carbon intensity ratio CI_A / CI_B")
    axis.set_ylabel("Carbon objective (g/s)")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    return PlacementCostCurveOutputs(frame, csv_path, figure_path)


def main() -> None:
    outputs = run_placement_cost_curves()
    print("=== Phase 3.5 Candidate Placement Cost Curves ===")
    print(f"Candidates: {outputs.summary['placement_id'].nunique()}")
    print(f"CSV: {outputs.summary_csv}")
    print(f"Figure: {outputs.figure}")


if __name__ == "__main__":
    main()

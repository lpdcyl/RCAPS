"""Stage A: throughput-target (rho) sensitivity on the symmetric control."""

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
    aggregate_sweep,
    boundary_rows,
    load_phase35_context,
    output_path,
    run_ci_sweep,
    scenario_topology,
    validate_run_boundaries,
)


@dataclass(frozen=True, slots=True)
class RhoSensitivityOutputs:
    summary: pd.DataFrame
    runs: tuple[SweepRun, ...]
    boundaries: tuple[dict[str, object], ...]
    summary_csv: Path
    figure: Path


def run_rho_sensitivity(
    config_dir: str | Path = CONFIG_DIR,
    *,
    output_dir: str | Path | None = None,
    context: Phase35Context | None = None,
) -> RhoSensitivityOutputs:
    context = load_phase35_context(config_dir) if context is None else context
    config = context.config
    topology = scenario_topology(context, config.baseline_scenario)
    runs: list[SweepRun] = []
    all_boundary_rows: list[dict[str, object]] = []
    for rho in config.rhos:
        run = run_ci_sweep(
            context,
            study="rho_sensitivity",
            scenario=config.baseline_scenario,
            rho=rho,
            topology=topology,
            capacity_tokens_per_second=config.baseline_capacity_tokens_per_second,
        )
        run, boundaries = validate_run_boundaries(context, run)
        runs.append(run)
        all_boundary_rows.extend(boundary_rows(run, boundaries))
    frame = pd.DataFrame([aggregate_sweep(run) for run in runs])
    csv_path = output_path(context, "rho_csv", output_dir)
    figure_path = output_path(context, "rho_figure", output_dir)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    axis.plot(frame["rho"], 100.0 * frame["max_routing_gap"], marker="o")
    axis.set_xlabel("Throughput target ratio rho")
    axis.set_ylabel("Maximum Routing Gap (%)")
    axis.grid(True, alpha=0.25)
    figure.tight_layout()
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    return RhoSensitivityOutputs(
        frame, tuple(runs), tuple(all_boundary_rows), csv_path, figure_path
    )


def main() -> None:
    outputs = run_rho_sensitivity()
    print("=== Phase 3.5 Rho Sensitivity ===")
    print(outputs.summary.to_string(index=False))
    print(f"CSV: {outputs.summary_csv}")
    print(f"Figure: {outputs.figure}")


if __name__ == "__main__":
    main()

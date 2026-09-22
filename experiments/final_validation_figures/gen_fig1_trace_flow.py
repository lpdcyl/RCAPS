"""Figure 1: historical carbon trace and aggregate path allocation."""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import pandas as pd

from experiments.final_validation_figures.paper_plot_style import COLORS, OUT, save_pair, style


def main() -> None:
    style()
    frame = pd.read_csv(OUT / "historical_ci_timeseries.csv")
    subset = frame[frame.load_profile == "medium"].sort_values("timestamp")
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 5.5), sharex=True, layout="constrained")
    axes[0].plot(range(len(subset)), subset.carbon_intensity_g_per_kwh, color=COLORS[0], linewidth=1.8)
    axes[0].set_ylabel("GB CI (gCO2e/kWh)")
    paths: dict[str, list[float]] = {}
    for raw in subset.dynamic_path_flow_share:
        values = json.loads(raw)
        for path in set(paths) | set(values):
            paths.setdefault(path, []).append(float(values.get(path, 0.0)))
    for index, (path, values) in enumerate(sorted(paths.items())):
        axes[1].plot(range(len(values)), values, linewidth=1.5, label=path)
    axes[1].set_xlabel("Historical 30-minute interval")
    axes[1].set_ylabel("Dynamic path share")
    axes[1].set_ylim(0, 1)
    axes[1].legend(frameon=False, fontsize=8, ncol=2)
    save_pair(fig, "final_validation_fig1_trace_flow")


if __name__ == "__main__":
    main()

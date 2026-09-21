"""Fig. 1: dynamic carbon reduction across trace and GPU scenarios."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.challenge3_figures.paper_plot_style import (
    COLORS,
    DATA,
    save_pair,
    style,
)


def main() -> None:
    style()
    frame = pd.read_csv(DATA)
    table = frame.pivot_table(
        index="trace", columns="gpu_scenario", values="dynamic_reduction_vs_helix", aggfunc="mean"
    )
    table = table.loc[["constant", "step", "periodic", "slow_drift", "noisy_boundary"]]
    scenarios = ["commodity_region", "moderate_asymmetric", "high_asymmetric"]
    colors = [COLORS["blue"], COLORS["orange"], COLORS["vermillion"]]
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    x = range(len(table.index))
    width = 0.24
    for offset, scenario, color in zip((-width, 0, width), scenarios, colors):
        ax.bar([value + offset for value in x], 100.0 * table[scenario], width, label=scenario, color=color)
    ax.set_xticks(list(x), ["constant", "step", "periodic", "slow drift", "noisy boundary"], rotation=18, ha="right")
    ax.set_ylabel("Carbon reduction vs. static Helix (%)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    save_pair(fig, "challenge3_fig1_dynamic_reduction")


if __name__ == "__main__":
    main()

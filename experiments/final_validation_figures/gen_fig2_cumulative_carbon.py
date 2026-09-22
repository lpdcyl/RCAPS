"""Figure 2: cumulative historical carbon for representative loads."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.final_validation_figures.paper_plot_style import COLORS, OUT, save_pair, style


def main() -> None:
    style()
    frame = pd.read_csv(OUT / "historical_ci_timeseries.csv").sort_values(["load_profile", "timestamp"])
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    for index, (load, group) in enumerate(frame.groupby("load_profile", sort=False)):
        cumulative = group.dynamic_carbon_g_per_second.cumsum()
        ax.plot(range(len(group)), cumulative, linewidth=1.8, label=load, color=COLORS[index])
    ax.set_xlabel("Historical 30-minute interval")
    ax.set_ylabel("Cumulative dynamic carbon (g)")
    ax.legend(frameon=False, ncol=3)
    save_pair(fig, "final_validation_fig2_cumulative_carbon")


if __name__ == "__main__":
    main()

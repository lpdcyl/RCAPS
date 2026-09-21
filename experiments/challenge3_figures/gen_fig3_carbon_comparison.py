"""Fig. 3: aggregate carbon comparison for the four scheduling strategies."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.challenge3_figures.paper_plot_style import COLORS, DATA, save_pair, style


def main() -> None:
    style()
    frame = pd.read_csv(DATA)
    columns = {
        "static_helix_carbon": "Static Helix",
        "static_routing_carbon": "Static carbon routing",
        "dynamic_carbon": "Dynamic carbon flow",
        "dynamic_dispatch_carbon": "Dynamic + dispatch",
    }
    means = frame[list(columns)].mean().rename(index=columns)
    colors = [COLORS["black"], COLORS["orange"], COLORS["blue"], COLORS["green"]]
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.bar(means.index, means.values, color=colors)
    ax.set_ylabel("Integrated operational carbon (g)")
    ax.tick_params(axis="x", rotation=18)
    ax.set_ylim(bottom=0)
    save_pair(fig, "challenge3_fig3_carbon_comparison")


if __name__ == "__main__":
    main()

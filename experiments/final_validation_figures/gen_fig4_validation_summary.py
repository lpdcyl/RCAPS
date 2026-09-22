"""Figure 4: historical reduction and placement interventions by load."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.final_validation_figures.paper_plot_style import COLORS, OUT, save_pair, style


def main() -> None:
    style()
    frame = pd.read_csv(OUT / "historical_ci_results.csv")
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.8), layout="constrained")
    axes[0].bar(frame.load_profile, 100.0 * frame.dynamic_reduction_vs_static_helix, color=COLORS[0])
    axes[0].set_ylabel("Dynamic reduction vs static Helix (%)")
    axes[0].set_xlabel("Load profile")
    axes[1].bar(frame.load_profile, frame.flow_reallocations, color=COLORS[1], label="Flow reallocations")
    axes[1].bar(frame.load_profile, frame.accepted_placement_changes, color=COLORS[2], label="Accepted placement changes")
    axes[1].set_ylabel("Count over one day")
    axes[1].set_xlabel("Load profile")
    axes[1].set_ylim(bottom=0, top=max(1.0, float(frame[["flow_reallocations", "accepted_placement_changes"]].to_numpy().max()) * 1.2))
    for index, row in frame.iterrows():
        axes[1].text(index, 0.03, f"{int(row.flow_reallocations)} / {int(row.accepted_placement_changes)}", ha="center", va="bottom", fontsize=8)
    axes[1].legend(frameon=False, fontsize=8)
    save_pair(fig, "final_validation_fig4_summary")


if __name__ == "__main__":
    main()

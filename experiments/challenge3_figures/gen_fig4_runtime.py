"""Fig. 4: measured per-case runtime of the scheduler components."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.challenge3_figures.paper_plot_style import COLORS, OUT, save_pair, style


def main() -> None:
    style()
    path = OUT / "challenge3_runtime_summary.csv"
    frame = pd.read_csv(path)
    labels = {
        "scheduler": "Scheduler",
        "dispatch": "Dispatch",
        "slow_cbgp": "Slow CBGP",
        "always_replace_oracle": "Joint re-place oracle",
    }
    frame["label"] = frame["method"].map(labels)
    frame = frame.set_index("label").loc[list(labels.values())]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    colors = [COLORS["blue"], COLORS["green"], COLORS["purple"], COLORS["vermillion"]]
    ax.bar(frame.index, frame["median_seconds"], color=colors)
    ax.set_ylabel("Median runtime per case (s)")
    ax.tick_params(axis="x", rotation=18)
    ax.set_yscale("log")
    save_pair(fig, "challenge3_fig4_runtime")


if __name__ == "__main__":
    main()

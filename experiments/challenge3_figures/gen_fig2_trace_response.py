"""Fig. 2: temporal response to the piecewise-constant CI traces."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.challenge3_figures.paper_plot_style import COLORS, DATA, save_pair, style


def main() -> None:
    style()
    frame = pd.read_csv(DATA)
    subset = frame[
        (frame["load_profile"] == "medium")
        & (frame["gpu_scenario"] == "high_asymmetric")
        & (frame["network_condition"] == "non_bottleneck")
    ].copy()
    order = ["constant", "step", "periodic", "slow_drift", "noisy_boundary"]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.7), layout="constrained")
    summary = subset.groupby("trace", sort=False)[["flow_reallocations", "dispatch_path_changes"]].mean().reindex(order)
    x = range(len(summary))
    axes[0].bar(x, summary["flow_reallocations"], color=COLORS["blue"])
    axes[1].bar(x, summary["dispatch_path_changes"], color=COLORS["green"])
    for axis in axes:
        axis.set_xticks(list(x), ["constant", "step", "periodic", "slow drift", "noisy boundary"], rotation=22, ha="right")
    axes[0].set_xlabel("CI trace")
    axes[0].set_ylabel("Flow reallocations")
    axes[1].set_xlabel("CI trace")
    axes[1].set_ylabel("Dispatch path changes")
    for axis in axes:
        axis.set_ylim(bottom=0)
    save_pair(fig, "challenge3_fig2_trace_response")


if __name__ == "__main__":
    main()

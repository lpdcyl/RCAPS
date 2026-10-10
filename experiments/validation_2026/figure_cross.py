"""Plot paired 2x2 placement/scheduler outcomes for both 70B topologies."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
METRICS = (
    ("output_throughput_tokens_per_s", "Decode throughput (token/s)"),
    ("ttft_p95_s", "p95 TTFT (s)"),
    ("tpot_p95_s", "p95 TPOT (s/token)"),
)
SCHEDULERS = (("helix", "#666666"), ("rcaps", "#0072B2"))


def main() -> None:
    data = json.loads((HERE / "cross_summary.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2), constrained_layout=True)
    for row, scenario in enumerate(("single", "multi")):
        cells = data["scenarios"][scenario]["cell_mean"]
        for col, (metric, ylabel) in enumerate(METRICS):
            ax = axes[row, col]
            for layout_index, placement in enumerate(("helix", "rcaps")):
                for scheduler_index, (scheduler, color) in enumerate(SCHEDULERS):
                    cell = ("H" if placement == "helix" else "R") + (
                        "H" if scheduler == "helix" else "R")
                    outcome = cells[cell][metric]
                    x = layout_index + (scheduler_index - 0.5) * 0.34
                    if outcome["n"] < len(data["seeds"]):
                        ax.text(x, 0.02, f"n={outcome['n']}/3",
                                ha="center", va="bottom", rotation=90,
                                transform=ax.get_xaxis_transform(), fontsize=8,
                                color=color)
                        continue
                    ax.bar(x, outcome["mean"], width=0.30, color=color,
                           label=f"{scheduler.upper() if scheduler == 'rcaps' else 'Helix'} scheduler"
                           if layout_index == 0 else None)
                    for offset, value in zip((-0.07, 0, 0.07), outcome["by_seed"]):
                        ax.plot(x + offset, value, "o", markersize=3.2,
                                color="black")
            ax.set_xticks((0, 1), ("Helix layout", "RCAPS layout"))
            ax.set_ylabel(ylabel)
            ax.set_title("Single cluster" if row == 0 else "Three clusters")
            ax.grid(axis="y", alpha=0.22)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2,
               bbox_to_anchor=(0.5, 1.05), frameon=False)
    fig.text(0.5, -0.01,
             "Black dots: paired seeds 0/1/2. Single-cluster RCAPS layout + Helix scheduler failed on seed 1; no three-seed bar is shown.",
             ha="center", fontsize=9)
    fig.savefig(HERE / "figures/cross_factorial.png", dpi=220,
                bbox_inches="tight")
    plt.close(fig)
    print(HERE / "figures/cross_factorial.png")


if __name__ == "__main__":
    main()

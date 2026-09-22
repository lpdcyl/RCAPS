"""Figure 3: stage-aware carbon across prefill/decode workload mixes."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from experiments.final_validation_figures.paper_plot_style import COLORS, OUT, save_pair, style


def main() -> None:
    style()
    frame = pd.read_csv(OUT / "stage_aware_results.csv")
    summary = frame.groupby("workload", sort=False)[["decode_only_stage_carbon_g", "stage_weighted_flow_carbon_g", "joint_stage_carbon_g"]].mean()
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    x = range(len(summary))
    width = 0.25
    for offset, column, label, color in [
        (-width, "decode_only_stage_carbon_g", "Decode-only route", COLORS[0]),
        (0.0, "stage_weighted_flow_carbon_g", "Stage-weighted flow", COLORS[1]),
        (width, "joint_stage_carbon_g", "Bounded joint placement", COLORS[2]),
    ]:
        ax.bar([value + offset for value in x], summary[column], width=width, label=label, color=color)
    ax.set_xticks(list(x), ["prefill heavy", "balanced", "decode heavy"])
    ax.set_ylabel("Stage-aware carbon (g)")
    ax.legend(frameon=False, ncol=3, fontsize=8)
    save_pair(fig, "final_validation_fig3_stage_workloads")


if __name__ == "__main__":
    main()

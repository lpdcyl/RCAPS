"""Figure 3: Routing Gap versus CBGP carbon reduction."""

import matplotlib.pyplot as plt
import pandas as pd

from paper_plot_style import COLORS, POINTS_CSV, save_figure


data = pd.read_csv(POINTS_CSV)
fig, axis = plt.subplots(figsize=(4.3, 3.2))
for color, (scenario, frame) in zip(COLORS, data.groupby("gpu_scenario", sort=True)):
    axis.scatter(
        100.0 * frame["routing_gap"],
        100.0 * frame["cbgp_reduction"],
        s=13,
        alpha=0.7,
        color=color,
        label=scenario.replace("_", " "),
        edgecolors="none",
    )
axis.plot([0.0, 20.0], [0.0, 20.0], linestyle="--", color="#666666", linewidth=1.0)
axis.set_xlabel("Routing Gap (%)")
axis.set_ylabel("CBGP reduction vs. routing (%)")
axis.set_xlim(left=-0.2)
axis.set_ylim(bottom=-0.2)
axis.legend(frameon=False, loc="upper left")
save_figure(fig, "figure3_gap_vs_reduction")

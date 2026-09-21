"""Figure 4: CBGP wall-clock runtime versus Joint MILP runtime."""

import matplotlib.pyplot as plt
import pandas as pd

from paper_plot_style import COLORS, POINTS_CSV, save_figure


data = pd.read_csv(POINTS_CSV)
fig, axis = plt.subplots(figsize=(5.7, 3.2))
for color, (scenario, frame) in zip(COLORS, data.groupby("gpu_scenario", sort=True)):
    axis.scatter(
        frame["joint_runtime"],
        frame["cbgp_runtime"],
        s=13,
        alpha=0.65,
        color=color,
        label=scenario.replace("_", " "),
        edgecolors="none",
    )
axis.set_xscale("log")
axis.set_yscale("log")
axis.set_xlabel("Joint MILP wall time (s)")
axis.set_ylabel("CBGP wall time (s)")
axis.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
save_figure(fig, "figure4_runtime_comparison")

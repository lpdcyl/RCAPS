"""Figure 5: Scenario-level normalized carbon comparison."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paper_plot_style import COLORS, POINTS_CSV, save_figure


data = pd.read_csv(POINTS_CSV)
grouped = data.groupby("gpu_scenario", sort=True)
scenarios = [name.replace("_", " ") for name, _ in grouped]
frames = [frame for _, frame in data.groupby("gpu_scenario", sort=True)]
methods = ("Routing", "CBGP", "Oracle")
columns = ("routing_carbon", "cbgp_carbon", "joint_carbon")
values = np.asarray(
    [
        [(frame[column] / frame["routing_carbon"]).mean() for frame in frames]
        for column in columns
    ]
)
x = np.arange(len(scenarios))
width = 0.24
fig, axis = plt.subplots(figsize=(7.0, 3.2))
for index, method in enumerate(methods):
    axis.bar(
        x + (index - 1) * width,
        values[index],
        width,
        label=method,
        color=COLORS[index],
    )
axis.set_xticks(x, scenarios, rotation=12, ha="right")
axis.set_ylabel("Mean carbon normalized to routing")
axis.set_ylim(0.94, 1.005)
axis.legend(
    frameon=False,
    ncol=3,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.01),
)
save_figure(fig, "figure5_normalized_carbon")

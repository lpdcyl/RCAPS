"""Figure 2: Defined CBGP GapClosed over CI ratio and network capacity."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paper_plot_style import POINTS_CSV, save_figure


data = pd.read_csv(POINTS_CSV)
data = data[data["study"] == "network_sensitivity"]
scenarios = ("commodity_region", "high_asymmetric")
cmap = plt.get_cmap("cividis").copy()
cmap.set_bad("#d0d0d0")
fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharex=True, sharey=True)
image = None
for index, (axis, scenario) in enumerate(zip(axes, scenarios)):
    frame = data[data["gpu_scenario"] == scenario]
    matrix = frame.pivot(
        index="network_capacity", columns="ci_ratio", values="gap_closed"
    ).sort_index()
    values = np.ma.masked_invalid(100.0 * matrix.to_numpy())
    image = axis.imshow(
        values,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        vmin=0.0,
        vmax=100.0,
    )
    positions = range(len(matrix.columns))
    keep = list(positions)[::5]
    axis.set_xticks(keep, [f"{matrix.columns[i]:.2g}" for i in keep])
    axis.set_yticks(range(len(matrix.index)), [f"{value:g}" for value in matrix.index])
    axis.set_xlabel("CI ratio (A/B)")
    axis.text(
        0.02,
        0.97,
        f"({chr(97 + index)}) {scenario.replace('_', ' ')}",
        transform=axis.transAxes,
        va="top",
        color="white",
        bbox={"facecolor": "black", "alpha": 0.45, "edgecolor": "none"},
    )
axes[0].set_ylabel("Cross-region capacity (token/s)")
assert image is not None
colorbar = fig.colorbar(image, ax=axes, pad=0.02)
colorbar.set_label("CBGP GapClosed (%)")
save_figure(fig, "figure2_gap_closed_heatmap")

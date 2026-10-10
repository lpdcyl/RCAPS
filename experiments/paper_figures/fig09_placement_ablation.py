"""Internal placement ablation with benefit sign convention."""

import matplotlib.pyplot as plt
import numpy as np

from common import HELIX, OURS, multiseed, panel, save


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.55), sharey=True)
    for ax, s, letter, color in zip(axes, ("single", "multi"), "ab", (HELIX, OURS)):
        paired = []
        for seed in (0, 1, 2):
            before = multiseed(s, seed, "dev_ablation_before")
            after = multiseed(s, seed, "dev_placement_final_layout")
            paired.append([
                100 * (after["output_throughput_tokens_per_s"] /
                       before["output_throughput_tokens_per_s"] - 1),
                100 * (1 - after["ttft_p95_s"] / before["ttft_p95_s"]),
                100 * (1 - after["tpot_p95_s"] / before["tpot_p95_s"]),
            ])
        values = np.mean(paired, axis=0)
        errors = np.std(paired, axis=0, ddof=1)
        bars = ax.bar(np.arange(3), values, 0.62, color=color,
                      hatch="//" if s == "multi" else "", yerr=errors,
                      error_kw={"elinewidth": 0.8, "capsize": 2})
        ax.axhline(0, color="#50555A", linewidth=0.7)
        ax.set_xticks(range(3), ["Throughput", "P95 TTFT", "P95 TPOT"])
        ax.set_ylim(-6, 21)
        ax.set_ylabel("Benefit over coarse variant (%)" if s == "single" else "")
        for bar, value in zip(bars, values):
            ax.annotate(f"{value:+.1f}",
                        (bar.get_x() + bar.get_width() / 2, value),
                        xytext=(0, 3 if value >= 0 else -3),
                        textcoords="offset points", ha="center",
                        va="bottom" if value >= 0 else "top", fontsize=7.5)
        ax.grid(axis="y", alpha=0.16, linewidth=0.5)
        ax.set_axisbelow(True)
        panel(ax, letter)
    fig.subplots_adjust(wspace=0.19, top=0.9, bottom=0.22)
    save(fig, "fig09_placement_ablation")


if __name__ == "__main__":
    main()

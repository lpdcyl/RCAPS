"""Two distinct controlled comparisons; effects must not be added together."""

import matplotlib.pyplot as plt
import numpy as np

from common import HELIX, OURS, multiseed, panel, save


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")


def benefit(before, after):
    return [(after[METRICS[0]] / before[METRICS[0]] - 1) * 100,
            (1 - after[METRICS[1]] / before[METRICS[1]]) * 100,
            (1 - after[METRICS[2]] / before[METRICS[2]]) * 100]


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.7), sharey=True)
    x = np.arange(3)
    categories = ["Throughput", "P95 TTFT", "P95 TPOT"]
    for i, ax in enumerate(axes):
        for j, (s, color, hatch, label) in enumerate((
            ("single", HELIX, "", "1 cluster"),
            ("multi", OURS, "//", "3 clusters"),
        )):
            paired = []
            for seed in (0, 1, 2):
                before_name = ("dev_placement_helix_layout" if i == 0 else
                               "dev_scheduler_helix")
                after_name = ("dev_placement_final_layout" if i == 0 else
                              "dev_integrated")
                paired.append(benefit(multiseed(s, seed, before_name),
                                      multiseed(s, seed, after_name)))
            values = np.mean(paired, axis=0)
            errors = np.std(paired, axis=0, ddof=1)
            bars = ax.bar(x + (j - 0.5) * 0.35, values, 0.34,
                          color=color, hatch=hatch, edgecolor="white", linewidth=0.4,
                          label=label, yerr=errors,
                          error_kw={"elinewidth": 0.8, "capsize": 2})
            for bar, value in zip(bars, values):
                ax.annotate(f"{value:+.1f}",
                            (bar.get_x() + bar.get_width() / 2, value),
                            xytext=(0, 2 if value >= 0 else -3),
                            textcoords="offset points", ha="center",
                            va="bottom" if value >= 0 else "top", fontsize=7)
        ax.axhline(0, color="#50555A", linewidth=0.7)
        ax.set_xticks(x, categories)
        ax.set_ylim(-12, 48)
        ax.set_ylabel("Benefit over controlled baseline (%)" if i == 0 else "")
        ax.grid(axis="y", alpha=0.16, linewidth=0.5)
        ax.set_axisbelow(True)
        panel(ax, "ab"[i])
    axes[0].legend(frameon=False, loc="upper center", ncol=2,
                   bbox_to_anchor=(1.10, 1.22))
    fig.subplots_adjust(wspace=0.17, top=0.82, bottom=0.22)
    save(fig, "fig06_component_attribution")


if __name__ == "__main__":
    main()

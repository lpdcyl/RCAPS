"""Three-seed throughput and tail-latency response to offered load."""

import matplotlib.pyplot as plt
import numpy as np

from common import HELIX, OURS, panel, read, save


def main():
    summary = read("experiments/ccfa_validation/summary.json")["load"]
    metrics = (
        ("output_throughput_tokens_per_s", "Output throughput (tokens/s)"),
        ("ttft_p95_s", "P95 TTFT (s)"),
        ("tpot_p95_s", "P95 TPOT (s)"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(7.15, 4.2))
    for row, scenario in enumerate(("single", "multi")):
        settings = [summary[scenario][name] for name in ("low", "official", "high")]
        offered = np.array([item["offered_tokens_per_s"] for item in settings])
        for column, (key, label) in enumerate(metrics):
            ax = axes[row, column]
            for method, color, marker, legend in (
                ("helix", HELIX, "o", "Helix"),
                ("green", OURS, "s", "RCAPS"),
            ):
                values = [item[method][key]["mean"] for item in settings]
                errors = [item[method][key]["sd"] for item in settings]
                ax.errorbar(offered, values, yerr=errors, color=color,
                            marker=marker, markersize=3.6, linewidth=1.4,
                            capsize=2, elinewidth=0.8, label=legend)
            ax.set_xticks(offered)
            ax.set_xlabel("Offered load (tokens/s)" if row == 1 else "")
            ax.set_ylabel(label if column == 0 else "")
            if column > 0:
                ax.set_title(label, fontsize=8.5)
            ax.grid(alpha=0.17, linewidth=0.5)
            panel(ax, "abcdef"[row * 3 + column])
        axes[row, 0].text(0.97, 0.07,
                          "1 cluster" if row == 0 else "3 clusters",
                          transform=axes[row, 0].transAxes, ha="right",
                          fontsize=8, color="#4A4F54")
    axes[0, 0].legend(frameon=False, ncol=2, loc="upper left", fontsize=7.5)
    fig.subplots_adjust(left=0.1, right=0.99, top=0.92, bottom=0.12,
                        wspace=0.44, hspace=0.58)
    save(fig, "fig13_load_sweep")


if __name__ == "__main__":
    main()

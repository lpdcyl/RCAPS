"""Three-seed three-cluster sensitivity to cross-region propagation latency."""

import matplotlib.pyplot as plt
import numpy as np

from common import HELIX, OURS, panel, read, save


def main():
    summary = read("experiments/ccfa_validation/summary.json")["network"]
    settings = [summary[name] for name in ("rtt_0p5x", "official", "rtt_2x")]
    factors = np.array([0.5, 1.0, 2.0])
    metrics = (
        ("output_throughput_tokens_per_s", "Output throughput (tokens/s)"),
        ("ttft_p95_s", "P95 TTFT (s)"),
        ("tpot_p95_s", "P95 TPOT (s)"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.45))
    for index, (ax, (key, label)) in enumerate(zip(axes, metrics)):
        for method, color, marker, name in (
            ("helix", HELIX, "o", "Helix"),
            ("green", OURS, "s", "Ours"),
        ):
            values = [item[method][key]["mean"] for item in settings]
            errors = [item[method][key]["sd"] for item in settings]
            ax.errorbar(factors, values, yerr=errors, color=color,
                        marker=marker, markersize=3.6, linewidth=1.4,
                        capsize=2, elinewidth=0.8, label=name)
        ax.set_xticks(factors, ["0.5×", "1×", "2×"])
        ax.set_xlabel("Cross-cluster RTT multiplier")
        ax.set_ylabel(label)
        ax.grid(alpha=0.17, linewidth=0.5)
        panel(ax, "abc"[index])
    axes[0].legend(frameon=False, ncol=2, loc="best", fontsize=7.5)
    fig.subplots_adjust(left=0.1, right=0.99, top=0.84, bottom=0.25, wspace=0.5)
    save(fig, "fig14_rtt_sensitivity")


if __name__ == "__main__":
    main()

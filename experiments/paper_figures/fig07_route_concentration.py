"""Route-frequency concentration at the official offered loads."""

import matplotlib.pyplot as plt
import numpy as np

from common import HELIX, OURS, official, panel, save


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.8))
    for ax, s, letter in zip(axes, ("single", "multi"), "ab"):
        for method, color, linestyle, label in (
            ("helix", HELIX, "-", "Helix"),
            ("integrated", OURS, "--", "Ours"),
        ):
            data = official(s, method)
            values = sorted(data["route_counts"].values(), reverse=True)
            assert sum(values) == data["first_tokens_in_window"]
            cumulative = 100 * np.cumsum(values) / sum(values)
            ax.step(np.arange(1, len(values) + 1), cumulative, where="post",
                    color=color, linestyle=linestyle, linewidth=1.5,
                    label=f"{label} ({len(values)} paths)")
        ax.set_xscale("log")
        ax.set_xlim(1, 420 if s == "single" else 14)
        ax.set_ylim(0, 105)
        ax.set_xlabel("Top-$k$ paths, ordered by request count")
        ax.set_ylabel("Cumulative routed requests (%)")
        ax.grid(alpha=0.15, linewidth=0.5)
        ax.legend(frameon=False, loc="lower right", fontsize=7.2)
        panel(ax, letter)
    fig.subplots_adjust(wspace=0.33, bottom=0.2, top=0.89)
    save(fig, "fig07_route_concentration")


if __name__ == "__main__":
    main()

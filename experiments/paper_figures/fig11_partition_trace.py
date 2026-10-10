"""Offline graph-partition proxy objective, explicitly not simulator latency."""

import matplotlib.pyplot as plt

from common import HELIX, OURS, panel, read, save


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.6))
    for ax, s, letter, color in zip(axes, ("single", "multi"), "ab", (HELIX, OURS)):
        trace = read(f"experiments/critical_graph/runs/{s}_final/placement.json")["trace"]
        steps = [p["step"] for p in trace]
        scores = [p["score"] for p in trace]
        assert steps == list(range(len(steps)))
        ax.plot(steps, scores, color=color, marker="o", markersize=3.8,
                linewidth=1.2)
        ax.set_xlim(-0.25, max(steps) + 0.25)
        ax.set_xticks(range(0, max(steps) + 1, max(1, len(steps) // 5)))
        ax.set_ylim(min(scores) - 0.012, 1.013)
        ax.set_xlabel("Accepted partition refinement step")
        ax.set_ylabel("Normalized proxy objective")
        ax.grid(axis="y", alpha=0.15, linewidth=0.5)
        panel(ax, letter)
    fig.subplots_adjust(wspace=0.34, bottom=0.21, top=0.9)
    save(fig, "fig11_partition_trace")


if __name__ == "__main__":
    main()

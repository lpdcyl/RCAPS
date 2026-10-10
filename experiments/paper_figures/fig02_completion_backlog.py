"""Official-load completion and right-censoring evidence."""

import matplotlib.pyplot as plt
import numpy as np

from common import multiseed, paired_bars, panel, save


def main():
    pairs = [
        ([multiseed(s, seed, "paper_helix") for seed in (0, 1, 2)],
         [multiseed(s, seed, "paper_integrated") for seed in (0, 1, 2)])
        for s in ("single", "multi")]
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.4))
    for ax, key, scale, title in (
        (axes[0], "completion_fraction", 100, "Completed arrivals (%)"),
        (axes[1], "backlog_at_window_end", 1, "Requests remaining at 1800 s"),
    ):
        baseline = [[scale * item[key] for item in pair[0]] for pair in pairs]
        candidate = [[scale * item[key] for item in pair[1]] for pair in pairs]
        paired_bars(ax, ["1 cluster", "3 clusters"],
                    [np.mean(values) for values in baseline],
                    [np.mean(values) for values in candidate], title,
                    baseline_errors=[np.std(values, ddof=1) for values in baseline],
                    candidate_errors=[np.std(values, ddof=1) for values in candidate])
    for ax, letter in zip(axes, "ab"):
        panel(ax, letter)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper center", ncol=2,
               bbox_to_anchor=(0.34, 1.01))
    fig.subplots_adjust(wspace=0.4, top=0.83, bottom=0.22)
    save(fig, "fig02_completion_backlog")


if __name__ == "__main__":
    main()

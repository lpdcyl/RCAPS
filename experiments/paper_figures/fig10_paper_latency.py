"""Latency metrics aligned with the published Helix artifact."""

import matplotlib.pyplot as plt
import numpy as np

from common import multiseed, paired_bars, panel, save


def main():
    pairs = [
        ([multiseed(s, seed, "paper_helix") for seed in (0, 1, 2)],
         [multiseed(s, seed, "paper_integrated") for seed in (0, 1, 2)])
        for s in ("single", "multi")]
    metrics = [
        ("paper_prompt_request_p95_s", "P95 prompt request latency (s)"),
        ("paper_decode_request_p95_s", "P95 decode request latency (s)"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.5))
    for ax, (key, label), letter in zip(axes, metrics, "ab"):
        baseline = [[record[key] for record in pair[0]] for pair in pairs]
        candidate = [[record[key] for record in pair[1]] for pair in pairs]
        paired_bars(ax, ["1 cluster", "3 clusters"],
                    [np.mean(values) for values in baseline],
                    [np.mean(values) for values in candidate], label,
                    baseline_errors=[np.std(values, ddof=1) for values in baseline],
                    candidate_errors=[np.std(values, ddof=1) for values in candidate])
        panel(ax, letter)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper center", ncol=2,
               bbox_to_anchor=(0.34, 1.01))
    fig.subplots_adjust(wspace=0.35, top=0.83, bottom=0.21)
    save(fig, "fig10_paper_latency")


if __name__ == "__main__":
    main()

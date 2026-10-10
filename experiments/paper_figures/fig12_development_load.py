"""Separate lower-load three-seed experiment, with a distinct warmup protocol."""

import matplotlib.pyplot as plt
import numpy as np

from common import multiseed, paired_bars, panel, save


def main():
    pairs = [
        ([multiseed(s, seed, "dev_helix") for seed in (0, 1, 2)],
         [multiseed(s, seed, "dev_integrated") for seed in (0, 1, 2)])
        for s in ("single", "multi")]
    metrics = [
        ("output_throughput_tokens_per_s", "Output throughput\n(tokens/s)"),
        ("ttft_p95_s", "P95 TTFT (s)"),
        ("tpot_p95_s", "P95 TPOT (s)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.5))
    for ax, (key, label), letter in zip(axes, metrics, "abc"):
        baseline = [[record[key] for record in pair[0]] for pair in pairs]
        candidate = [[record[key] for record in pair[1]] for pair in pairs]
        paired_bars(ax, ["1 cluster", "3 clusters"],
                    [np.mean(values) for values in baseline],
                    [np.mean(values) for values in candidate], label,
                    baseline_errors=[np.std(values, ddof=1) for values in baseline],
                    candidate_errors=[np.std(values, ddof=1) for values in candidate])
        panel(ax, letter)
    axes[0].legend(frameon=False, loc="upper right", ncol=2,
                   bbox_to_anchor=(3.58, 1.20))
    fig.subplots_adjust(wspace=0.58, bottom=0.2, top=0.82)
    save(fig, "fig12_development_load")


if __name__ == "__main__":
    main()

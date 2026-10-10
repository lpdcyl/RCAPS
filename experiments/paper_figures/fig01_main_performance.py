"""Official-load end-to-end throughput and tail latency."""

import matplotlib.pyplot as plt
import numpy as np

from common import multiseed, paired_bars, panel, save


def main():
    scenarios = ["single", "multi"]
    pairs = [
        ([multiseed(s, seed, "paper_helix") for seed in (0, 1, 2)],
         [multiseed(s, seed, "paper_integrated") for seed in (0, 1, 2)])
        for s in scenarios]
    metrics = [
        ("output_throughput_tokens_per_s", "Output throughput\n(tokens/s)"),
        ("ttft_p95_s", "P95 TTFT (s)"),
        ("tpot_p95_s", "P95 TPOT (s)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.55))
    for i, (ax, (key, label)) in enumerate(zip(axes, metrics)):
        baseline = [[record[key] for record in pair[0]] for pair in pairs]
        candidate = [[record[key] for record in pair[1]] for pair in pairs]
        paired_bars(ax, ["1 cluster", "3 clusters"],
                    [np.mean(values) for values in baseline],
                    [np.mean(values) for values in candidate], label,
                    baseline_errors=[np.std(values, ddof=1) for values in baseline],
                    candidate_errors=[np.std(values, ddof=1) for values in candidate])
        panel(ax, "abc"[i])
    axes[0].legend(frameon=False, loc="upper right", ncol=2,
                   bbox_to_anchor=(3.58, 1.20))
    fig.subplots_adjust(wspace=0.58, bottom=0.2, top=0.82)
    save(fig, "fig01_main_performance")


if __name__ == "__main__":
    main()

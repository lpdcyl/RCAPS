"""Publication-friendly paired V2 comparison with individual seed points."""

from __future__ import annotations

import json
import os
from pathlib import Path
from statistics import mean

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
METRICS = (
    ("output_throughput_tokens_per_s", "Output throughput"),
    ("ttft_p95_s", "P95 TTFT"),
    ("tpot_p95_s", "P95 TPOT"),
)
BASELINES = ("rcaps", "rcaps_v2_fixed_structure")
LABELS = ("V1", "V2 fixed structure")
COLORS = ("#376a91", "#ba6a35")


def main() -> None:
    summary = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 3, figsize=(10.2, 5.4), constrained_layout=True)
    for row, scenario in enumerate(("single", "multi")):
        for col, (metric, title) in enumerate(METRICS):
            ax = axes[row, col]
            for index, baseline in enumerate(BASELINES):
                key = f"rcaps_v2 vs {baseline}"
                values = summary[scenario]["paired"][key][metric]
                ax.bar(index, mean(values), width=0.56, color=COLORS[index],
                       alpha=0.78, label=LABELS[index])
                for seed, value in enumerate(values):
                    ax.plot(index + (seed - 1) * 0.09, value, "o", ms=4.5,
                            color="#172d3d", zorder=3)
            ax.axhline(0, color="#606a70", linewidth=0.8)
            ax.set_xticks((0, 1), LABELS, rotation=15)
            ax.set_title(f"{scenario.capitalize()} cluster · {title}")
            ax.set_ylabel("Paired improvement (%)" if col == 0 else "")
            ax.grid(axis="y", alpha=0.22)
            ax.set_axisbelow(True)
    fig.suptitle("V2 improvement over two baselines", weight="bold")
    fig.supxlabel("Bars: mean of seed-wise improvements · dots: seeds 0, 1, 2 · positive favors V2",
                 fontsize=8)
    for suffix in ("pdf", "png"):
        fig.savefig(HERE / f"v2_paired_comparison.{suffix}", dpi=240)
    plt.close(fig)


if __name__ == "__main__":
    main()

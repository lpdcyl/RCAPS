"""Rebuild the paired three-seed placement attribution figure from JSON."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
METRICS = (
    ("output_throughput_tokens_per_s", "Throughput"),
    ("ttft_p95_s", "P95 TTFT"),
    ("tpot_p95_s", "P95 TPOT"),
)
STAGES = (
    ("TOPOLOGY_INCREMENT.json", "Topology initialization", "#0072B2", "///"),
    ("CRITICAL_RESOURCE_INCREMENT.json", "Critical-resource refinement",
     "#D55E00", "\\\\"),
)


def load() -> dict:
    values = {}
    for filename, label, color, hatch in STAGES:
        report = json.loads((ROOT / "paper" / filename).read_text(encoding="utf-8"))
        for row in report:
            values[(row["scenario"], label)] = row["metrics"]
    return values


def main() -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9,
        "ytick.labelsize": 9, "legend.fontsize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "savefig.dpi": 300,
    })
    values = load()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.45), layout="constrained")
    x = np.arange(len(METRICS))
    width = 0.35
    for ax, scenario, label, limits in zip(
            axes, ("single", "multi"),
            ("Single-cluster improvement (%)", "Three-cluster improvement (%)"),
            ((-4, 19), (-7, 46))):
        for stage_index, (_, stage, color, hatch) in enumerate(STAGES):
            x_stage = x + (stage_index - 0.5) * width
            effects = [values[(scenario, stage)][metric] for metric, _ in METRICS]
            means = [item["paired_improvement_percent_mean"] for item in effects]
            deviations = [item["paired_improvement_percent_sample_sd"]
                          for item in effects]
            ax.bar(x_stage, means, width=width, color=color, alpha=0.78,
                   edgecolor="black", linewidth=0.55, hatch=hatch,
                   yerr=deviations, capsize=3, ecolor="black", label=stage)
            for xpos, item in zip(x_stage, effects):
                by_seed = item["paired_improvement_percent_by_seed"]
                for offset, seed in zip((-0.075, 0, 0.075), (0, 1, 2)):
                    ax.scatter(xpos + offset, by_seed[str(seed)], s=12,
                               facecolors="white", edgecolors="black",
                               linewidths=0.65, zorder=5)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(x, [label for _, label in METRICS])
        ax.set_ylabel(label)
        ax.set_ylim(*limits)
        ax.grid(axis="y", alpha=0.18, linewidth=0.6)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, frameon=False, loc="upper center",
               bbox_to_anchor=(0.5, 1.13))
    OUT.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "png"):
        path = OUT / f"placement_attribution.{extension}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.07, dpi=300)
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()

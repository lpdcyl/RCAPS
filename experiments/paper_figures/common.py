"""Shared, reproducible plotting utilities for the RCAPS paper figures."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
HELIX = "#32678F"
OURS = "#C75B39"
CANONICAL = "#8D799D"
GRAY = "#5B626B"
LIGHT = "#EDF0F1"
GPU_COLORS = {"A100": "#32678F", "L4": "#2A8C82", "T4": "#D89B3C"}

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.linewidth": 0.7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.06,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.dpi": 160,
})


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def save(fig, stem: str):
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.png", dpi=300)
    plt.close(fig)
    print(OUT / f"{stem}.pdf")


def panel(ax, letter: str):
    ax.text(-0.08, 1.04, f"({letter})", transform=ax.transAxes,
            weight="bold", ha="right", va="bottom")


def official(scenario: str, method: str):
    return read(f"experiments/queue_dag/runs/paperload_{scenario}_{method}_seed0_1800.json")


def multiseed(scenario: str, seed: int, run_name: str):
    return read(f"experiments/multiseed/runs/seed{seed}/{scenario}/{run_name}.json")


def paired_bars(ax, categories, baseline, candidate, ylabel, labels=True,
                baseline_errors=None, candidate_errors=None):
    import numpy as np

    x = np.arange(len(categories))
    width = 0.34
    error_style = {"elinewidth": 0.8, "capsize": 2, "capthick": 0.8}
    a = ax.bar(x - width / 2, baseline, width, color=HELIX, label="Helix",
               yerr=baseline_errors, error_kw=error_style)
    b = ax.bar(x + width / 2, candidate, width, color=OURS, label="RCAPS",
               hatch="//", edgecolor="white", linewidth=0.5,
               yerr=candidate_errors, error_kw=error_style)
    ax.set_xticks(x, categories)
    ax.set_ylabel(ylabel)
    upper = max([*baseline, *candidate])
    if baseline_errors is not None:
        upper = max(upper, max(v + e for v, e in zip(baseline, baseline_errors)))
    if candidate_errors is not None:
        upper = max(upper, max(v + e for v, e in zip(candidate, candidate_errors)))
    ax.set_ylim(0, upper * 1.27)
    ax.grid(axis="y", alpha=0.18, linewidth=0.5)
    ax.set_axisbelow(True)
    if labels:
        for bars in (a, b):
            for bar in bars:
                val = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, val + ax.get_ylim()[1] * 0.018,
                        f"{val:.1f}", ha="center", va="bottom", fontsize=7.1)
    return a, b

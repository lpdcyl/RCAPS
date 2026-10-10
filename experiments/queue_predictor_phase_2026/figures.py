"""Plot ranking changes on fixed layouts and paired online differences."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "queue_predictor_2026"


def draw() -> list[Path]:
    audit = json.loads((OLD / "phase_audit.json").read_text(encoding="utf-8"))
    results = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    output = HERE / "figures"
    output.mkdir(exist_ok=True)
    paths = []

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    labels = ["Single initial", "Single RCAPS", "Three initial", "Three RCAPS"]
    cases = [("single", "coarse"), ("single", "original"),
             ("multi", "coarse"), ("multi", "original")]
    x = np.arange(len(cases))
    for offset, mode, color in ((-0.18, "legacy", "#8799ad"),
                                (0.18, "phase", "#2876a4")):
        values = [audit[name][arm][mode]["queue_rank_spearman"]
                  for name, arm in cases]
        ax.bar(x + offset, values, 0.34, color=color, label=mode)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Spearman versus measured GPU queue rank")
    ax.set_title("Same fixed layouts and seeds 0, 1, 2")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path = output / "phase_rank_audit.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    metrics = (("output_throughput_tokens_per_s", "Throughput"),
               ("ttft_p95_s", "P95 TTFT"), ("tpot_p95_s", "P95 TPOT"))
    colors = ("#2e6f9e", "#de8f45", "#5b9a70")
    for ax, (name, title) in zip(axes, (("single", "Single cluster"),
                                        ("multi", "Three clusters"))):
        rows = results[name]["seeds"]
        for index, (field, label) in enumerate(metrics):
            changes = [100 * (row["phase"][field] / row["original"][field] - 1)
                       for row in rows]
            ax.bar(index, np.mean(changes), width=0.58,
                   color=colors[index], alpha=0.78)
            ax.scatter(np.full(3, index) + np.array((-0.12, 0, 0.12)), changes,
                       color="#263443", s=26, zorder=3)
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_xticks(range(3), [label for _, label in metrics])
        ax.set_title(title)
        ax.set_ylabel("Change from RCAPS (%)")
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("Phase-corrected predictor: paired full-window outcomes")
    fig.text(0.5, 0.005, "Positive throughput and negative latency are favorable.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))
    path = output / "online_paired_changes.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    paths.append(path)
    return paths


if __name__ == "__main__":
    for path in draw():
        print(path)

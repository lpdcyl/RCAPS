"""Render paired online changes and retrospective hotspot-rank diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent


def draw() -> list[Path]:
    data = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    audit = json.loads((HERE.parent / "validation_2026/hotspot_audit.json").read_text(
        encoding="utf-8"))
    output = HERE / "figures"
    output.mkdir(exist_ok=True)
    paths = []

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
    metrics = (("output_throughput_tokens_per_s", "Throughput"),
               ("ttft_p95_s", "P95 TTFT"), ("tpot_p95_s", "P95 TPOT"))
    colors = ("#2e6f9e", "#de8f45", "#5b9a70")
    for ax, (scenario, title) in zip(axes, (("single", "Single cluster"),
                                            ("multi", "Three clusters"))):
        rows = data[scenario]["seeds"]
        for index, (key, label) in enumerate(metrics):
            changes = [100 * (row["queue_predictor"][key] /
                              row["baseline"][key] - 1) for row in rows]
            ax.bar(index, np.mean(changes), width=0.58, color=colors[index], alpha=0.78)
            ax.scatter(np.full(3, index) + np.array((-0.12, 0, 0.12)), changes,
                       color="#263443", s=26, zorder=3)
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_xticks(range(3), [label for _, label in metrics])
        ax.set_title(title)
        ax.set_ylabel("Change from RCAPS (%)")
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("Queue-predicted placement: paired online outcomes (seeds 0–2)")
    fig.text(0.5, 0.005, "Positive throughput is favorable; negative latency is favorable.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))
    path = output / "online_paired_changes.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    paths.append(path)

    fig, ax = plt.subplots(figsize=(7.8, 4.3))
    x = np.arange(2)
    old = [audit[name]["rcaps"]["mean_correlations"][
        "ensemble_queue_spearman" if name == "single" else
        "canonical_queue_spearman"] for name in ("single", "multi")]
    new = [data[name]["prediction_rank_correlations"][
        "baseline_layout_queue_rank_spearman"]["mean"]
        for name in ("single", "multi")]
    ax.bar(x - 0.18, old, width=0.34, color="#7b8b9e", label="Current demand proxy")
    ax.bar(x + 0.18, new, width=0.34, color="#2e6f9e", label="Queue-flow proxy")
    ax.set_xticks(x, ["Single cluster", "Three clusters"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Spearman correlation with measured GPU queue rank")
    ax.set_title("Same original RCAPS layouts, three-seed mean")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path = output / "queue_rank_prediction.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    paths.append(path)
    return paths


if __name__ == "__main__":
    for path in draw():
        print(path)

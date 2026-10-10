"""Plot structure outcomes and prefix sensitivity from validated summaries."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
FIGURES = HERE / "figures"
METRICS = (
    ("output_throughput_tokens_per_s", "Decode throughput (token/s)"),
    ("ttft_p95_s", "p95 TTFT (s)"),
    ("tpot_p95_s", "p95 TPOT (s/token)"),
)
COLORS = {"s1_all24": "#666666", "s1_lean": "#888888",
          "s3_prefix10": "#009E73", "s3_prefix11": "#56B4E9",
          "s2_prefix12": "#0072B2"}
LABELS = {"s1_all24": "Single path\n24 GPUs",
          "s1_lean": "Single path\n9 GPUs",
          "s3_prefix10": "Prefix 10",
          "s3_prefix11": "Prefix 11",
          "s2_prefix12": "Prefix 12"}


def draw(data: dict, filename: str, *, safe: bool) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.2), constrained_layout=True)
    for row, scenario in enumerate(("single", "multi")):
        section = data["scenarios"][scenario]
        arms = (["s1_all24", "s2_prefix12"] if safe else
                ["s1_lean", *(["s3_prefix10"] if scenario == "multi" else []),
                 "s3_prefix11", "s2_prefix12"])
        for col, (metric, ylabel) in enumerate(METRICS):
            ax = axes[row, col]
            for index, arm in enumerate(arms):
                result = section["outcomes"][arm][metric]
                if result["n"] != 3:
                    ax.text(index, 0.02, f"n={result['n']}/3", ha="center",
                            rotation=90, transform=ax.get_xaxis_transform())
                    continue
                ax.bar(index, result["mean"], color=COLORS[arm], width=0.7)
                for offset, value in zip((-0.13, 0, 0.13), result["by_seed"]):
                    ax.plot(index + offset, value, "o", color="black", markersize=3)
            ax.set_xticks(range(len(arms)), [LABELS[arm] for arm in arms])
            ax.set_ylabel(ylabel)
            ax.set_title(f"{'Single cluster' if scenario == 'single' else 'Three clusters'}: "
                         f"{section['offered_tokens_per_s']:g} offered token/s")
            ax.grid(axis="y", alpha=0.2)
    note = "Black dots: paired seeds 0/1/2. All arms use the same RCAPS online scheduler."
    if not safe:
        note += " The 24-GPU single path lacks complete results at the original load."
    fig.text(0.5, -0.01, note,
             ha="center", fontsize=9)
    FIGURES.mkdir(parents=True, exist_ok=True)
    output = FIGURES / filename
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(output)


def prefix_sensitivity(data: dict) -> None:
    metrics = (("shared_gpu_queue_s_per_arrival", "Shared GPU queue (request-s / arrival)"),
               ("shared_gpu_busy_fraction", "Shared GPU busy fraction"),
               ("tpot_p95_s", "p95 TPOT (s/token)"))
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6.7), constrained_layout=True)
    for row, scenario in enumerate(("single", "multi")):
        section = data["scenarios"][scenario]
        arms = (["s3_prefix11", "s2_prefix12"] if scenario == "single" else
                ["s3_prefix10", "s3_prefix11", "s2_prefix12"])
        lengths = [section["arms"][arm]["shared_prefix_length"] for arm in arms]
        for col, (metric, ylabel) in enumerate(metrics):
            ax = axes[row, col]
            means = [section["outcomes"][arm][metric]["mean"] for arm in arms]
            ax.plot(lengths, means, "o-", color="#0072B2")
            for x, arm in zip(lengths, arms):
                for value in section["outcomes"][arm][metric]["by_seed"]:
                    ax.plot(x, value, "x", color="black", markersize=4)
            ax.set_xticks(lengths)
            ax.set_xlabel("Shared prefix length (layers)")
            ax.set_ylabel(ylabel)
            ax.set_title("Single cluster" if scenario == "single" else "Three clusters")
            ax.grid(alpha=0.2)
    fig.text(0.5, -0.01, "Crosses: seeds 0/1/2. Single-cluster prefix 10 is infeasible with fixed branch assignments.",
             ha="center", fontsize=9)
    output = FIGURES / "prefix_sensitivity.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(output)


def main() -> None:
    high = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    safe = json.loads((HERE / "summary_safe.json").read_text(encoding="utf-8"))
    draw(high, "structure_high_load.png", safe=False)
    draw(safe, "structure_safe_load.png", safe=True)
    prefix_sensitivity(high)


if __name__ == "__main__":
    main()

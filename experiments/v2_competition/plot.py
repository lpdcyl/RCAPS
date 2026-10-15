"""Publication-friendly summary of the frozen-candidate competition sweep."""

from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .run_one import HERE


def main() -> None:
    data = json.loads((HERE / "summary_two_seeds.json").read_text(encoding="utf-8"))
    loads = [350, 525, 700]
    styles = {
        "compute_only": ("Compute-only", "#7B8794", "--", "s"),
        "static_resource": ("Static heterogeneous", "#E39C36", "-.", "D"),
        "event_dag": ("Event DAG", "#2369B2", "-", "o"),
    }
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.7), constrained_layout=True)
    for evaluator, (label, color, line, marker) in styles.items():
        rho = [data["loads"][str(load)]["spearman_agreement"][evaluator]
               ["output_throughput_tokens_per_s"] for load in loads]
        axes[0].plot(loads, rho, label=label, color=color, linestyle=line,
                     marker=marker, linewidth=2, markersize=6)
        tpot = [data["loads"][str(load)]["selected"][evaluator]
                ["online"]["tpot_p95_s"] for load in loads]
        axes[1].plot(loads, tpot, label=label, color=color, linestyle=line,
                     marker=marker, linewidth=2, markersize=6)
    axes[0].set_ylabel("Spearman agreement with online throughput")
    axes[0].set_ylim(0.5, 1.0)
    axes[1].set_ylabel("Selected layout P95 TPOT (s)")
    for ax in axes:
        ax.set_xlabel("Offered load (tokens/s)")
        ax.set_xticks(loads)
        ax.grid(True, alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8, loc="lower right")
    for extension in ("png", "svg"):
        fig.savefig(HERE / f"competition_ranking.{extension}", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()

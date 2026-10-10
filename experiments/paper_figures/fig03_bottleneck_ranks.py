"""Predicted GPU-demand ranks versus measured busy ranks in the 240 s audit."""

import json

import matplotlib.pyplot as plt
from scipy.stats import rankdata, spearmanr

from common import CANONICAL, GRAY, OURS, ROOT, panel, read, save
from experiments.critical_graph.model_audit import state_from_placement
from experiments.critical_graph.partition import scenario
from experiments.critical_graph.path_ensemble import measure as path_ensemble_measure
from experiments.critical_graph.topology import TopologyModel


def source(s):
    model = TopologyModel(scenario(s)[0])
    state = state_from_placement(ROOT / "experiments" / "critical_graph" / "runs" / s / "placement.json")
    profile = read(f"experiments/critical_graph/runs/{s}/pilot_profile_seed1_240.json")
    actual = {int(k.split("-")[1]) - 2: v for k, v in profile["gpu_busy_fraction"].items()}
    canonical = {node: 0.0 for node in model.types}
    for path in state["paths"]:
        for stage in model._stages(state, path):
            if stage["device"] != "sink":
                node = int(stage["device"])
                canonical[node] += 0.5 * max(
                    stage["prefill_s"] / model.prompt_tokens,
                    stage["decode_s"] / model.decode_batch)
    ensemble = path_ensemble_measure(model, state).gpu_demand_s
    keys = sorted(actual)
    return {name: [values[k] for k in keys] for name, values in
            (("actual", actual), ("canonical", canonical), ("ensemble", ensemble))}


def main():
    audit = read("experiments/critical_graph/runs/resource_audit_seed1_240.json")
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 3.6))
    for ax, s, letter, title in zip(
        axes, ("single", "multi"), "ab", ("One cluster", "Three clusters")
    ):
        data = source(s)
        actual = rankdata([-x for x in data["actual"]], method="average")
        ax.plot([1, 24], [1, 24], color="#A6ADB3", linewidth=0.8, zorder=0)
        correlations = []
        for name, marker, color, label in (
            ("canonical", "o", CANONICAL, "Two design paths"),
            ("ensemble", "s", OURS, "Compatible paths"),
        ):
            predicted = rankdata([-x for x in data[name]], method="average")
            rho = spearmanr(actual, predicted).statistic
            expected = audit[s]["canonical_rank_correlation" if name == "canonical"
                                else "path_ensemble_rank_correlation"]
            assert abs(rho - expected) < 1e-10
            correlations.append(rho)
            ax.scatter(predicted, actual, s=19, marker=marker, facecolor="none",
                       edgecolor=color, linewidth=0.9, label=label)
        ax.set_xlim(0, 25)
        ax.set_ylim(25, 0)
        ax.set_xticks([1, 5, 10, 15, 20, 24])
        ax.set_yticks([1, 5, 10, 15, 20, 24])
        ax.set_xlabel("Predicted GPU busy rank")
        ax.set_ylabel("Measured GPU busy rank")
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=9)
        ax.text(0.98, 0.97,
                f"$\\rho$: {correlations[0]:.2f} $\\rightarrow$ {correlations[1]:.2f}",
                transform=ax.transAxes, ha="right", va="top", fontsize=7.5,
                color=GRAY)
        panel(ax, letter)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.10),
               ncol=2, frameon=False, fontsize=8)
    fig.text(0.5, 0.035,
             "Each GPU has one circle and one square   |   Rank 1 = busiest   |   Diagonal = perfect agreement",
             ha="center", va="bottom", fontsize=7.5)
    fig.subplots_adjust(wspace=0.34, bottom=0.28, top=0.87)
    save(fig, "fig03_bottleneck_ranks")


if __name__ == "__main__":
    main()

"""Plot the audited 600-second, single-seed resource-pool load sweep."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .prepare import HERE


STYLE = {
    "adaptive": ("Full V2", "#1261a0", "o"),
    "fixed_branches": ("Fixed branches", "#308050", "s"),
    "fixed_structure": ("Fixed structure", "#8760a8", "D"),
    "helix": ("Helix ILP", "#cc6e2e", "^"),
    "helix_petals": ("Helix-Petals", "#cc6e2e", "^"),
}


def main() -> None:
    summary = json.loads((HERE / "sensitivity_summary.json").read_text(encoding="utf-8"))
    cases = summary["cases"]
    fig, axes = plt.subplots(2, 5, figsize=(16, 6.3), sharex="col",
                             constrained_layout=True)
    for col, (case, load_rows) in enumerate(cases.items()):
        loads = sorted(float(key) for key in load_rows)
        methods = load_rows[f"{loads[0]:g}"].keys()
        for method in methods:
            label, color, marker = STYLE[method]
            metric_rows = [load_rows[f"{load:g}"][method]["metrics"] for load in loads]
            completion = [100 * row["completion_fraction"] for row in metric_rows]
            tpot = [row["tpot_p95_s"] for row in metric_rows]
            axes[0, col].plot(loads, completion, label=label, color=color,
                              marker=marker, linewidth=1.8, markersize=4)
            axes[1, col].plot(loads, tpot, label=label, color=color,
                              marker=marker, linewidth=1.8, markersize=4)
        axes[0, col].set_title(case, fontsize=12, fontweight="bold")
        axes[0, col].set_ylim(0, 105)
        axes[0, col].set_yticks([0, 25, 50, 75, 100])
        axes[1, col].set_xlabel("Offered token/s")
        axes[1, col].set_xticks(loads)
        for row in (0, 1):
            axes[row, col].grid(alpha=0.25, linewidth=0.6)
    axes[0, 0].set_ylabel("Completion (%)")
    axes[1, 0].set_ylabel("P95 TPOT (s)")
    handles, labels = [], []
    for axis in axes.flat:
        local_handles, local_labels = axis.get_legend_handles_labels()
        for handle, label in zip(local_handles, local_labels):
            if label not in labels:
                handles.append(handle)
                labels.append(label)
    fig.legend(handles, labels, loc="outside lower center", ncol=len(labels),
               frameon=False, fontsize=9)
    for ext in ("png", "svg"):
        fig.savefig(HERE / f"resource_load_sweep.{ext}", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Plot V2 structure selection and within-pool P95 TPOT changes."""

from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .prepare import HERE


def main() -> None:
    data = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))["cases"]
    cases = list(data)
    x = np.arange(len(cases))
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.1), constrained_layout=True)
    prefixes = [data[case]["structure"]["adaptive"]["prefix_layers"]
                for case in cases]
    branches = [len(data[case]["structure"]["adaptive"]["branches"])
                for case in cases]
    colors = ["#2979B8" if count == 3 else "#49A57A" for count in branches]
    axes[0].bar(x, prefixes, color=colors, width=0.62)
    for i, case in enumerate(cases):
        shared = len(data[case]["structure"]["adaptive"]["stem"])
        axes[0].text(i, prefixes[i] + 1.5, f"{shared} A100 · {branches[i]} suffix",
                     ha="center", fontsize=8, rotation=30)
    axes[0].set_ylim(0, 91)
    axes[0].set_xticks(x, cases)
    axes[0].set_ylabel("Selected shared-prefix layers")
    axes[0].set_title("V2 structure")
    axes[0].grid(axis="y", alpha=0.2)

    width = 0.24
    controls = (("fixed_branches", "Fixed branches", "#49A57A"),
                ("fixed_structure", "Fixed structure", "#8064A2"),
                ("helix", "Helix layout", "#DD9340"))
    for index, (method, label, color) in enumerate(controls):
        values = []
        for case in cases:
            row = data[case]
            actual = ("helix" if "helix" in row["statistics"]
                      else "helix_petals") if method == "helix" else method
            if actual not in row["statistics"]:
                values.append(np.nan)
                continue
            v2 = row["statistics"]["adaptive"]["tpot_p95_s"]["mean"]
            control = row["statistics"][actual]["tpot_p95_s"]["mean"]
            values.append(100 * (control - v2) / control)
        offset = (index - 1) * width
        bars = axes[1].bar(x + offset, values, width=width, color=color, label=label)
        if method == "helix":
            for case, bar in zip(cases, bars):
                if case in ("C3", "C4", "C5"):
                    bar.set_hatch("//")
    axes[1].set_xticks(x, cases)
    axes[1].set_ylabel("V2 P95 TPOT reduction vs control (%)")
    axes[1].set_ylim(0, 80)
    axes[1].set_title("Within-pool comparison")
    axes[1].grid(axis="y", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8, loc="upper right")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    for ext in ("png", "svg"):
        fig.savefig(HERE / f"resource_generalization.{ext}", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Make the paper figure from complete three-seed branch comparisons."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
SETTINGS = (("C1_single", 600, (4, 5, 6)),
            ("C1_multi", 320, (1, 2, 3)))
METRICS = (("output_throughput_tokens_per_s", "Output throughput (token/s)"),
           ("completion_fraction", "Completion fraction"),
           ("backlog_at_window_end", "End backlog (requests)"))
COLORS = {"k1": "#5B8FF9", "k2": "#F6BD16", "k3": "#5AD8A6",
          "equal_gpu_k2": "#E8684A"}


def main() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, axes = plt.subplots(2, 3, figsize=(10.2, 5.7), constrained_layout=True)
    for row, (case, load, seeds) in enumerate(SETTINGS):
        data = {}
        variants = ("k1", "k2", "k3") + (("equal_gpu_k2",) if row == 0 else ())
        for variant in variants:
            data[variant] = []
            for seed in seeds:
                path = (HERE / "runs" / "formal" / case / variant /
                        f"load{load:g}_seed{seed}.json")
                if not path.exists():
                    raise FileNotFoundError(path)
                data[variant].append(json.loads(path.read_text(encoding="utf-8")))
        traces = {seed: {data[variant][i]["trace_sha256"] for variant in variants}
                  for i, seed in enumerate(seeds)}
        if any(len(values) != 1 for values in traces.values()):
            raise ValueError(f"Unpaired traces: {case}")
        for col, (metric, ylabel) in enumerate(METRICS):
            ax = axes[row, col]
            for i, variant in enumerate(variants):
                x = (2.16 if variant == "equal_gpu_k2" else i + 1)
                values = np.array([item[metric] for item in data[variant]])
                color = COLORS[variant]
                ax.scatter([x - .055, x, x + .055], values, s=17,
                           color=color, alpha=.55, zorder=2)
                ax.errorbar(x, values.mean(), yerr=[[values.mean() - values.min()],
                                                    [values.max() - values.mean()]],
                            fmt="o", color=color, markersize=7, capsize=3,
                            linewidth=1.5, zorder=3,
                            label=("24-GPU two branches" if variant == "equal_gpu_k2"
                                   else f"{variant}: {len(data[variant])} seeds"))
            ax.set_xticks((1, 2, 3), ("1 branch", "2 branches", "3 branches"))
            ax.set_xlim(.65, 3.35)
            ax.set_ylabel(ylabel)
            ax.grid(axis="y", color="#D8D8D8", linewidth=.6)
            if col == 0:
                ax.set_title(f"{case}: {load:g} offered token/s")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    axes[0, 2].legend(handles, labels, frameon=False, fontsize=7,
                      loc="upper right")
    for extension in ("pdf", "png"):
        path = HERE / f"figure_branch_parallelism.{extension}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()

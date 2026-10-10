"""Compact, editable vector framework diagram for the three implemented methods."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch


HERE = Path(__file__).resolve().parent
NAVY = "#243C53"
BLUE = "#32678F"
TEAL = "#2B8A83"
ORANGE = "#C75B39"
INK = "#28343F"
MUTED = "#64727F"
EDGE = "#CAD4DB"
PALE = "#F5F8FA"
GRAY = "#A9B4BC"


def rounded(ax, x, y, w, h, *, face="white", edge=EDGE, radius=0.07,
            lw=0.8, z=1):
    patch = FancyBboxPatch((x, y), w, h,
                           boxstyle=f"round,pad=0.008,rounding_size={radius}",
                           linewidth=lw, edgecolor=edge, facecolor=face, zorder=z)
    ax.add_patch(patch)
    return patch


def label(ax, x, y, value, *, size=7.4, color=INK, weight="normal",
          ha="center", va="center", z=5):
    ax.text(x, y, value, fontsize=size, color=color, weight=weight,
            ha=ha, va=va, zorder=z)


def arrow(ax, x0, y0, x1, y1, *, color=MUTED, width=1.2,
          dashed=False, head=8, z=3):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1),
                                 arrowstyle="-|>", mutation_scale=head,
                                 linewidth=width, color=color,
                                 linestyle="--" if dashed else "-", zorder=z))


def node(ax, x, y, w, h, text, color, *, outline=False, size=7.0):
    rounded(ax, x, y, w, h,
            face="white" if outline else color,
            edge=color, radius=0.035, lw=0.85, z=4)
    label(ax, x + w / 2, y + h / 2, text, size=size,
          color=color if outline else "white", weight="semibold")


def card(ax, x, title, number, subtitle):
    y, w, h = 0.32, 2.19, 2.43
    rounded(ax, x, y, w, h, face=PALE, edge=EDGE, radius=0.09, lw=0.95)
    rounded(ax, x + 0.13, y + h - 0.38, 0.26, 0.26,
            face=NAVY, edge=NAVY, radius=0.13)
    label(ax, x + 0.26, y + h - 0.25, str(number), size=8.2,
          color="white", weight="bold")
    label(ax, x + 0.48, y + h - 0.25, title, size=9.1,
          color=NAVY, weight="bold", ha="left")
    label(ax, x + 0.14, y + h - 0.58, subtitle,
          size=7.2, color=MUTED, ha="left")
    ax.plot([x + 0.13, x + w - 0.13], [y + h - 0.77] * 2,
            color=EDGE, linewidth=0.65, zorder=2)
    return x, y, w, h


def event_module(ax, x):
    card(ax, x, "Resource event DAG", 1,
         "GPU compute · transfer · queue")
    y = 1.22
    node(ax, x + 0.17, y, 0.40, 0.32, "GPU", BLUE)
    node(ax, x + 0.70, y, 0.45, 0.32, "Link", TEAL)
    node(ax, x + 1.28, y, 0.42, 0.32, "Wait", ORANGE)
    node(ax, x + 1.84, y, 0.24, 0.32, "G", BLUE)
    for a, b in ((0.57, 0.70), (1.15, 1.28), (1.70, 1.84)):
        arrow(ax, x + a, y + 0.16, x + b, y + 0.16,
              color=ORANGE, width=1.55, head=8)
    node(ax, x + 0.17, 0.71, 0.40, 0.27, "GPU", BLUE,
         outline=True, size=6.8)
    arrow(ax, x + 0.37, 0.99, x + 0.37, 1.20,
          color=MUTED, dashed=True, width=0.95, head=7)
    label(ax, x + 0.64, 0.84, "resource order", size=6.6,
          color=MUTED, ha="left")
    label(ax, x + 0.15, 0.48, "Output: critical path and bottleneck",
          size=7.1, color=NAVY, weight="semibold", ha="left")


def partition_module(ax, x):
    card(ax, x, "Topology-aware partition", 2,
         "capacity + critical-path feedback")
    node(ax, x + 0.16, 1.14, 0.53, 0.36, "C1\n0–11", BLUE, size=6.8)
    node(ax, x + 1.10, 1.52, 0.72, 0.36, "A: C1/C3\n12–79", TEAL, size=6.4)
    node(ax, x + 1.10, 0.82, 0.72, 0.36, "B: C1/C2\n12–79", TEAL,
         outline=True, size=6.4)
    arrow(ax, x + 0.69, 1.34, x + 1.08, 1.70,
          color=MUTED, width=1.2)
    arrow(ax, x + 0.69, 1.28, x + 1.08, 1.00,
          color=MUTED, width=1.2)
    label(ax, x + 1.53, 1.31, "two complete\nsuffix paths",
          size=6.7, color=MUTED)
    label(ax, x + 0.15, 0.48, "Output: layer cuts and feasible DAG",
          size=7.1, color=NAVY, weight="semibold", ha="left")


def scheduler_module(ax, x):
    card(ax, x, "Queue-aware DAG routing", 3,
         "earliest-finish dynamic program")
    node(ax, x + 0.16, 1.19, 0.31, 0.31, "0", NAVY,
         outline=True, size=7.5)
    node(ax, x + 0.80, 1.56, 0.48, 0.31, "GPU A", BLUE, size=6.6)
    node(ax, x + 0.80, 0.81, 0.48, 0.31, "GPU B", BLUE,
         outline=True, size=6.6)
    node(ax, x + 1.63, 1.19, 0.39, 0.31, "80", NAVY,
         outline=True, size=7.5)
    arrow(ax, x + 0.47, 1.36, x + 0.79, 1.72,
          color=ORANGE, width=1.6)
    arrow(ax, x + 0.47, 1.31, x + 0.79, 0.96,
          color=GRAY, width=0.95)
    arrow(ax, x + 1.28, 1.72, x + 1.61, 1.37,
          color=ORANGE, width=1.6)
    arrow(ax, x + 1.28, 0.96, x + 1.61, 1.31,
          color=GRAY, width=0.95)
    label(ax, x + 1.51, 0.70, "queue snapshot", size=6.5,
          color=ORANGE)
    label(ax, x + 0.15, 0.48, "Output: prompt path; KV-pinned decode",
          size=7.05, color=NAVY, weight="semibold", ha="left")


def main():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    fig, ax = plt.subplots(figsize=(7.35, 3.00))
    ax.set_xlim(0, 7.35)
    ax.set_ylim(0, 3.0)
    ax.axis("off")
    for fn, x in ((event_module, 0.05),
                  (partition_module, 2.58),
                  (scheduler_module, 5.11)):
        fn(ax, x)
    arrow(ax, 2.27, 1.55, 2.55, 1.55, color=NAVY, width=1.75, head=9)
    label(ax, 2.41, 1.75, "bottleneck", size=6.4, color=MUTED)
    arrow(ax, 4.80, 1.55, 5.08, 1.55, color=NAVY, width=1.75, head=9)
    label(ax, 4.94, 1.75, "layer DAG", size=6.4, color=MUTED)
    label(ax, 1.15, 2.89, "OFFLINE ANALYSIS", size=6.7,
          color=MUTED, weight="semibold")
    label(ax, 3.68, 2.89, "OFFLINE PLACEMENT", size=6.7,
          color=MUTED, weight="semibold")
    label(ax, 6.21, 2.89, "ONLINE SCHEDULING", size=6.7,
          color=MUTED, weight="semibold")
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.99)
    for ext, kwargs in (("pdf", {}), ("svg", {}),
                        ("png", {"dpi": 300})):
        path = HERE / f"ccf_method_framework.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.025, **kwargs)
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Unified control/data-plane overview for the Helix-GREEN paper."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


HERE = Path(__file__).resolve().parent
NAVY = "#263E55"
BLUE = "#376E96"
TEAL = "#2C8A83"
ORANGE = "#C75B39"
INK = "#2C3944"
MUTED = "#657581"
EDGE = "#C8D3DB"
PALE_BLUE = "#F2F7FA"
PALE_GREEN = "#F3F8F6"
PALE_GOLD = "#FAF7F1"
ALT = "#AAB7BF"


def txt(ax, x, y, string, size=7.5, color=INK, weight="normal",
        ha="center", va="center", z=7):
    ax.text(x, y, string, fontsize=size, color=color, weight=weight,
            ha=ha, va=va, zorder=z)


def box(ax, x, y, w, h, *, face="white", border=EDGE, radius=0.06,
        lw=0.85, z=2):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0.006,rounding_size={radius}",
                       facecolor=face, edgecolor=border, linewidth=lw, zorder=z)
    ax.add_patch(p)
    return p


def pill(ax, x, y, w, h, string, *, fill, text_color="white",
         border=None, size=7.4, weight="semibold"):
    box(ax, x, y, w, h, face=fill, border=border or fill,
        radius=min(h / 2.8, 0.06), lw=0.9, z=5)
    txt(ax, x + w / 2, y + h / 2, string, size=size,
        color=text_color, weight=weight)


def arrow(ax, x0, y0, x1, y1, *, color=NAVY, width=1.45,
          dashed=False, head=8, z=6):
    p = FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                        mutation_scale=head, linewidth=width, color=color,
                        linestyle="--" if dashed else "-", zorder=z)
    ax.add_patch(p)


def bent(ax, pts, *, color=MUTED, width=1.05, dashed=True, head=7):
    for (x0, y0), (x1, y1) in zip(pts[:-2], pts[1:-1]):
        ax.plot([x0, x1], [y0, y1], color=color, linewidth=width,
                linestyle="--" if dashed else "-", zorder=5)
    arrow(ax, *pts[-2], *pts[-1], color=color, width=width,
          dashed=dashed, head=head)


def section(ax, x, y, w, h, label, face):
    box(ax, x, y, w, h, face=face, border=EDGE, radius=0.085,
        lw=0.95, z=1)
    txt(ax, x + 0.15, y + h - 0.20, label, size=9.5,
        color=NAVY, weight="bold", ha="left")
    ax.plot([x + 0.14, x + w - 0.14], [y + h - 0.39] * 2,
            color=EDGE, linewidth=0.7, zorder=3)


def controller(ax):
    x, y, w, h = 0.12, 0.82, 1.89, 2.95
    section(ax, x, y, w, h, "Coordinator", PALE_BLUE)
    pill(ax, 0.30, 3.04, 1.50, 0.34, "GPU / link profiles",
         fill="white", text_color=MUTED, border=EDGE,
         size=7.5, weight="normal")
    pill(ax, 0.30, 2.50, 1.50, 0.38, "Event DAG + critical path",
         fill=BLUE, size=7.2)
    pill(ax, 0.30, 1.96, 1.50, 0.38, "Topology-aware partition",
         fill=TEAL, size=7.2)
    ax.plot([0.28, 1.82], [1.81, 1.81], color=EDGE, linewidth=0.7)
    txt(ax, 0.31, 1.74, "online decision", size=6.6,
        color=MUTED, ha="left")
    pill(ax, 0.30, 1.17, 1.50, 0.43, "Queue-aware DAG routing",
         fill=ORANGE, size=7.15)
    for yy in ((3.04, 2.88), (2.50, 2.34)):
        arrow(ax, 1.05, yy[0], 1.05, yy[1],
              color=MUTED, width=0.95, head=6)
    pill(ax, 0.43, 0.24, 1.24, 0.33, "New request",
         fill="white", text_color=INK, border=EDGE,
         size=7.3, weight="normal")
    arrow(ax, 1.05, 0.57, 1.05, 1.16,
          color=ORANGE, width=1.5, head=8)


def fabric(ax):
    x, y, w, h = 2.44, 0.82, 2.90, 2.95
    section(ax, x, y, w, h, "Multi-cluster GPU fabric", PALE_GREEN)
    # The cluster membership illustrates a shared prefix and two physical
    # suffix corridors; exact GPU-layer intervals are shown in Figs. 04/05.
    box(ax, 2.67, 1.75, 0.80, 0.70,
        face="#E8F1F7", border="#95B3C8", radius=0.06)
    txt(ax, 3.07, 2.34, "C1", size=7.1,
        color=BLUE, weight="bold")
    pill(ax, 2.79, 1.88, 0.56, 0.34, "A100\nprefix",
         fill=BLUE, size=6.5)
    box(ax, 3.83, 2.43, 0.91, 0.78,
        face="#E7F3F0", border="#8BB9B1", radius=0.06)
    txt(ax, 4.29, 3.10, "C3", size=7.1,
        color=TEAL, weight="bold")
    pill(ax, 3.96, 2.55, 0.65, 0.36, "L4 / T4\nlater layers",
         fill=TEAL, size=6.4)
    box(ax, 3.83, 1.14, 0.91, 0.78,
        face="#F0F4F4", border="#AEC2C0", radius=0.06)
    txt(ax, 4.29, 1.81, "C2", size=7.1,
        color=TEAL, weight="bold")
    pill(ax, 3.96, 1.26, 0.65, 0.36, "L4 / T4\nlater layers",
         fill="white", text_color=TEAL, border=TEAL,
         size=6.4)
    pill(ax, 4.89, 1.82, 0.36, 0.35, "Out",
         fill="white", text_color=NAVY, border=NAVY,
         size=6.7)
    # An orange active request path and a gray legal alternative.
    arrow(ax, 3.47, 2.09, 3.81, 2.78,
          color=ORANGE, width=1.85, head=9)
    arrow(ax, 4.74, 2.78, 4.92, 2.15,
          color=ORANGE, width=1.85, head=9)
    arrow(ax, 3.47, 2.03, 3.81, 1.53,
          color=ALT, width=1.0, head=7)
    arrow(ax, 4.74, 1.53, 4.92, 1.85,
          color=ALT, width=1.0, head=7)
    txt(ax, 3.80, 0.96, "orange: selected route   gray: feasible route",
        size=6.5, color=MUTED)


def worker(ax):
    x, y, w, h = 5.70, 0.82, 1.59, 2.95
    section(ax, x, y, w, h, "GPU worker (zoom)", PALE_GOLD)
    pill(ax, 5.87, 2.93, 1.25, 0.33, "Inbound queue",
         fill="white", text_color=INK, border=EDGE,
         size=7.2, weight="normal")
    pill(ax, 5.87, 2.23, 0.71, 0.43, "Placed\nlayers",
         fill=BLUE, size=6.8)
    pill(ax, 6.69, 2.23, 0.43, 0.43, "KV\ncache",
         fill="white", text_color=TEAL, border=TEAL,
         size=6.4)
    pill(ax, 5.87, 1.38, 1.25, 0.34, "Next stage / token",
         fill="white", text_color=INK, border=EDGE,
         size=7.1, weight="normal")
    arrow(ax, 6.23, 2.92, 6.23, 2.67,
          color=NAVY, width=1.1, head=6)
    arrow(ax, 6.58, 2.45, 6.68, 2.45,
          color=TEAL, width=1.0, head=6)
    arrow(ax, 6.68, 2.36, 6.59, 2.36,
          color=TEAL, width=1.0, head=6)
    arrow(ax, 6.23, 2.22, 6.23, 1.73,
          color=NAVY, width=1.1, head=6)
    txt(ax, 6.50, 1.07, "prefill → pinned decode",
        size=6.7, color=MUTED)


def main():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    fig, ax = plt.subplots(figsize=(7.40, 4.00))
    ax.set_xlim(0, 7.40)
    ax.set_ylim(0, 4.00)
    ax.axis("off")
    controller(ax)
    fabric(ax)
    worker(ax)
    # Control messages deploy the layer plan and choose a route at admission.
    arrow(ax, 1.81, 2.15, 2.42, 2.15,
          color=TEAL, width=1.3, dashed=True, head=8)
    txt(ax, 2.12, 2.34, "placement", size=6.4,
        color=TEAL)
    arrow(ax, 1.81, 1.39, 2.66, 1.94,
          color=ORANGE, width=1.75, head=9)
    txt(ax, 2.18, 1.45, "prompt route", size=6.3,
        color=ORANGE)
    # The worker box expands one GPU in the fabric, not an extra pipeline hop.
    bent(ax, [(4.62, 2.91), (5.45, 2.91), (5.69, 2.91)],
         color=MUTED, width=0.95, dashed=True, head=7)
    txt(ax, 5.43, 3.10, "node detail", size=6.5,
        color=MUTED)
    # A bottom loop conveys completion and live queue state back to routing.
    bent(ax, [(6.45, 0.82), (6.45, 0.51),
              (1.56, 0.51), (1.56, 1.16)],
         color=MUTED, width=1.05, dashed=True, head=7)
    txt(ax, 3.98, 0.35, "completion + queue / link availability",
        size=6.8, color=MUTED)
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.99)
    for ext, kwargs in (("pdf", {}), ("svg", {}),
                        ("png", {"dpi": 300})):
        path = HERE / f"ccf_integrated_framework.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.025, **kwargs)
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()

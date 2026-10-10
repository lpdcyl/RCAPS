"""Draw the actual single-cluster layer-compatibility DAG from final artifacts.

The boxes and links are read from placement.json and simulator_cluster.ini.
Only the visual layout and the highlighted example transition are specified here.
"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle


HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "critical_graph" / "runs" / "single_final"
STEM = HERE / "fig15_single_actual_layer_dag"

SHARED = "#75628D"
BRANCH_A = "#32678F"
BRANCH_B = "#C75B39"
CROSS = "#A8B3BA"
EXAMPLE = "#168B78"
INK = "#25313A"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
})


def load_graph():
    placement = json.loads((RUN / "placement.json").read_text(encoding="utf-8"))
    intervals = {int(uid): tuple(bounds)
                 for uid, bounds in placement["intervals"].items()}
    branches = placement["branches"]
    shared = placement["shared"]

    config = ConfigParser()
    if not config.read(RUN / "simulator_cluster.ini", encoding="utf-8"):
        raise FileNotFoundError(RUN / "simulator_cluster.ini")

    def uid(label):
        if label in {"source", "sink"}:
            return label
        prefix = "compute_node_"
        if not label.startswith(prefix):
            raise ValueError(f"Unexpected layout node: {label}")
        return int(label[len(prefix):]) - 2

    links = ast.literal_eval(config["Links"]["names"])
    edges = [(uid(config[name]["in"]), uid(config[name]["out"]))
             for name in links]
    if len(edges) != len(set(edges)):
        raise ValueError("Duplicate links in simulator layout")
    canonical = {("source", shared), (shared, branches[0][0]),
                 (shared, branches[1][0]),
                 (branches[0][-1], "sink"),
                 (branches[1][-1], "sink")}
    for branch in branches:
        canonical.update(zip(branch, branch[1:]))
    if not canonical <= set(edges):
        raise ValueError("A design-branch link is missing from the exported DAG")
    cross = set(edges) - canonical
    membership = {uid: lane for lane, branch in enumerate(branches)
                  for uid in branch}
    for left, right in cross:
        if left not in membership or right not in membership:
            raise ValueError(f"Unexpected extra edge: {left} -> {right}")
        if membership[left] == membership[right]:
            raise ValueError(f"Extra edge is not cross-branch: {left} -> {right}")
        boundary = intervals[left][1]
        start, end = intervals[right]
        if not start <= boundary < end:
            raise ValueError(f"Layer-incompatible edge: {left} -> {right}")

    successors = defaultdict(list)
    for left, right in edges:
        successors[left].append(right)

    @lru_cache(None)
    def count_paths(node):
        return 1 if node == "sink" else sum(count_paths(nxt)
                                             for nxt in successors[node])

    if (9, 3) not in cross or intervals[9][1] != 24:
        raise ValueError("The selected example is absent from the final layout")
    return intervals, branches, shared, canonical, cross, len(edges), count_paths("source")


def arrow(ax, start, end, *, color, width=1.1, alpha=1.0, scale=8, zorder=2):
    patch = FancyArrowPatch(start, end, arrowstyle="-|>",
                            mutation_scale=scale, linewidth=width,
                            color=color, alpha=alpha, zorder=zorder,
                            shrinkA=0, shrinkB=0)
    ax.add_patch(patch)


def gpu_box(ax, uid, bounds, y, color, *, height=0.46, detailed=False):
    start, end = bounds
    inset = 0.08
    rect = Rectangle((start + inset, y - height / 2),
                     end - start - 2 * inset, height,
                     facecolor=color, edgecolor="white", linewidth=0.65,
                     zorder=5)
    ax.add_patch(rect)
    label = f"G{uid}  [{start},{end})" if detailed else str(uid)
    fontsize = 8.4 if detailed else (7.2 if end - start <= 2 else 8.0)
    ax.text((start + end) / 2, y, label, color="white", fontsize=fontsize,
            ha="center", va="center", weight="bold", zorder=6,
            clip_on=True)


def setup_axis(ax, *, xlim, ylim, ticks):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks(ticks)
    ax.set_xlabel("Model layer boundary", color=INK)
    ax.set_yticks([])
    ax.spines[["left", "right", "top"]].set_visible(False)
    ax.spines["bottom"].set_color("#9BA6AD")
    ax.grid(axis="x", color="#E5E9EC", linewidth=0.65)
    ax.set_axisbelow(True)


def draw_full(ax, intervals, branches, shared, cross):
    ys = {shared: 0.0}
    ys.update({uid: 0.95 for uid in branches[0]})
    ys.update({uid: -0.95 for uid in branches[1]})
    setup_axis(ax, xlim=(-4.5, 84.5), ylim=(-1.62, 1.65),
               ticks=[0, 12, 20, 30, 40, 50, 60, 70, 80])

    # Every pale vertical arrow is an actual extra link from the exported layout.
    for left, right in sorted(cross, key=lambda edge: (intervals[edge[0]][1], edge)):
        x = intervals[left][1]
        direction = 1 if ys[right] > ys[left] else -1
        start = (x, ys[left] + direction * 0.25)
        end = (x, ys[right] - direction * 0.25)
        if (left, right) == (9, 3):
            arrow(ax, start, end, color=EXAMPLE, width=2.25,
                  scale=12, zorder=4)
        else:
            arrow(ax, start, end, color=CROSS, width=0.8,
                  alpha=0.68, scale=5.5, zorder=1)

    arrow(ax, (-3.7, 0), (0, 0), color=INK, scale=9)
    for branch, y in ((branches[0], 0.95), (branches[1], -0.95)):
        arrow(ax, (12, 0.24 if y > 0 else -0.24),
              (12, y - 0.25 if y > 0 else y + 0.25),
              color=INK, scale=8)
        for left, right in zip(branch, branch[1:]):
            boundary = intervals[left][1]
            arrow(ax, (boundary - 0.07, y), (boundary + 0.07, y),
                  color=INK, width=0.75, scale=5.5, zorder=7)
        arrow(ax, (80, y), (83.1, 0), color=INK, scale=8)

    gpu_box(ax, shared, intervals[shared], 0, SHARED)
    for branch, y, color in ((branches[0], 0.95, BRANCH_A),
                             (branches[1], -0.95, BRANCH_B)):
        for uid in branch:
            gpu_box(ax, uid, intervals[uid], y, color)
    ax.text(-4.1, 0, "S", ha="center", va="center", fontsize=10,
            weight="bold", color=INK)
    ax.text(83.4, 0, "T", ha="center", va="center", fontsize=10,
            weight="bold", color=INK)
    ax.text(0, 0.35, "Shared prefix", ha="left", va="bottom",
            fontsize=9, color=SHARED, weight="bold")
    ax.text(12, 1.26, "Designed suffix A", ha="left", va="bottom",
            fontsize=9, color=BRANCH_A, weight="bold")
    ax.text(12, -1.31, "Designed suffix B", ha="left", va="top",
            fontsize=9, color=BRANCH_B, weight="bold")


def draw_zoom(ax, intervals, shared):
    setup_axis(ax, xlim=(-0.6, 36.6), ylim=(-1.2, 1.18),
               ticks=[0, 12, 19, 24, 26, 33, 36])
    y_a, y_b = 0.67, -0.67
    gpu_box(ax, shared, intervals[shared], 0, SHARED,
            height=0.48, detailed=True)
    for uid in (9, 17):
        gpu_box(ax, uid, intervals[uid], y_a, BRANCH_A,
                height=0.48, detailed=True)
    for uid in (0, 3, 11):
        gpu_box(ax, uid, intervals[uid], y_b, BRANCH_B,
                height=0.48, detailed=True)
    arrow(ax, (12, 0.24), (12, y_a - 0.25), color=INK, scale=8)
    arrow(ax, (12, -0.24), (12, y_b + 0.25), color=INK, scale=8)
    arrow(ax, (24, y_a - 0.25), (24, y_b + 0.25),
          color=EXAMPLE, width=2.3, scale=11, zorder=8)
    ax.add_patch(Rectangle((24, y_b - 0.24), 2, 0.48,
                           fill=False, edgecolor=EXAMPLE,
                           linewidth=2.1, zorder=9))
    ax.text(25, -1.02, "executed after switch", color=EXAMPLE,
            ha="center", va="top", fontsize=8.1, weight="bold")
    ax.set_title("Actual stitched transition at layer 24", loc="left",
                 fontsize=11, weight="bold", pad=9, color=INK)


def main():
    intervals, branches, shared, _, cross, edge_count, path_count = load_graph()
    fig = plt.figure(figsize=(16, 7.2), facecolor="white")
    full = fig.add_axes([0.065, 0.49, 0.90, 0.39])
    zoom = fig.add_axes([0.065, 0.11, 0.63, 0.27])
    note = fig.add_axes([0.735, 0.11, 0.23, 0.27])
    note.axis("off")
    draw_full(full, intervals, branches, shared, cross)
    draw_zoom(zoom, intervals, shared)

    note.text(0, 0.93, "What this means", fontsize=11, weight="bold",
              color=INK, transform=note.transAxes)
    facts = [
        f"{len(intervals)} GPUs, 80 model layers",
        "2 designed complete suffixes",
        f"{edge_count} exported links; {len(cross)} cross-branch links",
        f"{path_count:,} structural source-to-sink paths",
        "G9 finishes at 24; G3 can continue to 26",
    ]
    for index, line in enumerate(facts):
        note.text(0, 0.76 - index * 0.14, line, fontsize=9.2,
                  color=INK, transform=note.transAxes)
    note.text(0, 0.02,
              "Path count describes graph structure,\nnot live queue or KV feasibility.",
              fontsize=8.1, color="#52616B", transform=note.transAxes)

    fig.text(0.065, 0.955,
             "Actual layer-compatible DAG from the final single-cluster placement",
             fontsize=15, weight="bold", color=INK)
    fig.text(0.065, 0.915,
             "Numbers inside boxes are GPU IDs. Box position and width follow stored layer intervals."
             " Pale arrows are additional cross-branch links; teal marks one real example.",
             fontsize=9.5, color="#52616B")
    fig.text(0.065, 0.025,
             "Source: single_final/placement.json + simulator_cluster.ini."
             " S/T = source/sink; G# = placement GPU ID (simulator node ID = G# + 2)."
             " Intervals use [start, end).",
             fontsize=8.5, color="#52616B")

    for suffix in ("svg", "pdf", "png"):
        fig.savefig(STEM.with_suffix(f".{suffix}"), dpi=240,
                    bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"{STEM}.svg | {edge_count} links | {len(cross)} cross-branch links"
          f" | {path_count} structural paths")


if __name__ == "__main__":
    main()

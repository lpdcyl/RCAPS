"""Plot occupied model-layer intervals by GPU and physical cluster."""

import ast
import configparser

import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

from common import GPU_COLORS, LIGHT, ROOT, official, panel, save


def parse_solution(relative):
    cp = configparser.ConfigParser()
    cp.read(ROOT / relative, encoding="utf-8")
    offset = int(cp["Settings"]["offset"])
    intervals = {}
    for name, raw in cp["Solution"].items():
        node = int(name.rsplit("_", 1)[1]) - offset
        layers = ast.literal_eval(raw)
        if layers:
            assert layers == list(range(min(layers), max(layers) + 1))
            intervals[node] = (min(layers), max(layers) + 1)
    return intervals


def types(scenario):
    config = ("examples/simulation/config/single24.ini" if scenario == "single"
              else "artifact_evaluation/distributed_clusters/config/3cluster24.ini")
    cp = configparser.ConfigParser()
    cp.read(ROOT / config, encoding="utf-8")
    return {i: cp[f"ComputeNode-{i}"]["type"] for i in range(24)}


def draw(ax, solution, gpu_types, scenario, letter):
    intervals = parse_solution(solution)
    order = list(range(24))
    for row, node in enumerate(order):
        ax.add_patch(Rectangle((0, row - 0.4), 80, 0.8,
                               facecolor=LIGHT, edgecolor="none"))
        if node in intervals:
            lo, hi = intervals[node]
            ax.add_patch(Rectangle((lo, row - 0.4), hi - lo, 0.8,
                                   facecolor=GPU_COLORS[gpu_types[node]],
                                   edgecolor="white", linewidth=0.35))
    if scenario == "multi":
        for y in (3.5, 13.5):
            ax.axhline(y, color="#515962", linewidth=0.7, linestyle="--")
        for y, cluster in ((1.5, "C1"), (8.5, "C2"), (18.5, "C3")):
            ax.text(81.2, y, cluster, rotation=90, va="center", ha="left", fontsize=7)
    ax.set_xlim(0, 84)
    ax.set_ylim(23.8, -0.8)
    ax.set_xticks([0, 20, 40, 60, 80])
    ax.set_yticks(range(24), [f"{n}: {gpu_types[n]}" for n in order], fontsize=6.3)
    ax.set_xlabel("Transformer layer")
    ax.set_ylabel("GPU index and type")
    panel(ax, letter)


def main(scenario):
    helix = official(scenario, "helix")
    ours = official(scenario, "integrated")
    gpu_types = types(scenario)
    fig, axes = plt.subplots(1, 2, figsize=(7.15, 5.0), sharey=True)
    draw(axes[0], helix["solution"], gpu_types, scenario, "a")
    draw(axes[1], ours["solution"], gpu_types, scenario, "b")
    handles = [Patch(facecolor=GPU_COLORS[k], label=k) for k in ("A100", "L4", "T4")]
    fig.legend(handles=handles, frameon=False, loc="upper center", ncol=3,
               bbox_to_anchor=(0.53, 0.99))
    fig.subplots_adjust(left=0.13, right=0.95, bottom=0.1, top=0.88, wspace=0.31)
    number = "04" if scenario == "single" else "05"
    save(fig, f"fig{number}_{scenario}_placement")

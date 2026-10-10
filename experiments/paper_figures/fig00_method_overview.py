"""Vector schematic of the three implemented methods; no empirical data encoded."""

from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.pyplot as plt

from common import HELIX, OURS, CANONICAL, GRAY, LIGHT, panel, save


def box(ax, x, y, w, h, label, color, *, pale=False, size=7.3):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.03",
                           facecolor="white" if pale else color,
                           edgecolor=color, linewidth=0.8)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            color=color if pale else "white", fontsize=size)
    return patch


def arrow(ax, xy0, xy1, *, color=GRAY, width=1.1, dashed=False):
    ax.add_patch(FancyArrowPatch(xy0, xy1, arrowstyle="-|>", mutation_scale=7,
                                 color=color, linewidth=width,
                                 linestyle="--" if dashed else "-"))


def setup(ax, letter):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    panel(ax, letter)


def event_dag(ax):
    setup(ax, "a")
    xs = [0.03, 0.27, 0.52, 0.76]
    labels = ["Link", "GPU 1", "Link", "GPU 2"]
    colors = [CANONICAL, HELIX, CANONICAL, HELIX]
    for y, suffix in ((0.64, "r1"), (0.22, "r2")):
        ax.text(0.0, y + 0.075, suffix, ha="right", va="center", fontsize=7)
        for x, label, color in zip(xs, labels, colors):
            box(ax, x, y, 0.19, 0.15, label, color, size=7)
        for x in (0.22, 0.46, 0.71):
            arrow(ax, (x, y + 0.075), (x + 0.05, y + 0.075),
                  color=OURS if y > 0.5 else GRAY,
                  width=1.6 if y > 0.5 else 0.9)
    arrow(ax, (0.36, 0.64), (0.36, 0.37), color=OURS, dashed=True, width=1.4)
    ax.text(0.39, 0.50, "same GPU", fontsize=6.8, color=OURS, va="center")
    ax.text(0.04, 0.03, "Solid: request order     Dashed: resource order",
            fontsize=6.6, color=GRAY)


def placement(ax):
    setup(ax, "b")
    box(ax, 0.01, 0.41, 0.22, 0.19, "Shared\n0--11", HELIX, size=7)
    for y, cluster, color, text in ((0.70, "C2", CANONICAL, "12--79"),
                                     (0.12, "C3", OURS, "12--79")):
        box(ax, 0.43, y, 0.27, 0.18, f"{cluster}\nlayers {text}",
            color, size=6.8)
        arrow(ax, (0.23, 0.51), (0.43, y + 0.09), color=color, width=1.2)
        box(ax, 0.78, y, 0.19, 0.18, "Sink", GRAY, pale=True, size=7)
        arrow(ax, (0.70, y + 0.09), (0.78, y + 0.09), color=color)
    ax.text(0.01, 0.01, "Capacity-bounded layer cuts; link cost guides GPU order",
            fontsize=6.6, color=GRAY)


def scheduling(ax):
    setup(ax, "c")
    box(ax, 0.02, 0.42, 0.14, 0.17, "0", GRAY, pale=True)
    for x, y, label in ((0.38, 0.68, "40: A"), (0.38, 0.19, "40: B"),
                        (0.74, 0.68, "80: C"), (0.74, 0.19, "80: D")):
        box(ax, x, y, 0.2, 0.17, label, HELIX if y > 0.5 else CANONICAL,
            pale=y < 0.5, size=7)
    for p0, p1, chosen in (((0.16, 0.5), (0.38, 0.765), True),
                            ((0.16, 0.5), (0.38, 0.275), False),
                            ((0.58, 0.765), (0.74, 0.765), True),
                            ((0.58, 0.275), (0.74, 0.275), False),
                            ((0.58, 0.765), (0.74, 0.275), False)):
        arrow(ax, p0, p1, color=OURS if chosen else "#AAB0B5",
              width=1.8 if chosen else 0.8)
    ax.text(0.02, 0.04, "Edge finish = max(arrival, release) + service",
            fontsize=6.6, color=GRAY)
    ax.text(0.42, 0.53, "queue snapshot", fontsize=6.8, color=OURS)


def main():
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.2))
    for ax, fn in zip(axes, (event_dag, placement, scheduling)):
        fn(ax)
    fig.subplots_adjust(left=0.04, right=0.98, bottom=0.10, top=0.94,
                        wspace=0.19)
    save(fig, "fig00_method_overview")


if __name__ == "__main__":
    main()

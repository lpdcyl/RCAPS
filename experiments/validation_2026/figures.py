"""Labeled figures of 70B placement ablations and measured bottlenecks."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
COLORS = {"helix": "#555555", "rcaps_coarse": "#78909C",
          "rcaps_full_search": "#E69F00", "rcaps_static_no_graph": "#009E73",
          "rcaps": "#0072B2"}
LABELS = {"helix": "Helix", "rcaps_coarse": "Topology only",
          "rcaps_full_search": "Full graph search",
          "rcaps_static_no_graph": "Static route search", "rcaps": "RCAPS guided"}


def search_figure(data: dict, directory: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.0), constrained_layout=True)
    for ax, scenario in zip(axes, ("single", "multi")):
        summary = data["A_B_and_static_ablation"].get(scenario, {}).get("metrics", {})
        methods = ("helix", "rcaps_coarse", "rcaps_static_no_graph",
                   "rcaps_full_search", "rcaps")
        for x, method in enumerate(methods):
            if method not in summary:
                continue
            stats = summary[method]["tpot_p95_s"]
            ax.bar(x, stats["mean"], color=COLORS[method], width=0.62,
                   label=LABELS[method])
            for offset, value in zip(np.linspace(-0.12, 0.12, len(stats["values"])),
                                     stats["values"]):
                ax.plot(x + offset, value, "o", color="black", markersize=3.5)
        ax.set_title("Single cluster" if scenario == "single" else "Three clusters")
        ax.set_ylabel("p95 TPOT (s/query token)")
        ax.set_xticks(range(len(methods)), [LABELS[name] for name in methods],
                      rotation=23, ha="right")
        ax.grid(axis="y", alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5,
               bbox_to_anchor=(0.5, 1.08), frameon=False)
    fig.savefig(directory / "search_ablation.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def top_keys(profiles: dict, field: str, count=6) -> list[str]:
    keys = set().union(*(profile.get(field, {}) for profile in profiles.values()))
    return sorted(keys, key=lambda key: max(
        profile.get(field, {}).get(key, {}).get("mean", 0.0)
        for profile in profiles.values()), reverse=True)[:count]


def bottleneck_figure(data: dict, scenario: str, directory: Path) -> None:
    profiles = data["A_B_and_static_ablation"].get(scenario, {}).get("resource_profile", {})
    if not all(name in profiles for name in ("rcaps_coarse", "rcaps")):
        return
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    variants = ("rcaps_coarse", "rcaps")
    for ax, field, title, ylabel in (
            (axes[0, 0], "gpu_queue_request_s", "GPU queueing", "Queued request-seconds"),
            (axes[0, 1], "gpu_busy_fraction", "GPU busy fraction", "Fraction of window"),
            (axes[1, 0], "link_dispatch_wait_request_s", "Network dispatch waiting",
             "Waiting request-seconds")):
        keys = top_keys(profiles, field)
        x = np.arange(len(keys))
        for index, variant in enumerate(variants):
            values = [profiles[variant].get(field, {}).get(key, {}).get("mean", 0)
                      for key in keys]
            ax.bar(x + (index - 0.5) * 0.36, values, width=0.36,
                   color=COLORS[variant], label=LABELS[variant])
        ax.set_xticks(x, keys, rotation=35, ha="right", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
    ax = axes[1, 1]
    x = np.arange(2)
    values = [sum(item["mean"] for item in
                  profiles[variant]["gpu_queue_request_s"].values())
              for variant in variants]
    ax.bar(x, values, color=[COLORS[variant] for variant in variants])
    ax.set_xticks(x, [LABELS[variant] for variant in variants])
    ax.set_ylabel("Queued request-seconds")
    ax.set_title("Total GPU queueing")
    ax.set_ylim(0, max(values) * 1.2)
    ax.grid(axis="y", alpha=0.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2,
               bbox_to_anchor=(0.5, 1.04), frameon=False)
    count = len(profiles["rcaps"]["fraction_cross_region"]["values"])
    fig.suptitle(f"Measured bottlenecks: {scenario} ({count} paired seeds)")
    fig.text(0.5, -0.02, "Dispatch waiting includes scheduling and bandwidth contention; "
             "link propagation is measured separately in summary.json.",
             ha="center", fontsize=9)
    fig.savefig(directory / f"bottlenecks_{scenario}.png", dpi=220,
                bbox_inches="tight")
    plt.close(fig)


def network_components_figure(data: dict, scenario: str, directory: Path) -> None:
    """Show dispatch waiting, bandwidth service, and propagation separately."""
    profiles = data["A_B_and_static_ablation"].get(scenario, {}).get(
        "resource_profile", {})
    if not all(name in profiles for name in ("rcaps_coarse", "rcaps")):
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    components = (("link_dispatch_wait_request_s", "Dispatch waiting", "#E69F00"),
                  ("link_service_request_s", "Bandwidth service", "#0072B2"),
                  ("link_propagation_request_s", "Propagation", "#009E73"))
    for ax, method in zip(axes, ("rcaps_coarse", "rcaps")):
        profile = profiles[method]
        keys = sorted(set().union(*(profile.get(field, {})
                                    for field, _, _ in components)),
                      key=lambda key: sum(profile.get(field, {}).get(key, {}).get(
                          "mean", 0.0) for field, _, _ in components),
                      reverse=True)[:6]
        x = np.arange(len(keys))
        base = np.zeros(len(keys))
        for field, label, color in components:
            values = np.array([profile.get(field, {}).get(key, {}).get("mean", 0.0)
                               for key in keys])
            ax.bar(x, values, bottom=base, color=color, label=label)
            base += values
        ax.set_xticks(x, keys, rotation=35, ha="right", fontsize=8)
        ax.set_title(LABELS[method])
        ax.set_ylabel("Cumulative request-seconds")
        ax.grid(axis="y", alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3,
               bbox_to_anchor=(0.5, 1.08), frameon=False)
    count = len(profiles["rcaps"]["fraction_cross_region"]["values"])
    fig.suptitle(f"Measured network time: {scenario} ({count} paired seeds)")
    fig.text(0.5, -0.02, "Dispatch waiting includes scheduler decisions and "
             "bandwidth contention; components are measured separately.",
             ha="center", fontsize=9)
    fig.savefig(directory / f"network_components_{scenario}.png", dpi=220,
                bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    source = HERE / "summary.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    directory = HERE / "figures"
    directory.mkdir(exist_ok=True)
    search_figure(data, directory)
    for scenario in ("single", "multi"):
        bottleneck_figure(data, scenario, directory)
        network_components_figure(data, scenario, directory)
    print(directory)


if __name__ == "__main__":
    main()

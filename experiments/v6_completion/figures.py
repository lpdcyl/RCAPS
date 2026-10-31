"""Rebuild publication figures only from audited per-seed CSVs."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.v5_core_supplement.run import sha, write

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
COLORS = {"HH": "#5975a4", "HHplus": "#e6a141", "V4": "#31946b"}


def records(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def grouped_tpot(path, name, labels):
    data = records(path)
    scenarios = ("single", "multi")
    cells = ("HH", "HHplus", "V4")
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), layout="constrained")
    for ax, scenario in zip(axes, scenarios):
        for offset, cell in enumerate(cells):
            ys, errors = [], []
            for label in labels:
                selected = [float(r["tpot_p95_s"]) for r in data if
                            r["scenario"] == scenario and r["condition"] == label and
                            r["cell"] == cell and r["status"] == "completed"]
                ys.append(mean(selected) if len(selected) == 5 else np.nan)
                errors.append(stdev(selected) if len(selected) == 5 else 0)
            x = np.arange(len(labels)) + (offset - 1) * 0.25
            ax.bar(x, ys, width=0.24, yerr=errors, capsize=2,
                   color=COLORS[cell], label=cell)
        ax.set_title(scenario.capitalize())
        ax.set_ylabel("P95 TPOT (s)")
        ax.set_xticks(np.arange(len(labels)), labels, rotation=30, ha="right")
        ax.grid(axis="y", alpha=0.2)
        ax.legend(ncol=3)
    save(fig, name)


def bandwidth():
    data = records(HERE / "bandwidth_threshold/individual.csv")
    cells = ("sparse_chunk", "sparse_nochunk", "canonical_chunk", "canonical_nochunk")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for ax, points, title, selector, xkey in (
        (axes[0], [12.5, 25, 50, 100, 200], "Bandwidth sweep (threshold 50 MB/s)",
         lambda r: float(r["threshold_MBps"]) == 50, "bandwidth_MBps"),
        (axes[1], [25, 50, 100], "Threshold sweep (bandwidth 50 MB/s)",
         lambda r: float(r["bandwidth_MBps"]) == 50, "threshold_MBps")):
        for cell in cells:
            values = []
            for point in points:
                group = [float(r["tpot_p95_s"]) for r in data if selector(r) and
                         float(r[xkey]) == point and r["cell"] == cell and
                         r["status"] == "completed"]
                values.append(mean(group) if len(group) == 5 else np.nan)
            ax.plot(points, values, marker="o", label=cell.replace("_", " "))
        ax.set_title(title)
        ax.set_xlabel("MB/s")
        ax.set_ylabel("P95 TPOT (s)")
        ax.grid(alpha=0.2)
        ax.legend(fontsize=7)
    save(fig, "bandwidth_threshold_tpot")


def capacity():
    rows = records(HERE / "session_capacity/slo_capacity.csv")
    scenarios = ("single", "multi")
    cells = ("HH", "HHplus", "V4", "batch", "marginal", "cycle",
             "no_session", "k1", "k1_5", "k3", "k4")
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), layout="constrained")
    for ax, scenario in zip(axes, scenarios):
        subset = {(r["scenario"], r["cell"]): r for r in rows}
        values = [subset[scenario, cell]["largest_tested_feasible_load"] for cell in cells]
        heights = [float(x) if x else 0 for x in values]
        ax.bar(cells, heights, color=[COLORS.get(c, "#78909c") for c in cells])
        for i, value in enumerate(values):
            if not value:
                ax.text(i, max(heights, default=1) * 0.03, "none", rotation=90,
                        ha="center", va="bottom", fontsize=7)
        ax.set_title(scenario.capitalize())
        ax.set_ylabel("Largest certified offered load (tokens/s)")
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.2)
    save(fig, "session_capacity_grid")


def weight_online():
    rows = records(HERE / "weight_online/individual.csv")
    labels = ("w0_low", "w0_high", "w1_low", "w1_high", "w2_low", "w2_high")
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    for case in ("C1_single", "C1_multi"):
        values = []
        for label in labels:
            group = [float(r["tpot_p95_s"]) for r in rows if r["case"] == case
                     and r["label"] == label and r["status"] == "completed"]
            values.append(mean(group) if len(group) == 5 else np.nan)
        ax.plot(labels, values, marker="o", label=case)
    ax.set_ylabel("P95 TPOT (s)")
    ax.set_title("Placement-weight sensitivity")
    ax.grid(alpha=0.2)
    ax.legend()
    save(fig, "placement_weights_tpot")


def scalability():
    rows = records(HERE / "scalability/individual.csv")
    fig, axes = plt.subplots(1, 2, figsize=(8, 4), layout="constrained")
    for ax, field, ylabel in ((axes[0], "route_mean_us", "Mean route wall time (µs)"),
                              (axes[1], "route_p95_us", "P95 route wall time (µs)")):
        values = []
        for size in (48, 96):
            group = [float(r[field]) for r in rows if int(r["size"]) == size and
                     r["status"] == "completed"]
            values.append(mean(group) if len(group) == 5 else np.nan)
        ax.bar(["48", "96"], values, color="#5975a4")
        ax.set_xlabel("GPU count")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.2)
    save(fig, "scalability_route_time")


def main():
    grouped_tpot(HERE / "robustness/individual.csv", "robustness_tpot",
                 ("profile10", "profile20", "bandwidth20", "bandwidth50",
                  "latency20", "activation_kv_low20", "activation_kv_high20",
                  "singleton1", "boundary50ms"))
    grouped_tpot(HERE / "generalization/individual.csv", "generalization_tpot",
                 ("prompt2", "prompt4", "output_half", "output2",
                  "gamma_cv2", "gamma_cv4"))
    bandwidth()
    capacity()
    weight_online()
    scalability()
    files = sorted(OUT.glob("*.png")) + sorted(OUT.glob("*.pdf"))
    assert len(files) == 12
    write(OUT / "FINAL_AUDIT.json", dict(passed=True, figure_pairs=6,
          sources={p.relative_to(HERE).as_posix(): sha(p) for p in (
              HERE / "robustness/individual.csv", HERE / "generalization/individual.csv",
              HERE / "bandwidth_threshold/individual.csv",
              HERE / "session_capacity/slo_capacity.csv",
              HERE / "weight_online/individual.csv", HERE / "scalability/individual.csv")},
          outputs={p.name: sha(p) for p in files}))


if __name__ == "__main__":
    main()

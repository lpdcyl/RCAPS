"""Shared publication style for Challenge 2 data-driven figures."""

from pathlib import Path

import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = PROJECT_ROOT / "results/challenge2"
POINTS_CSV = RESULT_DIR / "challenge2_point_results.csv"
COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00")

plt.rcParams.update(
    {
        "font.size": 10,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "mathtext.fontset": "stix",
    }
)


def save_figure(figure: plt.Figure, name: str) -> None:
    """Save a vector figure plus a raster preview for render verification."""

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(RESULT_DIR / f"{name}.pdf")
    figure.savefig(RESULT_DIR / f"{name}_preview.png")
    plt.close(figure)

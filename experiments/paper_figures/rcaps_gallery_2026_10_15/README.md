# RCAPS experiment figure gallery (2026-10-15)

This folder currently contains the **source code and annotated figure index for 39 RCAPS V2/V1 experimental plots**. Rendered PNG/SVG plots, the multipage PDF and ZIP gallery **have not yet been committed to GitHub**; they remain available as downloads in the original ChatGPT conversation.

- `INDEX.md` — Chinese plot-by-plot explanations and links to experiment data sources.
- `build_rcaps_figures.py` — reproducible Matplotlib plotting definitions and data transcribed from audited repository reports.

## Local rebuild

Install `matplotlib`, `numpy`, and a CJK-compatible font. Before running, adjust the output paths `OUT`, `PDF`, `ZIP`, and `INDEX` at the top of the script, which currently point to the original `/mnt/data` workspace, and set `plt.rcParams['font.family']` to a font available on your computer (e.g., `Noto Sans CJK SC`).

```bash
python experiments/paper_figures/rcaps_gallery_2026_10_15/build_rcaps_figures.py
```

## Scope and limitations

Some plots are **V1 history**, not V2 generalization; three-seed simulations are not significance tests or real-GPU measurements. Stronger alternatives sometimes tie or exceed V2. Failed windows cannot be converted into full-window performance values. The 42-GPU plot illustrates an original Helix artifact configuration, not a completed RCAPS scaling benchmark.

Existing plots outside this new folder are unchanged.

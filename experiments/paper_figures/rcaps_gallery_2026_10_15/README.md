# RCAPS experiment figure gallery (2026-10-15)

This directory holds **39 experiment figures** generated from audited results in this repository. The figures and index are for research presentation and paper drafting, and do not constitute new experiments.

- `INDEX.md`: Chinese descriptions, experiment citations, and per-figure PNG/SVG references.
- `SVG/`: renderable vector versions of all 39 figures.
- `PNG/`: raster preview versions (also included in the downloadable ZIP bundle).
- `build_rcaps_figures.py`: reproducible Matplotlib plotting script with embedded, report-derived numerical inputs.
- `RCAPS_V2_V1_实验图册_2026-10-15.pdf`: 39-page report.
- `RCAPS_全部实验图_PNG_SVG_2026-10-15.zip`: portable archive.

**Evidence boundaries.** Some plots use V1 historical results, not V2; V1 load and RTT sensitivity does **not** demonstrate V2 generalization. Formal results use three seeds and simulation rather than physical GPU measurements. Some method alternatives are approximate ties or negative results. Helix's 42-GPU example is an original artifact configuration, not an RCAPS experiment. Failed windows are flagged and not replaced with estimated results. See individual captions in `INDEX.md`.

To regenerate after installing `matplotlib`, `numpy` and a CJK font (prefer Noto Sans CJK):

```bash
python experiments/paper_figures/rcaps_gallery_2026_10_15/build_rcaps_figures.py
```

Existing figures directly under `experiments/paper_figures/` are preserved and remain unchanged.

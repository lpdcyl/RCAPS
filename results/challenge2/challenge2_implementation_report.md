# Challenge 2 Implementation Report

## Modified and added files

Modified:

- `src/carbon/config.py` — `CBGPConfig` and `load_cbgp_config`.

Added:

- `src/analysis/carbon_bottleneck.py`
- `src/optimizer/cbgp.py`
- `tests/test_cbgp.py`
- `configs/challenge2_cbgp.yaml`
- `experiments/exp_challenge2.py`
- `experiments/verify_challenge2_results.py`
- `experiments/challenge2_figures/paper_plot_style.py`
- `experiments/challenge2_figures/gen_fig1_routing_gap_heatmap.py`
- `experiments/challenge2_figures/gen_fig2_gap_closed_heatmap.py`
- `experiments/challenge2_figures/gen_fig3_gap_vs_reduction.py`
- `experiments/challenge2_figures/gen_fig4_runtime.py`
- `experiments/challenge2_figures/gen_fig5_carbon_comparison.py`
- `results/challenge1_final_report.md`
- formal Challenge 2 reports and outputs under `results/challenge2/`.

No existing Phase 3/3.5 experiment source or historical result was modified.

## New classes and functions

`CarbonBottleneckReport` and `BoundaryBottleneck` capture compute/network
utilization, carbon asymmetry, low-carbon headroom, active boundaries, and
priority scores. `analyze_carbon_bottlenecks` extracts these signals from
existing flow/graph data.

`CBGPResult` and `CBGPIteration` record placement, flow, candidate counts,
optimization calls, visited signatures, termination, and wall time.
`generate_local_boundary_candidates` implements pair shifts and coordinated
shared-cut shifts. `solve_cbgp` performs the deterministic bounded search.

## Configuration and hash

Formal config: `configs/challenge2_cbgp.yaml`

```text
bottleneck_utilization_threshold = 0.85
max_boundary_shift = 8
max_iterations = 4
min_relative_improvement = 0.0001
solver_tolerance = 1e-8
placement_gap_thresholds = [0.01, 0.03, 0.05]
random_seed = 20260921
```

SHA-256:

```text
5b34633bc812c991e50dc7f99cafc960d93816c1d2808250e9745add9a245fc2
```

The YAML was frozen before the formal run and was not modified afterward.

## Tests and commands

Final test command:

```text
D:\software\miniconda\envs\gllm\python.exe -m pytest -q
```

Result: **68 passed, 0 failed, 0 skipped, 0 warnings**.

Phase 3.5 regression command:

```text
D:\software\miniconda\envs\gllm\python.exe -u -c "from pathlib import Path; from experiments.exp_phase35 import run_phase35; run_phase35(output_dir=Path('results/challenge2_phase35_regression'))"
```

Formal experiment command:

```text
D:\software\miniconda\envs\gllm\python.exe -u -m experiments.exp_challenge2
```

Representative recomputation:

```text
D:\software\miniconda\envs\gllm\python.exe -m experiments.verify_challenge2_results
```

Figure generation runs the five scripts in
`experiments/challenge2_figures/`; each writes a vector PDF and a PNG preview.

## Outputs

- `results/challenge1_final_report.md`
- `results/challenge2/challenge2_point_results.csv`
- `results/challenge2/challenge2_summary.csv`
- `results/challenge2/challenge2_scenario_summary.csv`
- `results/challenge2/challenge2_failure_cases.csv`
- `results/challenge2/challenge2_runtime_summary.csv`
- `results/challenge2/challenge2_verification.csv`
- `results/challenge2/challenge2_config_hash.txt`
- `results/challenge2/challenge2_report.md`
- `results/challenge2/challenge2_implementation_report.md`
- `results/challenge2/figure1_routing_gap_heatmap.pdf`
- `results/challenge2/figure2_gap_closed_heatmap.pdf`
- `results/challenge2/figure3_gap_vs_reduction.pdf`
- `results/challenge2/figure4_runtime_comparison.pdf`
- `results/challenge2/figure5_normalized_carbon.pdf`
- `results/challenge2/latex_includes.tex`

## Runtime summary

The 930-point run completed successfully. Median wall-clock measurements were
1.154 ms for routing, 4.733 ms for guided CBGP, 4.666 ms for unguided local
search, and 329.809 ms for the Joint MILP Oracle. These are recorded in
`challenge2_runtime_summary.csv` and are environment-specific simulator
measurements.

## Scope boundary

Challenge 1 consistency is documented in `results/challenge1_final_report.md`.
Challenge 2 is complete. Challenge 3 was not started: no dynamic CI trace,
scheduler, dispatch, migration, hysteresis, or other dynamic controller was
implemented.

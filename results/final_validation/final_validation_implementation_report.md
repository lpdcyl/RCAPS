# Final Validation implementation report

## Branch and commits

- Starting tag: `prototype-before-final-validation` at `858541a`.
- Working branch: `final-validation`.
- Validation artifacts and tests are committed on this branch; the completion
  summary records the resulting final commit hash.

## Added implementation

- `src/carbon/stage.py`: `StageWorkload`, `StageCarbonResult`,
  `WorkloadWeightedEnergyProvider`, and stage-aware carbon evaluation.
- `src/carbon/trace.py`: canonical historical CSV support,
  `HistoricalCITraceLoader`, and explicit region mapping adapter.
- `configs/final_validation.yaml`: parameterized stage workloads, SLO fields
  marked disabled/unsupported, and historical-source controls.
- `experiments/import_historical_ci.py`: raw API JSON to canonical CSV
  preprocessing with source metadata and SHA-256.
- `experiments/exp_final_validation.py`: stage-aware and historical experiments.
- `experiments/final_validation_figures/`: four reproducible vector-PDF/PNG
  figure scripts.
- `tests/test_final_validation.py`: stage semantics, compatibility, linearity,
  historical loader, and region mapping tests.

## Modified implementation

- `src/carbon/config.py`: explicit prefill/decode phase parsing and legacy scalar
  energy compatibility. Existing decode-only callers retain their values.
- `configs/energy_profiles.yaml`: added parameterized prefill profiles while
  preserving all legacy decode values.

## API and compatibility

`ConfiguredLinearEnergyProvider` remains the existing provider. Explicit phase
profiles now support `prefill` and `decode`; legacy `joules_per_token` input is
duplicated into both phases. Carbon flow and placement APIs remain unchanged.
The stage layer evaluates both phases over the same validated flow edges and
preserves the existing Joule-to-kWh conversion.

## Data source and preprocessing

Source: UK National Grid Carbon Intensity API, endpoint and retrieval metadata
recorded in `data/carbon/metadata/uk_grid_intensity_2025-01-01.json`. The raw
JSON is unmodified. Actual 30-minute observations were emitted as canonical
`timestamp,region,carbon_intensity_g_per_kwh` CSV; no interpolation was used.
The source covers one GB signal and is mapped to both synthetic simulator
regions, explicitly limiting the claim to temporal ingestion.

## Tests and commands

```text
D:\software\miniconda\envs\gllm\python.exe -m pytest -q
D:\software\miniconda\envs\gllm\python.exe -m experiments.import_historical_ci
D:\software\miniconda\envs\gllm\python.exe -m experiments.exp_final_validation
D:\software\miniconda\envs\gllm\python.exe -m experiments.final_validation_figures.gen_fig1_trace_flow
D:\software\miniconda\envs\gllm\python.exe -m experiments.final_validation_figures.gen_fig2_cumulative_carbon
D:\software\miniconda\envs\gllm\python.exe -m experiments.final_validation_figures.gen_fig3_stage_workloads
D:\software\miniconda\envs\gllm\python.exe -m experiments.final_validation_figures.gen_fig4_validation_summary
```

The test suite currently contains 81 passing tests. Legacy Phase 3.5 (930
points), Challenge 2 (930 points), and Challenge 3 (135 points) were rerun in
new `results/final_validation/` subdirectories without overwriting historical
formal results.

## Deliberate non-implementation

No request queue, arrival generator, service-time model, latency estimator,
SLO evaluator, migration model, new scheduler family, RL method, or Challenge 4
was added. The original simulator audit demonstrates that those objects do not
exist to integrate safely.

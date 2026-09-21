# Phase 1B — Placement-aware Carbon Flow Foundation

Status: **PASSED**

Environment: Conda `gllm`, Python 3.10.20. The repository still has no Git
metadata, so `git status --short` reports that it is not a Git repository.

## 1. Actual modified files

- `src/carbon/model.py`
- `src/optimizer/placement_milp.py`
- `tests/test_carbon_model.py`
- `tests/test_carbon_flow.py`
- `tests/test_carbon_placement.py`
- `results/phase1b_carbon_model_implementation.md` (this report)

The regression run also created the isolated output directory
`results/phase1b_phase35_regression/`. No file under `experiments/` or
`configs/` was modified, and no historical `results/phase35_*` file was
overwritten. The historical summary and boundary CSV modification timestamps
remained unchanged.

## 2. Added classes and functions

- `CarbonIntensityProvider`: runtime-checkable protocol exposing
  `get_ci(region, timestamp=None) -> float`.
- `ConstantCIProvider`: immutable adapter around a static region-to-CI mapping.
- `CarbonIntensityInput`: Python 3.10-compatible input type alias accepting the
  legacy mapping or a provider.
- `as_ci_provider`: adapts legacy mappings without changing callers.
- `resolve_ci_snapshot`: resolves each unique requested region exactly once.
- `validate_carbon_intensity_g_per_kwh`: rejects negative and non-finite CI.
- `operational_carbon_g`: shared joule/kWh carbon conversion.

## 3. CI provider design

`ConstantCIProvider` copies and validates its input mapping and ignores the
optional timestamp. Known regions return their configured value exactly.
Unknown regions raise an explicit `ValueError`; there is no zero default,
fallback, or region inference. No third-party dependency was added.

## 4. Snapshot design

Both `CarbonCostModel.build` and `solve_carbon_aware_placement` call
`resolve_ci_snapshot` once at the start of an invocation. The helper deduplicates
and sorts regions, calls the provider once per unique region, validates the
result, and returns a plain `dict[str, float]`. All subsequent model and MILP
loops use this resolved snapshot. The placement solver also passes that static
snapshot into its fixed-placement validation, so it never re-queries the live
provider during the same optimization invocation.

## 5. Backward compatibility

The existing `carbon_intensity_by_region` parameter name, positional order, and
mapping call form are unchanged. Existing Phase 3/3.5 experiment callers were
not edited. A `Mapping[str, float]` is internally wrapped by
`ConstantCIProvider`. All existing result fields remain present.

## 6. Unit system

- Energy: J/token
- Carbon intensity: gCO2/kWh
- GPU carbon cost: gCO2/token
- Flow: token/s
- Optimization objective: gCO2/s
- Conversion: `CI * energy / 3_600_000`, mathematically identical to
  `energy / 3_600_000 * CI`
- Network-edge carbon cost: zero (unchanged)

The exact conversion test verifies that 3,600,000 J/token at 1 gCO2/kWh equals
1 gCO2/token.

## 7. Shared Flow/Placement carbon semantics

`operational_carbon_g` is now the single conversion used by both fixed-placement
`CarbonCostModel` construction and joint placement MILP coefficient
construction. The joint solution is reconstructed and validated through the
same `CarbonCostModel` plus fixed-placement carbon-flow optimizer. Tests also
recompute the objective as `sum(gpu_flow * gpu_carbon_cost)`.

## 8. Added tests

Nine tests were added, covering:

1. Exact physical-unit conversion.
2. CI linearity.
3. Energy linearity.
4. Equal-workload regional CI ratios.
5. Constant-provider timestamp invariance and explicit unknown-region failure.
6. Legacy mapping/provider equivalence within `1e-12`.
7. One provider lookup per unique region with timestamp propagation.
8. Fixed-flow objective/manual-sum consistency.
9. Joint-placement snapshot and shared-cost consistency.

## 9. Pytest result

Executed:

```text
D:\software\miniconda\envs\gllm\python.exe -m pytest -q
```

Result: **58 passed in 13.97s**, with no failures, skips, or warnings. The
original 49-test baseline and all 9 new tests passed.

## 10. Phase 3.5 numerical regression

Executed `experiments.exp_phase35.run_phase35` with output redirected to
`results/phase1b_phase35_regression/`.

- Experiment points: 930
- Boundary/signature-switch rows: 309
- Valid non-degenerate crossings: 42
- Degenerate switches: 248
- Symmetric baseline `F_H`: 164.0
- Symmetric baseline `F_target`: 155.8 (serialized float: 155.79999999999998)
- Symmetric maximum routing gap: 0.0042435542982061 = 0.424355%
- Global maximum routing gap: 0.1839073755431772 = 18.390738%

The 1%, 3%, and 5% classifications are exactly equal to the historical
baseline. Placement, flow-signature, and boundary classifications are also
exactly equal.

## 11. Maximum numerical error versus historical baseline

| Field | Maximum absolute error |
|---|---:|
| `F_H` | 0.0 |
| `F_target` | 0.0 |
| `routing_carbon` | 0.0 |
| `joint_carbon` | 0.0 |
| `routing_gap` | 0.0 |

All required errors are below the `1e-9` tolerance.

## 12. Known limitations

- Only the constant provider is implemented; no trace-backed or dynamic CI
  provider exists.
- The timestamp is an interface/snapshot input only and does not change values
  for `ConstantCIProvider`.
- Accounting remains operational GPU-compute carbon only; network energy is
  outside scope.
- No scheduler, dispatch, migration, hysteresis, BACR, CBGP, RL, GNN, LARAC, or
  new placement algorithm was added.
- The workspace has no Git metadata, so change status must be tracked by the
  explicit file list above.

## 13. Readiness for Phase 1C / Challenge 2

**Yes.** Phase 1B satisfies the required unit, API compatibility, snapshot,
flow/placement consistency, full-test, and historical numerical-regression
gates. Phase 1C / Challenge 2 was not started and requires separate user
authorization.

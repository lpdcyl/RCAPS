# Challenge 2 Report — Carbon-Bottleneck-Guided Placement

Status: **COMPLETE**

This study is a deterministic, parameterized, synthetic simulation study. It
does not claim measurements from a production data center, first place, SOTA,
or universal optimality.

## 1. Motivation

Carbon-aware routing can often exploit low-carbon paths without changing model
placement. In other operating regions, the fixed Helix placement removes the
low-carbon compute paths from the feasible Serving Graph, so routing alone is
structurally insufficient. Challenge 2 asks whether a small, interpretable
placement search can recover part of the benefit of the global placement oracle
without solving the global placement MILP at every point.

## 2. Problem formulation

For a fixed Helix placement `P_H`:

`C_R = min_f C(P_H, f)`.

The global placement-and-routing oracle is:

`C_J = min_(P,f) C(P, f)`.

The routing gap is `Gap = (C_R - C_J) / C_R`. The formal primary labels use
the predeclared thresholds `Gap <= 1%` for routing-sufficient and `Gap >= 3%`
for placement-necessary; the 5% threshold is reported as a sensitivity label.
For non-sufficient points, `GapClosed = (C_R - C_CBGP)/(C_R - C_J)`.

## 3. Method: CBGP

Carbon-Bottleneck-Guided Placement starts from `P_H` and repeats a bounded,
deterministic local search:

1. Solve the fixed-placement carbon-flow LP.
2. Measure compute saturation, network saturation, per-layer carbon asymmetry,
   and spare capacity on lower-carbon GPUs.
3. Prioritize active strict boundaries in the Serving Graph.
4. Generate one-boundary pair shifts and coordinated shifts of all intervals
   sharing a layer cut. The latter is necessary when parallel Helix paths share
   a boundary.
5. Reuse `LayerPlacement.validate`, throughput-profile checks, graph
   connectivity, and max-flow feasibility before the carbon LP.
6. Evaluate feasible candidates using the same frozen CI snapshot and carbon
   semantics as routing and the Joint Oracle.
7. Accept only a relative improvement of at least 0.01%; stop on no candidate,
   no feasible candidate, threshold failure, or four iterations. Visited
   placement signatures prevent cycles.

Dual/shadow prices were not used: the current HiGHS LP path does not retain
stable duals in the project result object, and equivalent paths can make them
non-robust. CBGP therefore depends only on observable capacity and cost signals.

## 4. Implementation

- `src/analysis/carbon_bottleneck.py`: `CarbonBottleneckReport`,
  `BoundaryBottleneck`, and bottleneck extraction.
- `src/optimizer/cbgp.py`: candidate generation, coordinated-cut moves,
  feasibility filtering, greedy search, cycle prevention, and diagnostics.
- `src/carbon/config.py`: validated `CBGPConfig` and YAML loader.
- `configs/challenge2_cbgp.yaml`: frozen formal parameters.
- `experiments/exp_challenge2.py`: frozen-grid evaluation and aggregations.
- `experiments/verify_challenge2_results.py`: representative-point recomputation.
- `experiments/challenge2_figures/`: reproducible publication-style figure
  scripts and shared plotting style.
- `tests/test_cbgp.py`: ten Challenge 2 unit/invariant tests.

## 5. Correctness

The final test suite contains **68 passed, 0 failed, 0 skipped, 0 warnings**.
It includes compute/network bottleneck detection, candidate generation and
memory filtering, interval continuity, deterministic output, no-benefit and
beneficial toy cases, Oracle ordering, and termination.

Across all 930 formal points, the invariant `C_J <= C_CBGP <= C_R` held within
the project tolerance. Representative recomputation of routing-sufficient,
placement-necessary, CBGP-success, and CBGP-failure points found maximum
absolute error `8.33e-17`; manual flow-carbon sums, throughput constraints, and
all three placement signatures matched.

## 6. Phase 3.5 regression

The isolated output is `results/challenge2_phase35_regression/`.

- 930 points
- 309 boundary/signature rows
- 42 valid non-degenerate crossings
- Symmetric maximum gap: 0.424355%
- Global maximum gap: 18.390738%
- Maximum absolute error for `F_H`, `F_target`, `routing_carbon`,
  `joint_carbon`, and `routing_gap`: 0.0
- 1% / 3% / 5% classifications: exactly identical to Phase 1B

Historical Phase 3.5 files were not overwritten.

## 7. Main results

The formal Challenge 2 grid contains 930 points:

| Metric | Result |
|---|---:|
| Routing-sufficient (`Gap <= 1%`) | 728 |
| Placement-necessary (`Gap >= 3%`) | 170 |
| Placement-necessary (`Gap >= 5%`) | 145 |
| CBGP-improved points (`reduction > 0.01%`) | 63 |
| Necessary-region points improved | 59 / 170 |
| Mean carbon reduction vs. routing | 0.3944% |
| Maximum carbon reduction vs. routing | 7.1383% |
| Mean GapClosed in necessary region | 32.95% |
| Median GapClosed in necessary region | 0.00% |
| Maximum GapClosed | 100.00% |

Thus CBGP is useful in a subset of placement-necessary cases, but it does not
recover the global placement benefit uniformly.

## 8. Placement Necessity Region

The necessary region is concentrated in high GPU heterogeneity under selected
network constraints. Scenario-level counts are:

| GPU scenario | Points | Routing-sufficient | Placement-necessary | CBGP changes | Max reduction |
|---|---:|---:|---:|---:|---:|
| symmetric | 341 | 341 | 0 | 0 | 0.0000% |
| moderate asymmetric | 31 | 29 | 0 | 0 | 0.0000% |
| commodity region | 279 | 249 | 11 | 0 | 0.0000% |
| high asymmetric | 279 | 109 | 159 | 63 | 7.1383% |

The commodity result is important: its 11 necessary points did not produce an
unjustified placement change. In high asymmetry, CBGP improves 63 points, but
many Oracle placements require a coordinated GPU-stage reassignment beyond a
single local boundary cut.

## 9. Efficiency

Median wall-clock times over 930 points were:

| Method | Median | Mean | P95 |
|---|---:|---:|---:|
| Routing-only | 1.154 ms | 1.185 ms | 1.468 ms |
| Guided CBGP | 4.733 ms | 5.300 ms | 7.469 ms |
| Unguided local search | 4.666 ms | 5.419 ms | 9.010 ms |
| Joint MILP Oracle | 329.809 ms | 365.216 ms | 741.367 ms |

CBGP's median wall time is approximately 69.7× lower than the Joint Oracle in
this simulator. Guided CBGP generated at most 11 local candidates (median 3),
versus a much larger global layer-count assignment space. Runtime values are
single-run wall-clock measurements on the fixed `gllm` environment; they are
comparative simulator timings, not hardware performance claims.

## 10. Sensitivity

- **GPU heterogeneity:** high asymmetry is the only scenario with substantial
  CBGP activity. Symmetric and moderate scenarios remain routing-sufficient in
  the formal primary label.
- **CI ratio:** CBGP gains occur when regional carbon asymmetry aligns with a
  feasible local boundary shift. A high CI ratio alone does not guarantee a
  local candidate can preserve throughput.
- **Network capacity:** high-asymmetric Gap and CBGP benefit are non-monotonic.
  At capacity 1–2 token/s, mean GapClosed is high (approximately 0.99 and
  0.90 respectively); at capacities 10–30 token/s, Oracle gaps can be larger
  while local candidates often fail the throughput filter.
- **Rho:** the existing rho sensitivity remains non-monotonic. Maximum gaps
  are approximately 0.106% (`rho=0.90`), 0.424% (`rho=0.95`), and 0% at
  `rho=0.98` and `1.00`; no monotone placement-necessity claim is made.

## 11. Ablation

The deterministic unguided local search uses the same frozen shift, iteration,
and improvement limits but does not filter boundaries by bottleneck relevance.
Guidance reduced the candidate set in 48/930 points and produced the same count
in 882/930 points. It was not uniformly better: unguided search found lower
carbon in 30 points, while guided search never had a strictly lower result in
this comparison. This negative ablation is retained: the current bottleneck
prioritization is a useful interpretability signal, but not yet a reliable
efficiency/improvement dominance guarantee.

## 12. Failure cases

`results/challenge2/challenge2_failure_cases.csv` contains 111 primary
placement-necessary points where GapClosed was below 0.5. Every recorded case
had the same evidence-backed reason: no local pair or coordinated-cut candidate
passed the throughput target. The largest-gap high-asymmetric case has a
substantial Oracle improvement, but the Oracle changes GPU-stage assignment;
the current local boundary neighborhood cannot reach it without a multi-stage
reassignment. These cases are not deleted or re-tuned away.

## 13. Limitations

- All results are synthetic, parameterized simulations with configured energy
  profiles, CI values, and network capacities.
- CBGP is a bounded greedy local search; it does not claim global optimality.
- The current strict-boundary representation and profiled 8/16/24-layer
  throughput granularity limit candidate moves.
- No migration, request scheduling, dynamic dispatch, hysteresis, dynamic CI
  trace, network operational energy, RL/GNN/LARAC, or Challenge 3 component is
  implemented.
- Runtime measurements are environment-specific and single-run.

## 14. Conclusion

Challenge 2 is successfully completed. CBGP is correct, finite, reproducible,
and substantially cheaper than the Joint Oracle. It recovers non-zero Oracle
benefit in a reproducible high-heterogeneity/low-capacity subset, while the
majority of placement-necessary failures expose a meaningful limitation of
single-boundary local search rather than a hidden numerical or accounting bug.

# Final Validation & Reality-Gap Closure

## 1. Research questions

The original three-part research frame is retained: placement-aware carbon
flow, carbon-aware placement/CBGP, and fast dynamic scheduling with selective
slow placement. Final validation asks how far those claims survive when checked
against the repository's actual simulator objects, stage-aware workload energy,
and one real historical carbon-intensity source.

## 2. Existing prototype

The repository is an aggregate serving-graph simulator. It loads GPU/model/
network/placement configurations, builds a strict layer-boundary graph, and
solves max-flow, carbon-aware flow, joint placement, or CBGP optimization. The
Challenge 3 scheduler recomputes interval flow quotas and the dispatcher
validates deterministic quota accounting.

## 3. Validation gaps

The original simulator contains no discrete-event clock, request arrival,
queue, request execution, service time, token emission, completion event, or
latency object. Therefore TTFT, TBT, end-to-end latency, queueing latency, and
SLO violations are **unsupported**, not estimated. The detailed audit is in
`helix_simulator_audit.md`.

## 4. Helix request-level integration

Status: **PARTIAL/BLOCKED by missing simulator primitives**. Existing topology,
placement, energy, CI, and aggregate flow objects remain reusable. A request
adapter was not allowed to fabricate arrival or latency semantics. The explicit
request-level output file reports TTFT, TBT, latency, and SLO as unsupported.

## 5. Stage-aware carbon model

`StageWorkload` separates prefill input tokens and decode output tokens.
`evaluate_stage_carbon` computes

`C_total = C_prefill + C_decode`

with the unchanged `3,600,000 J/kWh` conversion and the existing placement-aware
flow edges. `WorkloadWeightedEnergyProvider` exposes a workload-weighted view to
the existing flow and placement solvers. The loader supports explicit prefill /
decode profiles and maps a legacy scalar `joules_per_token` to both phases.

The stage profiles are explicitly parameterized simulator assumptions, not GPU
measurements. Nine representative rows were run: three GPU compositions ×
prefill-heavy, balanced, and decode-heavy workloads. Under the frozen profile,
stage-weighted routing selected the same aggregate paths as decode-only routing
(mean route-level change: 0%). The bounded joint placement comparator improved
stage carbon by 1.8413% on average relative to the fixed Helix stage route and
changed placement in 9/9 representative rows. This is a model/accounting
validation result, not profiling evidence.

## 6. Historical CI support

`HistoricalCITraceLoader` accepts the canonical columns
`timestamp,region,carbon_intensity_g_per_kwh`, supports ISO-8601 or UNIX
timestamps, and uses explicit piecewise-constant resampling only. The raw data
is preserved under `data/carbon/raw/`; the processed CSV and source metadata are
under `data/carbon/processed/` and `data/carbon/metadata/`.

The historical input is one day of actual 30-minute values from the public UK
National Grid Carbon Intensity API (2025-01-01). It is mapped to both synthetic
regions A and B, so this validates temporal trace ingestion but makes no
multi-region spatial claim.

## 7. Experiment methodology

- Legacy regression: unchanged formal grids and legacy decode semantics.
- Stage-aware: fixed Helix, stage-weighted routing, and bounded joint placement
  at one fixed CI/network setting across three GPU scenarios and three workload
  mixes.
- Historical CI: high-asymmetric topology, three loads, 48 source intervals,
  30-minute scheduler horizon, static Helix/static carbon routing/dynamic flow/
  slow-CBGP comparison.
- All comparisons keep the same topology, placement baseline, target throughput,
  and horizon within each experiment. Served fraction is reported.

## 8. Challenge 1 validation

Status: **VALIDATED COMPLETE within the aggregate simulator**. Placement affects
feasible flow; regional CI is resolved into an interval snapshot; energy and CI
share one carbon accounting path. Stage-aware prefill/decode accounting is now
available with explicit parameterized profiles.

## 9. Challenge 2 validation

Status: **VALIDATED COMPLETE within the aggregate simulator**. The final 930-point
legacy run matches all scientific carbon, placement, routing, and classification
columns of the formal Challenge 2 output. Runtime columns are allowed to vary.
The prior Routing Sufficient majority, Placement Necessity subset, CBGP local
search limitation, unguided ablation, and failure cases remain unchanged.

## 10. Challenge 3 validation

Status: **VALIDATED COMPLETE for the declared aggregate scheduling study**.
The final 135-point legacy run preserves mean reduction (15.1684%), maximum
reduction (67.3023%), improved count (135/135), demand satisfaction (100%),
capacity violations (0), slow-CBGP invocations (34), and accepted placement
changes (10). A bounded MILP incumbent changed the diagnostic
`always_replace_placement_changes` count by 6 in one rerun; all required carbon,
throughput, violation, flow, slow-CBGP, and accepted-placement metrics were
identical. This is recorded as solver nondeterminism under the time-limited
comparator, not silently overwritten.

## 11. Request-level performance results

No request-level performance experiment is claimed. The existing dispatcher
validates deterministic token quotas, but there is no arrival sequence, queue,
service time, or completion event. TTFT, TBT, latency, and SLO violations are
`UNSUPPORTED`.

## 12. Carbon results

The historical temporal check served 100% of aggregate demand at all three
loads. Dynamic carbon reduced static Helix carbon by 25.4056% (low), 4.3958%
(medium), and 0.8446% (high), for a mean reduction of 10.2153%. The real trace
was mapped to both synthetic regions, so the result tests trace ingestion and
temporal scheduling only; it does not test spatial carbon arbitrage.

## 13. Stage-aware results

Prefill-heavy, balanced, and decode-heavy workloads all ran successfully for
commodity, moderate-asymmetric, and high-asymmetric GPU compositions. The
configured prefill/decode energy ratios did not change the fixed-placement path
allocation in this representative grid. The bounded joint placement reference
did lower stage carbon, but its observed MILP gap reached 34.65% in the hardest
row; it is explicitly a bounded comparator, not an exact oracle.

## 14. Historical CI results

The raw API response contains 48 actual 30-minute GB values. Processing retained
the source interval and used no interpolation. Dynamic flow had zero path
reallocations and slow-CBGP had zero invocations because the one-region mapped
signal contains no spatial CI asymmetry. That null result is retained as the
correct limitation of this data setup.

## 15. Runtime

The final legacy Challenge 3 medians remain 14.80 ms scheduler, 93.95 ms
dispatcher, 0.33 ms slow-CBGP, and 6.57 s bounded joint comparator. The full
Phase 3.5 and Challenge 2 regressions completed successfully; runtime columns
are machine-dependent.

## 16. Failure cases

No aggregate demand or capacity failures occurred in the formal Challenge 3
grid. The important negative findings remain visible: 35/135 points did not
improve over static carbon routing, stage-weighted routing produced no change in
the selected aggregate paths under the declared profile, and historical mapped
CI produced no reallocations. The bounded comparator has non-zero optimality
gaps and is not presented as exact.

## 17. Limitations

The largest remaining research gap is the missing genuine Helix request-level
simulator. The next data requirement is a real multi-region historical CI set;
the current one-region source cannot support spatial historical conclusions.
Energy values remain parameterized because no hardware profiling data was
available in the repository. No migration cost, latency, queueing, or production
SLO claim is made.

## 18. Final conclusions

The aggregate research prototype is validated and backward-compatible. The
stage-aware accounting and historical trace importer close two measurement-
fidelity gaps without changing the frozen research framework or formal grids.
The request-level reality gap is honestly **PARTIAL/BLOCKED**, and the final
reports preserve that boundary rather than converting aggregate throughput into
latency or SLO evidence.

# Experiment Audit Report

**Date:** 2026-09-22  
**Project:** Helix_waterwise / carbon-helix-sim  
**Audit mode:** local static audit of evaluation code and result artifacts

The configured external reviewer MCP described by the experiment-audit skill is
not available in this runtime. This report is therefore an explicit local audit,
not a cross-model independent verdict.

## Overall Verdict: WARN

## A. Ground-truth provenance: PASS with scope qualification

The experiments are simulation-only. Challenge 1–3 reference configured graph,
throughput, energy, and CI inputs rather than a dataset ground truth. Synthetic
CI traces and parameterized energy profiles are labeled as simulator assumptions
in the YAML and reports. The historical check uses actual values from the UK
National Grid Carbon Intensity API, with source metadata and SHA-256 for the raw
file; it is one GB regional signal, not a multi-region ground truth dataset.

## B. Score normalization: PASS

Carbon reductions are computed against explicitly named static baselines at the
same target throughput and horizon. No metric is divided by the model's own
maximum output statistic. Demand satisfaction and served fraction are reported
alongside carbon.

## C. Result existence: PASS

The formal tables exist under `results/challenge3/` and
`results/final_validation/`. The independent Challenge 3 verifier checks 135
rows, trace-grid membership, demand satisfaction, zero violations, and the
configuration hash. Phase 3.5 and Challenge 2 regressions were regenerated and
compared to their formal result tables.

## D. Dead code / pipeline use: PASS

The stage-aware and historical experiment entry points were executed, their
CSV outputs were written, and the test suite exercises the stage provider,
historical importer, trace mapping, and backward-compatible energy loader.

## E. Scope assessment: WARN

The legacy grid has 930 Phase 3.5 points, 930 Challenge 2 points, and 135
Challenge 3 points. Final validation adds 9 stage-aware representative rows and
3 historical load rows. There are no request-arrival seeds because the original
repository has no request simulator. Claims must remain simulation/proxy claims
and must not be phrased as production latency or SLO evidence.

## F. Evaluation type

- Challenge 1/2/3 legacy: `simulation_only` with parameterized/synthetic inputs.
- Stage-aware validation: `simulation_only` with parameterized energy profiles.
- Historical CI validation: `simulation_only` using one real GB trace, mapped to
  both synthetic simulator regions; spatial generalization is unsupported.
- TTFT, TBT, latency, and SLO: unsupported rather than imputed.

## Claim impact

- Aggregate placement-aware carbon-flow claim: supported within the simulator.
- Dynamic scheduling carbon/demand claim: supported within the 135-point
  synthetic Challenge 3 grid and the limited historical GB check.
- Stage-aware accounting claim: supported as a parameterized implementation and
  representative experiment.
- Request-level latency/SLO improvement: unsupported.
- Multi-region historical generalization: unsupported.
- Exact Challenge 3 joint oracle claim: unsupported; its bounded MILP gap is
  reported explicitly.

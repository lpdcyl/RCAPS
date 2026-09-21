# Challenge 3 — Carbon-aware Helix request scheduling

Challenge 3 is complete on branch `challenge3-autonomous`. The experiment is a
configuration-driven, interval-level scheduler study over 135 points: five
piecewise-constant CI traces × three load profiles × three GPU compositions ×
three cross-region capacities. The formal configuration is frozen by
`9d86aa32c3139d04e289344aa1fdda21962d5d2ea32ce6166be26733e691756f`.

## What is implemented

`TraceCIProvider` resolves a local CSV trace with the declared piecewise-constant
boundary rule: the latest sample at or before the interval timestamp is used,
and the final value is held after the trace ends. `CarbonFlowScheduler` takes
one CI snapshot per scheduling interval and calls the existing carbon-aware flow
optimizer; it does not make per-request placement decisions. `DeterministicQuotaDispatcher`
turns the interval path quotas into deterministic token requests with an
explicit no-overrun invariant. `SlowCBGPController` checks structural
carbon-bottleneck evidence only at the configured placement cadence and applies
persistence and minimum-dwell rules before attempting a boundary update.

The baselines are static Helix routing, static carbon routing, dynamic carbon
flow, dynamic carbon flow plus deterministic dispatch, slow CBGP, and an
always-replace joint placement/routing comparator. All flows are checked for
capacity and demand satisfaction.

## Formal results

| Metric | Result |
|---|---:|
| Formal experiment points | 135 |
| Dynamic scheduling improved vs static Helix | 135/135 |
| Mean reduction vs static Helix | 15.1684% |
| Maximum reduction vs static Helix | 67.3023% |
| Mean reduction vs static carbon routing | 13.4518% |
| Points improved vs static carbon routing | 97/135 |
| Dynamic demand satisfaction | 1.0000 for every point |
| Capacity violations | 0 |
| Performance violations | 0 |
| Flow reallocations | 310 total |
| Slow CBGP invocations | 34 total |
| Accepted slow placement changes | 10 total |
| Always-replace placement changes | 511 total |

The largest mean trace-level reduction is for the step trace (28.6624%),
followed by periodic (21.6444%) and slow drift (14.3039%). The constant and
noisy-boundary traces are intentionally less reactive (5.5592% and 5.6723%).
The complete point table, summaries, failure table, and runtime table are in
`results/challenge3/`.

The measured median runtimes per formal point are 14.80 ms for scheduling,
93.95 ms for dispatch, 0.33 ms for slow CBGP checks, and 6.57 s for the joint
re-placement comparator.

## Important scope limitation

The current simulator has no request arrival process, queue, service-time
distribution, token emission timestamps, or latency instrumentation. Therefore
Challenge 3 reports throughput, carbon, path quotas, and capacity invariants;
it does **not** claim TTFT, TBT, p95 latency, SLO compliance, or real request
queueing behavior. Requests in the dispatcher test are one-token synthetic
units used to validate quota accounting.

The always-replace comparator is still the existing joint carbon
placement-and-routing MILP, but the frozen Challenge 3 configuration gives
each solve a deterministic 2-second limit and 1% requested relative gap so the
135-point study is tractable. The observed incumbent gap is recorded in the
point CSV (`oracle_mip_gap_mean`, `oracle_mip_gap_max`); its maximum is 66.67%
for a hard low-load case. Consequently this comparator is a bounded
joint-replacement reference, not an exact optimality certificate. Challenge 1,
Challenge 2, and Phase 3.5 retain their original exact solver defaults.

## Regression and integrity checks

- `pytest -q`: 75 passed, with no failures or warnings.
- Phase 3.5 re-run: 930 points; all scientific columns are exactly equal to
  `results/phase1b_phase35_regression/phase35_summary.csv`.
- Challenge 2 re-run: 930 points; all scientific columns and placement/routing
  classifications are exactly equal to the formal Challenge 2 result. Only
  wall-clock runtime columns differ, as expected from machine scheduling.
- No Challenge 2 configuration or formal result was modified.

## Reproduction

```text
D:\software\miniconda\envs\gllm\python.exe -m pytest -q
D:\software\miniconda\envs\gllm\python.exe -c "from experiments.exp_challenge3 import run_challenge3; run_challenge3(workers=8)"
D:\software\miniconda\envs\gllm\python.exe -m experiments.challenge3_figures.gen_fig1_dynamic_reduction
D:\software\miniconda\envs\gllm\python.exe -m experiments.challenge3_figures.gen_fig2_trace_response
D:\software\miniconda\envs\gllm\python.exe -m experiments.challenge3_figures.gen_fig3_carbon_comparison
D:\software\miniconda\envs\gllm\python.exe -m experiments.challenge3_figures.gen_fig4_runtime
```

Figures are emitted as vector PDFs with PNG previews under
`results/challenge3/`. No Stage-aware Carbon Model, new CBGP algorithm,
dynamic placement policy, migration model, hysteresis feature, CI trace
pipeline, or further Challenge was started.

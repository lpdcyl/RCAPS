# Phase 3.5 Results

## Scope and validation

This run evaluates the predeclared synthetic scenarios in
`configs/phase35_sensitivity.yaml`. It does not use dynamic carbon traces,
migration, hysteresis, or BACR. GPU-composition and energy cases are simulator
sensitivity assumptions, not measured production data-center configurations.

- Tests: 49 passed.
- Full experiment points: 930.
- Every point satisfies `joint_carbon <= routing_carbon`.
- Every point satisfies `F_target = rho * F_H` exactly at saved precision.
- Maximum Region-share normalization error: `1.11e-16`.
- Apparent Placement transitions: 309.
- Raw fixed-cost crossings: 45.
- Validated, non-degenerate Placement boundaries: 42.
- Degenerate/equivalent switches: 248.

## Symmetric control and rho sensitivity

The original symmetric control reproduces `F_H = 164 token/s`, `rho = 0.95`,
`F_target = 155.8 token/s`, and maximum Routing Gap `0.4244%`. It remains below
1% at every CI point.

| rho | F_target | max Gap | mean Gap | validated boundaries |
|---:|---:|---:|---:|---:|
| 0.90 | 147.60 | 0.1056% | 0.0034% | 2 |
| 0.95 | 155.80 | 0.4244% | 0.0279% | 3 |
| 0.98 | 160.72 | 0.0000% | 0.0000% | 0 |
| 1.00 | 164.00 | 0.0000% | 0.0000% | 0 |

The hypothesized monotonic increase with rho is not supported in the symmetric
control. At rho 0.98 and 1.00 the feasible throughput constraint removes the
observed Placement advantage.

## GPU-composition sensitivity at rho 0.95

| scenario | F_H | max Gap | CI points >1% | >3% | >5% | validated boundaries |
|---|---:|---:|---:|---:|---:|---:|
| symmetric | 164 | 0.4244% | 0.00% | 0.00% | 0.00% | 3 |
| moderate_asymmetric | 136 | 1.6785% | 6.45% | 0.00% | 0.00% | 0 |
| high_asymmetric | 148 | 8.9217% | 83.87% | 77.42% | 67.74% | 2 |
| commodity_region | 130 | 0.0000% | 0.00% | 0.00% | 0.00% | 0 |

GPU asymmetry alone is not sufficient: the high-asymmetry mix creates a broad
Placement-benefit region, while the commodity-region mix is fully absorbed by
Routing at the baseline network capacity.

## Network sensitivity

Stage B selected `commodity_region` as the low-gap asymmetric representative
and `high_asymmetric` as the high-gap representative. Cross-region flow is
nonzero in many cells, confirming that the network parameter enters the
optimized solution. A fraction above 1 is possible because one request can
cross the Region boundary more than once.

The global maximum Routing Gap is `18.3907%` at:

- scenario: `high_asymmetric`;
- rho: `0.95`;
- cross-region capacity: `20 token/s` (`2.56 Mbps`);
- `CI_A / CI_B = 4.0`;
- scenario-specific `F_H = 136 token/s`, `F_target = 129.2 token/s`;
- Routing cross-region fraction: `0.4180`;
- joint cross-region fraction: `0.1084`.

At this capacity, the Gap increases smoothly from `15.91%` at CI ratio 2.875
to `18.39%` at ratio 4.0, so the result is a stable region rather than a single
isolated grid point. The high-asymmetry network sweeps contain validated
fixed-cost crossings at multiple capacities. Network effects are non-monotonic:
some bandwidths expose a Placement advantage, while others allow Routing to
recover it.

## Energy sensitivity

All one-at-a-time 0.75x/1.25x changes keep the symmetric-control maximum Gap
below 1%. The largest is `0.6898%` for `L4_1.25x`. Thus the specified energy
heterogeneity alone does not create a Placement Necessity Region.

## Candidate Placement curves and boundaries

The symmetric rho-0.95 sweep yields two unique candidates after adding the
Helix placement. Both appear on the optimum envelope. The three observed
signature transitions at right-hand CI ratios 0.625, 1.25, and 1.5 are genuine
non-degenerate fixed-cost crossings. Across all staged experiments, however,
248 of 309 signature switches are equivalent within the configured `1e-4`
relative tolerance and are not counted as scientific boundaries.

## Go / No-Go

Classification: **Case A, with scope qualification**.

A stable Placement Necessity Region exists in the predeclared, non-post-hoc
high-asymmetry topology and persists across several network capacities, with
Gap well above 1%, 3%, and 5% and validated cost crossings. It is not universal:
the symmetric control, commodity-region baseline, and all specified energy-only
sensitivities remain Routing-sufficient at the 1% threshold. This supports a
Routing-first design with Placement reconfiguration enabled only when resource
asymmetry and network constraints place the system inside the measured
necessity region. Because all resource cases are synthetic, a production-system
claim still requires empirical hardware/topology calibration before proceeding
to dynamic reconfiguration.

# Challenge 1 Final Report — Placement-aware Carbon Flow Modeling

Status: **COMPLETE**

## 1. Mathematical semantics

For placement `pi`, feasible serving flow `f`, workload/energy state `w`, and a
carbon-intensity snapshot `t`, the simulator evaluates

`C(pi, f, w, t) = sum_g f_g * e_g(pi, w) / 3,600,000 * CI_region(g)(t)`.

The fixed-placement routing optimum is

`C_R(pi) = min_f C(pi, f, w, t)`

subject to graph capacity, conservation, and the requested throughput. The
joint placement oracle is

`C_J = min_(pi,f) C(pi, f, w, t)`

subject to the same flow semantics plus placement and memory constraints.

## 2. Energy unit

Configured operational compute energy is measured in joules per processed
token (`J/token`). It is parameterized by GPU type, inference phase, batch
size, and placed layer count. It is a synthetic simulator parameter, not a TDP
conversion or a hardware measurement.

## 3. Carbon-intensity unit

Regional carbon intensity is measured in grams of CO2 equivalent per kilowatt
hour (`gCO2e/kWh`). `CarbonIntensityProvider` and legacy static mappings are
resolved into one invocation-level regional snapshot.

## 4. Carbon unit

Each placed GPU receives an operational compute cost in `gCO2e/token` using
`energy_j_per_token / 3,600,000 * CI_g_per_kWh`.

## 5. Flow-objective unit

GPU flow is measured in `token/s`; therefore the optimizer objective is
`gCO2e/s`. Reported `gCO2e/1000 tokens` is derived from the same objective and
achieved throughput.

## 6. Placement dependence

Placement determines each GPU's layer interval, compute throughput and energy
per token, and the strict-boundary logical network edges in the Serving Graph.
Consequently it changes both per-GPU carbon coefficients and the feasible flow
polytope:

`Placement -> Serving Graph -> Flow -> Carbon Cost`.

Network edges retain zero operational-carbon coefficient; they constrain only
bandwidth/capacity and connectivity/latency structure.

## 7. Backward compatibility

Existing `Mapping[str, float]` CI inputs remain valid with unchanged parameter
order and result fields. They are adapted internally through
`ConstantCIProvider`. Provider-backed calls resolve each unique region once,
and both routing and placement optimization consume the frozen snapshot.

## 8. Phase 3.5 numerical regression

The Phase 1B regression reproduced all 930 historical points. Maximum absolute
errors for `F_H`, `F_target`, `routing_carbon`, `joint_carbon`, and
`routing_gap` were all `0.0`. The 1%, 3%, and 5% classifications were exactly
identical. It also reproduced 42 valid non-degenerate crossings, a symmetric
maximum gap of 0.424355%, and a global maximum gap of 18.390738%.

## 9. Known limitations

- All workloads, energy profiles, carbon intensities, and topologies are
  parameterized synthetic simulator inputs.
- There is no dynamic CI trace, real carbon API, DCGM measurement, or network
  operational-energy model.
- The model is static within one optimization invocation.
- There is no request scheduler, migration, hysteresis, or dynamic dispatch.

## 10. Reuse by Challenge 2

Challenge 2 keeps the cost model and routing LP unchanged. For every local
placement candidate it rebuilds the strict-boundary Serving Graph, reuses the
same energy provider and frozen CI snapshot, and evaluates the candidate with
the same fixed-placement carbon-flow solver. The existing joint placement MILP
remains the global oracle. Thus routing baseline, CBGP, and Oracle differ only
in placement search, not in carbon accounting.

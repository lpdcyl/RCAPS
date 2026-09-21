# Carbon Helix Simulator

Requires Python 3.11 or newer.

Phase 1 implements only:

```text
Fixed Layer Placement -> Logical Serving Graph -> Max-Flow / Min-Cut
```

The graph uses strict layer-boundary connections (`end_i == start_j`) and
explicit directed physical network links. Partial inference is intentionally
disabled.

The default `AnalyticalThroughputProvider` uses a **simulator analytical
approximation**:

```text
effective compute units per second / placed-layer compute work per token
```

This is not the Helix profiling formula. `ProfiledThroughputProvider` instead
looks up throughput by GPU type and layer count, matching the abstraction used
by Helix, and raises `MissingThroughputProfileError` when a profile is absent.

## Run

```powershell
python -m pytest -q
python -m examples.phase1_demo
```

All numerical experiment parameters are read from YAML files under `configs/`.

## Phase 2

Phase 2 keeps the layer placement and logical graph fixed, then minimizes the
operational GPU-compute carbon proxy while maintaining a configured fraction
of Helix max-flow throughput:

```powershell
python -m experiments.exp_ci_sweep
```

The energy parameters in `configs/energy_profiles.yaml` are explicitly marked
as simulator assumptions. They are not derived from TDP and are not claims of
measured production energy. The experiment saves a summary CSV, a long-form
path-flow CSV, and the `CI_A / CI_B -> Flow Share` figure under `results/`.

## Phase 3

Phase 3 first solves a carbon-independent, throughput-optimal placement with
`scipy.optimize.milp`. It then compares carbon-aware routing on that fixed
placement against joint placement and routing at exactly the same throughput.
The default Phase 3 experiment uses the configured discrete throughput profiles;
all energy values remain explicit simulator assumptions.

```powershell
python -m experiments.exp_helix_carbon_routing
python -m experiments.exp_routing_placement_sweep
python -m experiments.exp_phase_diagram
```

The static experiments report routing and placement breakpoints, the routing
gap, and a `CI ratio x cross-region bandwidth` strategy diagram. Partial
inference, dynamic carbon traces, migration, hysteresis, and reconfiguration
policies are intentionally outside this phase.

## Phase 3.5

Phase 3.5 tests when fixed-Helix carbon-aware Routing is sufficient and when
joint Placement provides a material additional benefit. The GPU-composition
and energy cases in `configs/phase35_sensitivity.yaml` are predeclared synthetic
sensitivity scenarios, not measured production configurations.

```powershell
python -m experiments.exp_placement_cost_curves
python -m experiments.exp_rho_sensitivity
python -m experiments.exp_phase35
```

An apparent Placement signature change is no longer treated as a scientific
boundary by itself. Both adjacent placements are held fixed and re-routed at
the left endpoint, midpoint, and right endpoint. A validated boundary requires
a signed cost crossing and must not be an equivalent switch within the
configured relative degeneracy tolerance.

The full suite runs in stages: symmetric rho sensitivity; GPU-composition
sensitivity at rho 0.95; CI-by-network sensitivity for one low-gap and one
high-gap asymmetric scenario; and one-at-a-time energy multipliers. It writes
the pointwise `results/phase35_summary.csv`, validated-boundary diagnostics,
aggregate sensitivity tables, and four continuous Routing Gap/cost-curve
figures. Dynamic carbon, migration, hysteresis, and BACR remain out of scope.

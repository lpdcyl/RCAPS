# Phase 1A — Placement-aware Carbon Flow Model Design

## 0. Scope

This phase is a read-only design audit. No business code, configuration,
experiment, test, or historical Phase 3/3.5 result was changed. CBGP, scheduler,
CI traces, migration, hysteresis, and BACR were not started.

Audited modules and direct dependants:

- `src/carbon/model.py`, `src/carbon/config.py`
- `src/graph/topology.py`, `src/graph/serving_graph.py`
- `src/optimizer/maxflow.py`, `src/optimizer/carbon_flow.py`,
  `src/optimizer/placement_milp.py`
- `src/simulator/simulator.py`, `src/utils/config.py`
- Phase 2, Phase 3, and Phase 3.5 shared/experiment modules
- Carbon, flow, placement, experiment, and Phase 3.5 tests
- Energy, GPU, model, Phase 2, Phase 3, and Phase 3.5 YAML configuration

## 1. Current carbon implementation call chain

The fixed-placement path is:

```text
energy_profiles.yaml
  -> load_energy_provider()
  -> ConfiguredLinearEnergyProvider

phase3_experiment.yaml + sweep value
  -> carbon_intensities()
  -> Mapping[region, CI]

LayerPlacement + Topology + ModelProfile
  -> build_serving_graph()
  -> logical compute/network/coordinator edges and capacities

Placement + EnergyProvider + Mapping[region, CI]
  -> CarbonCostModel.build()
  -> GPUCarbonCost for every placed GPU

ServingGraph + CarbonCostModel + F_target
  -> solve_carbon_aware_flow()
  -> minimum-carbon feasible edge flow
  -> FlowCarbonMetrics
```

The joint Placement+Routing path is:

```text
Topology + ModelProfile + ThroughputProvider
  -> _build_base_model()
  -> placement choices, enabled physical edges, capacities, and flow variables

EnergyProvider + Mapping[region, CI] + candidate layer counts
  -> per-(GPU, layer-count) carbon coefficients
  -> solve_carbon_aware_placement()
  -> selected placement and physical flow

Selected placement
  -> build_serving_graph()
  -> CarbonCostModel.build()
  -> solve_carbon_aware_flow()
  -> independent fixed-placement validation of the MILP carbon result
```

Phase 3.5 calls both paths for every CI point. It also rebuilds fixed-placement
costs for the left, midpoint, and right CI values when validating apparent
placement boundaries.

## 2. Current energy semantics

### Definition and loading

Energy profiles are declared in `configs/energy_profiles.yaml` and loaded by
`src.carbon.config.load_energy_provider()`. The loader requires:

- provider name `configured_linear`;
- metadata explicitly stating that TDP is not used as energy/token;
- a hierarchy of GPU type -> phase -> batch size;
- `joules_per_token_per_layer` as the configured value.

The resulting in-memory type is:

```text
Mapping[gpu_type, Mapping[phase, Mapping[batch_size, J/token/layer]]]
```

### Calculation

`ConfiguredLinearEnergyProvider` computes:

```text
E_i = joules_per_token_per_layer[gpu_type, phase, batch]
      * placed_layer_count
```

The returned unit is joules per processed token for the entire interval placed
on that GPU. `MultipliedEnergyProvider` applies the Phase 3.5 synthetic
per-GPU-type multiplier without changing this unit.

### Supported workload dimensions today

- Phase: the API accepts a string and the YAML schema is phase-indexed. Only
  `decode` is configured, so `prefill` is structurally possible but not
  operationally supported by current data.
- Layer count: supported and linear. The fixed model receives start/end layers;
  the joint MILP receives a layer count. Layer position does not affect energy.
- Batch size: supported as an exact profile lookup. Only batch size 1 is
  configured.
- Token count: not an explicit energy-model input. Energy is per token; flow in
  token/s converts it to an energy/carbon rate.
- Input/output token distinction: not represented.

Phase 1B should retain these semantics. A request-workload object is premature
until stage-specific data beyond `(phase, batch_size)` exists.

## 3. Current Carbon Intensity semantics

CI enters the core as `Mapping[str, float]`, keyed by the exact `GPUNode.region`
identifier. Current topology regions are `A` and `B`.

- Phase 2 and Phase 3 configuration fix Region B at 200 gCO2/kWh and sweep
  Region A from YAML.
- `experiments.phase3_common.carbon_intensities()` constructs the mapping.
- `CarbonCostModel.build()` looks up each GPU's region, rejects missing regions,
  converts the value to float, and rejects negative values.
- `solve_carbon_aware_placement()` independently performs the same region
  presence/nonnegative checks and uses the mapping directly.
- There is no timestamp and no CI provider abstraction.

There is no hard-coded CI value in the core carbon/optimizer modules. Numeric
CI values are hard-coded only in YAML experiment definitions and test fixtures.
Phase 3.5 also has experiment-specific assumptions that region names are `A`
and `B` when reconstructing a CI ratio. That logic is outside the carbon model
and need not change in Phase 1B.

## 4. Current unit system

The existing conversion is physically consistent for the declared operational
GPU-compute proxy:

```text
JOULES_PER_KWH = 3,600,000 J/kWh

carbon_g_per_token
  = energy_joules_per_token
    * carbon_intensity_g_per_kwh
    / 3,600,000
```

The fixed-flow objective multiplies this coefficient by compute-edge flow:

```text
(g/token) * (token/s) = g/s
```

Reported derived metrics are:

- `carbon_g_per_second`: total operational GPU-compute carbon rate;
- `carbon_g_per_1000_tokens = carbon_g_per_second / throughput * 1000`.

The joint MILP uses the same formula, but currently duplicates it in
`placement_milp.py`. Both fixed-flow LP and joint MILP multiply the numerical
objective by `1e9` for solver conditioning, then report unscaled physical units.

Network edges currently have zero carbon coefficient. Network bandwidth enters
only as a capacity constraint. No J/GB, WAN energy, router power, or network
carbon constant should be introduced in Phase 1B.

## 5. Phase 3.5 dependency and compatibility surface

The following interfaces/fields are compatibility-sensitive:

### Inputs that existing experiments pass

- `load_energy_provider()` returns `(EnergyProvider, metadata)`.
- `Phase3Context.energy_provider` is an `EnergyProvider`.
- `CarbonCostModel.build(..., carbon_intensity_by_region, phase, batch_size)`
  receives the CI mapping positionally.
- `solve_carbon_aware_placement(..., energy_provider,
  carbon_intensity_by_region, throughput_target, phase, batch_size)` also
  receives the CI mapping positionally.
- `solve_carbon_aware_flow()` receives an already-resolved `CarbonCostModel`.

### Outputs used by experiments/tests

- `CarbonCostModel.gpu_costs`, `phase`, `batch_size`, `accounting_scope`;
- `GPUCarbonCost.region`, `carbon_intensity_g_per_kwh`,
  `energy_joules_per_token`, `carbon_g_per_token`;
- `CarbonCostModel.carbon_g_per_token(gpu_id)`;
- every existing `FlowCarbonMetrics` field;
- `CarbonFlowResult.edge_carbon_cost_g_per_token` and solver/check fields;
- `CarbonPlacementMILPResult.carbon_g_per_second`,
  `carbon_g_per_1000_tokens`, `milp_carbon_g_per_second`, placement/flow fields,
  and `validated_flow`.

Changing names, positional order, units, or output meanings would break Phase
2/3/3.5. Phase 1B must preserve them.

## 6. Recommended Placement-aware Carbon Flow formulation

For placement `pi`, let `G_pi=(V_pi,E_pi)` be the serving graph. Placement
determines each GPU interval, which compute and network edges exist, and every
edge capacity. Let `x_e` be the token/s flow on logical edge `e`.

For GPU `i` in region `r(i)`, define its placed-interval energy:

```text
E_i(pi, w) [J/token]
```

where the current minimal workload is `w=(phase, batch_size)`. At one resolved
time `t`, define:

```text
c_i(pi, w, t)
  = E_i(pi, w) * CI(r(i), t) / 3,600,000       [g/token]
```

Each GPU already has a split logical compute edge
`e_i=(gpu_i_in, gpu_i_out)`. Therefore the fixed-placement objective is:

```text
C(pi, f, w, t)
  = sum_i x_{e_i} * c_i(pi, w, t)              [g/s]
```

subject to the existing flow-conservation, capacity, and fixed-throughput
constraints. Compute cost belongs on the compute edge/its flow variable, not on
a NetworkX node: that preserves standard edge-flow optimization and counts each
token exactly when it consumes a GPU interval.

For joint placement, let `z_{i,k}` be the existing GPU flow associated with GPU
`i` selecting layer count `k`. The equivalent objective is:

```text
min sum_{i,k} z_{i,k}
    * E(i,k,w)
    * CI(r(i),t)
    / 3,600,000
```

This is already the implemented mathematics. Phase 1B should unify how CI and
unit conversion produce the coefficient rather than change the optimization.

## 7. Recommended minimal API

The smallest compatible design fits in the existing `src/carbon/model.py`.
Creating a parallel carbon framework is unnecessary.

### 7.1 Carbon Intensity provider

```python
@runtime_checkable
class CarbonIntensityProvider(Protocol):
    def get_ci(
        self,
        region: str,
        timestamp: float | None = None,
    ) -> float:
        """Return CI in gCO2/kWh for an exact topology region id."""


@dataclass(frozen=True, slots=True)
class ConstantCIProvider:
    carbon_intensity_g_per_kwh: Mapping[str, float]

    def get_ci(self, region: str, timestamp: float | None = None) -> float:
        ...  # timestamp intentionally ignored
```

The provider must reject missing regions, negative values, NaN, and infinity
with explicit errors. It must not alias `region_A` to `A`; topology region ids
remain the source of truth.

For backward compatibility:

```python
CarbonIntensityInput = Mapping[str, float] | CarbonIntensityProvider

def as_ci_provider(value: CarbonIntensityInput) -> CarbonIntensityProvider:
    if isinstance(value, Mapping):
        return ConstantCIProvider(value)
    return value
```

Existing mappings therefore become constant providers automatically.

### 7.2 Deterministic CI snapshot

An optimizer must not repeatedly query a time-varying source while constructing
one objective. Resolve all required regions once:

```python
def resolve_ci_snapshot(
    provider_or_mapping: CarbonIntensityInput,
    regions: Iterable[str],
    timestamp: float | None = None,
) -> Mapping[str, float]: ...
```

The same immutable snapshot must be used for joint-MILP coefficients and its
post-solve fixed-placement validation. This prevents coefficient drift inside
one optimization call and gives `C(pi,f,w,t)` a well-defined `t`.

### 7.3 Shared physical-unit conversion

```python
def operational_carbon_g(
    energy_joules: float,
    carbon_intensity_g_per_kwh: float,
) -> float:
    return (
        carbon_intensity_g_per_kwh
        * energy_joules
        / JOULES_PER_KWH
    )
```

The multiplication/division order should match the current implementation to
minimize floating-point differences.

### 7.4 Existing model and solver signatures

Keep the positional parameter name/order and broaden only its accepted type:

```python
CarbonCostModel.build(
    topology,
    model,
    placement,
    energy_provider,
    carbon_intensity_by_region: CarbonIntensityInput,
    *,
    phase,
    batch_size,
    timestamp: float | None = None,
)

solve_carbon_aware_placement(
    topology,
    model,
    throughput_provider,
    energy_provider,
    carbon_intensity_by_region: CarbonIntensityInput,
    throughput_target,
    *,
    phase,
    batch_size,
    timestamp: float | None = None,
    tolerance=...,
)
```

`CarbonCostModel` should remain an immutable cost snapshot. It should not retain
a live provider whose answers can change after construction.

### 7.5 Future TraceCIProvider design (not Phase 1B implementation)

`TraceCIProvider` will implement the same `get_ci(region, timestamp)` protocol.
CSV parsing, interpolation/step policy, time bounds, and missing-region policy
belong in the provider/configuration layer. Placement, flow optimizers, and the
future scheduler must never read trace files directly. No trace class or parser
is required in Phase 1B.

## 8. Energy API recommendation

### Phase 1B minimum

Keep `EnergyProvider`, `ConfiguredLinearEnergyProvider`, and
`MultipliedEnergyProvider` unchanged. They already provide the exact two access
patterns needed by fixed placement and the current homogeneous-layer MILP:

- interval-based `energy_joules_per_token(...)`;
- layer-count-based `energy_joules_per_token_for_layer_count(...)`.

Continue passing `phase` and `batch_size` explicitly. Do not add a workload
class merely to wrap these two fields.

### Later extensions

Only after measured/configured profiles exist, a workload value object may add:

- input token count;
- expected output token count;
- prefill/decode stage distinction;
- batch/sequence shape;
- possibly stage-specific throughput and energy metadata.

That extension must preserve a simple per-token/per-stage coefficient usable by
both LP and MILP. It is outside Phase 1B.

## 9. Recommended Phase 1B file changes

### File: `src/carbon/model.py`

- Current responsibility: energy-provider protocols, configured energy model,
  GPU carbon cost snapshots, and J-to-kWh conversion constant.
- Modify: **yes**.
- Proposed changes: add `CarbonIntensityProvider`, `ConstantCIProvider`, the
  mapping adapter/snapshot resolver, and one shared operational-carbon unit
  conversion helper; let `CarbonCostModel.build()` accept either a mapping or
  provider plus optional timestamp.
- Why: this is the existing single source of carbon semantics and requires no
  parallel framework.
- Phase 3.5 impact: direct input boundary; high compatibility sensitivity.
- Compatibility: preserve argument order/name, mapping support, dataclass fields,
  formula order, units, and return values.

### File: `src/optimizer/placement_milp.py`

- Current responsibility: throughput placement and joint carbon
  Placement+Routing Oracle.
- Modify: **yes**.
- Proposed changes: accept the same mapping/provider input; resolve one CI
  snapshot per solve; use the shared conversion helper for MILP coefficients;
  pass the same snapshot to post-solve `CarbonCostModel.build()`.
- Why: it currently duplicates CI validation and unit conversion.
- Phase 3.5 impact: direct Oracle path; highest regression risk.
- Compatibility: preserve public positional signature, result dataclasses,
  objective scaling, tolerances, and validation logic.

### File: `tests/test_carbon_model.py`

- Current responsibility: energy scaling, missing profiles, unit conversion,
  and CI-energy interaction.
- Modify: **yes**.
- Proposed changes: provider validation, CI/energy linearity, exact unit test,
  region lookup, and legacy mapping/provider equivalence.
- Why: owns unit-level carbon semantics.
- Phase 3.5 impact: protective only.
- Compatibility: retain all existing tests unchanged and add cases.

### File: `tests/test_carbon_flow.py`

- Current responsibility: fixed-placement LP feasibility, improvement, CI flow
  response, and immutability.
- Modify: **yes**.
- Proposed changes: manually sum compute-edge flow times GPU `g/token` and
  compare with optimizer `g/s`; compare mapping and Constant provider results.
- Why: verifies Placement-aware flow cost end to end.
- Phase 3.5 impact: protects `C_R` semantics.
- Compatibility: additive tests only.

### File: `tests/test_carbon_placement.py`

- Current responsibility: joint Oracle dominance and placement response to CI.
- Modify: **yes**.
- Proposed changes: mapping/provider equality for joint MILP and preservation of
  fixed-flow/MILP carbon agreement.
- Why: ensures both optimizers share one coefficient semantics.
- Phase 3.5 impact: protects `C_J` and `C_J <= C_R`.
- Compatibility: additive tests only.

### File: `src/carbon/config.py`

- Current responsibility: YAML energy and experiment configuration loading.
- Modify: **no** in the minimum Phase 1B.
- Proposed changes: none; existing sweep loaders should continue returning
  mappings so they exercise the compatibility adapter.
- Why: no new configuration schema is required for Constant CI.
- Phase 3.5 impact: avoiding changes minimizes risk.
- Compatibility: unchanged.

### File: `src/optimizer/carbon_flow.py`

- Current responsibility: consume a resolved CarbonCostModel and optimize edge
  flow.
- Modify: **no** in the minimum Phase 1B.
- Proposed changes: none; it should remain independent of providers and time.
- Why: provider resolution belongs before LP construction.
- Phase 3.5 impact: no API change.
- Compatibility: unchanged.

### Files: Phase 2/3/3.5 experiment modules and YAML

- Current responsibility: build static region-CI mappings and run sweeps.
- Modify: **no** in Phase 1B.
- Proposed changes: none.
- Why: unchanged callers are the strongest backward-compatibility test.
- Phase 3.5 impact: outputs should remain numerically identical.
- Compatibility: legacy mappings are automatically wrapped.

No new production file is required for Phase 1B. In particular,
`src/carbon/trace.py` should not be created until trace behavior is authorized.

## 10. Backward compatibility plan

1. Treat every existing `Mapping[str,float]` as a ConstantCIProvider.
2. Preserve region ids exactly (`A`, `B` in current experiments).
3. Preserve current multiplication/division order and `JOULES_PER_KWH` value.
4. Preserve `CarbonCostModel`, `GPUCarbonCost`, flow result, and placement result
   field names and meanings.
5. Preserve the compute-edge-only objective and zero network carbon.
6. Preserve objective scaling, solver tolerances, and post-solve validation.
7. Resolve a provider once per optimizer call and reuse the snapshot.
8. Leave all current experiment code and YAML unchanged.
9. Require mapping and Constant provider results to differ by at most `1e-9`;
   with the same arithmetic order the expected difference is zero.
10. Run the full existing 49-test suite in `gllm`, then run Phase 3.5 into a
    separate compatibility output directory and compare numerical columns to
    historical CSVs without overwriting them.

## 11. Phase 1B test design

All tests are additive; existing assertions remain.

### A. CI linearity

At fixed energy, placement, and workload, doubling every relevant CI doubles
`carbon_g_per_token` and fixed-flow `carbon_g_per_second`.

### B. Energy linearity

At fixed CI, applying a 2x energy multiplier doubles the same carbon values.

### C. Unit conversion

`operational_carbon_g(3_600_000 J, 1 gCO2/kWh) == 1 gCO2`.

### D. Region lookup

Identical GPU/workload energy in two regions with different CI produces the
corresponding carbon ratio; missing, negative, NaN, or infinite CI fails
explicitly.

### E. Constant-CI backward compatibility

For identical inputs:

```text
{"A": x, "B": y}
```

and:

```text
ConstantCIProvider({"A": x, "B": y})
```

must produce matching GPU costs, Routing flow, objective, and joint placement
objective within `1e-9`.

### F. Flow-cost consistency

For one placement and solved flow, manually compute:

```text
sum(compute_edge_flow[token/s] * gpu_cost[g/token])
```

and require equality with `FlowCarbonMetrics.carbon_g_per_second` within a tight
floating tolerance.

### G. Joint-model consistency

Require the joint MILP objective, reconstructed CarbonCostModel, and validated
fixed-placement LP carbon to remain within the existing validation tolerance.

### H. Regression

- Existing suite: 49 tests must continue to pass.
- Phase 3.5 static-CI summary: routing/joint carbon, Gap, placements, and boundary
  classification must reproduce within `1e-9` in a non-historical output path.
- `C_J <= C_R` must remain true at every point.

## 12. Minimal Phase 1B implementation sequence

1. Add the provider Protocol and ConstantCIProvider to `carbon/model.py`.
2. Add strict CI validation, legacy mapping coercion, and snapshot resolution.
3. Extract the existing J × CI / 3.6e6 operation into one pure helper without
   changing arithmetic order.
4. Adapt `CarbonCostModel.build()` while preserving its existing positional API.
5. Adapt joint Placement MILP to resolve and reuse one snapshot and shared
   conversion.
6. Add tests A–G; do not change existing assertions.
7. Run the full 49-test baseline in `gllm`.
8. Run a non-overwriting Phase 3.5 compatibility regression and compare against
   historical results.
9. Stop and report before any trace, CBGP, or scheduler work.

## 13. Risks and entry decision

### Risks

- **Dual input ambiguity:** accepting mapping or provider is necessary for
  compatibility. Keep coercion in one function so it does not spread.
- **Dynamic-value drift:** querying a future trace multiple times during one
  solve could make MILP coefficients and validation disagree. Snapshot once.
- **MILP semantic duplication:** fixed placement uses interval energy while the
  MILP uses layer-count energy. They agree today because the MILP requires
  homogeneous layers and the energy model is linear; retain post-solve checking.
- **Floating reproducibility:** changing arithmetic order can perturb objectives
  and tie-breaking. Preserve the existing order and compare with `1e-9`.
- **Region-name coupling:** Phase 3.5 ratio code assumes `A`/`B`; the provider
  must not silently rename regions.
- **Stage overclaim:** only decode/batch-1 data exists. API structure is not
  evidence of validated prefill behavior.
- **Rate versus total carbon:** current optimization reports g/s and g/1000
  tokens, not total request carbon. Future scheduling must integrate over work
  or multiply by processed tokens explicitly.
- **Network carbon:** remains zero by design because no credible energy profile
  exists. Network remains a capacity constraint.

### Decision

**Phase 1A is complete and the design is ready for Phase 1B.**

The recommended change is small, preserves the existing optimization model,
and has an explicit compatibility path for every current caller. Phase 1B must
not begin until explicitly confirmed.

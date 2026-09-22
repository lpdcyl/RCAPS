# Request-level integration phase implementation report

## Scope completed

This phase stayed within the strict request-level boundary:

- audited the original Helix simulator without changing its algorithms;
- separated TTFT, TBT, and E2E from the original Helix prompt/decode metrics;
- ran the existing LLaMA-30B single-cluster Helix Online artifact;
- added an independent carbon↔Helix mapping interface;
- added focused tests and corrected the old audit conclusion.

No Challenge 4, scheduler family, RL, migration, hysteresis, SLO threshold,
frozen-result edit, original simulator rewrite, or direct use of
`DeterministicQuotaDispatcher` was introduced.

## Files added

- `src/integration/helix_request_metrics.py`: pure request-level metric
  extraction and deterministic percentile helpers.
- `src/integration/helix_adapter.py`: explicit layer, node, topology, and
  pipeline mapping helpers; it refuses missing carbon metadata.
- `src/integration/__init__.py`: small public integration surface.
- `experiments/exp_request_level_baseline.py`: fixed existing artifact runner.
- `tests/test_request_level_integration.py`: seven tests covering metrics,
  unavailable single-token TBT, unfinished queries, timestamp validation,
  placement/node/route/topology mapping, and deterministic feeder traces.
- `results/request_level_integration/baseline_requests.csv` and
  `baseline_summary.csv`: generated baseline outputs.
- `request_level_simulator_audit.md` and
  `final_validation_audit_amendment.md`: source audit and historical correction.

## Baseline lifecycle

The baseline uses `artifact_evaluation/single_cluster/step3_simulation.py` as
the reference configuration and preserves its vanilla setup: LLaMA-30B,
A100x4, existing ILP placement, `GlobalFlowScheduler` in Online mode,
`KVParameters(0.9, 0.6)`, `OnlineRequestFeeder` over Azure Conversation, and
seed 0. The new entry point only exposes a shorter configurable duration so a
small reproducible run can be made without changing the original function.

Command used for the committed CSVs:

```text
D:\software\miniconda\envs\gllm\python.exe experiments/exp_request_level_baseline.py --duration 60 --output-dir results/request_level_integration
```

The run generated 39 trace queries, completed all 39, and recorded 8,881
finished request iterations. Model loading completed at simulator time 16 s.
The run is profile/analytical simulation output: layer compute values come
from the existing machine profiles; network and event timing use the original
analytical latency/bandwidth model.

## Baseline summary

| metric | value |
| --- | ---: |
| completed queries | 39 |
| TTFT mean / p50 / p95 / p99 (s) | 0.268831 / 0.167050 / 0.484592 / 0.524732 |
| TBT mean / p50 / p95 / p99 (s) | 0.0903144 / 0.0810359 / 0.131447 / 0.384112 |
| E2E mean / p50 / p95 / p99 (s) | 20.7376 / 14.8655 / 40.3330 / 43.1842 |
| Helix prompt latency mean (s) | 0.268831 |
| Helix decode-iteration latency mean (s) | 0.0911445 |

TTFT is the documented initialization-sink first-token-ready proxy. TBT is
computed from consecutive decode completion timestamps and excludes the first
decode token. The CSV leaves TBT unavailable for single-token outputs rather
than writing zero.

## Verified mapping and remaining mismatch

The baseline's first query route is the explicit Helix path
`source -> node 2 -> node 3 -> node 4 -> node 5 -> sink`, with link UIDs
`10000, 10002, 10003, 10004, 10001`. The adapter maps the four loaded
15-layer intervals to stable carbon IDs and preserves route stage IDs.

The unresolved semantic mismatch is carbon metadata: the Helix artifact does
not specify regions or the carbon model's effective compute units. The
topology adapter therefore requires those maps from a later, explicitly scoped
integration phase and never invents them. No carbon dispatch result is
reported here.

## Verification

The focused integration tests pass (`7 passed`) and the full repository suite
passes (`88 passed`) with the documented interpreter. This phase adds no
changes to existing simulator or scheduler tests.

## Stop point / next stage suggestion

This phase is complete and intentionally stops here. A later phase may choose
an explicit contract for Helix regions, effective compute capacity, and a
carbon-aware request admission policy; that would require a new user-approved
scope and must not be inferred from this baseline.

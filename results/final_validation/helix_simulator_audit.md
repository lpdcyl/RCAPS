# Original Helix simulator audit

## Scope

The audit inspected `src/simulator/simulator.py`, the graph, topology,
throughput, carbon, optimizer, scheduler, and test modules, plus the existing
configuration files. This repository is a research prototype named
`carbon-helix-sim`; it is not a checkout of a separate production Helix
request simulator.

## Findings

1. **Discrete-event simulator:** No. `src/simulator/simulator.py` is a
   configuration loader and validation orchestrator. `run_validation_case`
   builds a logical serving graph and calls `solve_max_flow`; there is no event
   loop or simulation clock.
2. **Request arrival:** Unsupported. No request object, arrival timestamp,
   arrival process, or workload arrival trace exists.
3. **Queue:** Unsupported. There is no queue, admission buffer, worker queue,
   batching queue, or queueing discipline.
4. **Prefill/decode execution:** No request execution path exists. The carbon
   API already accepts a phase string, and the new final-validation model adds
   parameterized `prefill` and `decode` energy semantics, but the original
   simulator does not execute either stage.
5. **TTFT/TBT/end-to-end latency/completion:** None are recorded or computable
   from the existing simulator objects. The repository contains no latency
   event, token emission timestamp, completion timestamp, or SLO evaluator.
6. **Service time:** No measured or profiled per-request service-time model
   exists. `AnalyticalThroughputProvider` and
   `ProfiledThroughputProvider` expose aggregate token/s capacity only.
7. **Network latency:** Not calculated. Network links have bandwidth and are
   converted to token/s capacities in `src/utils/config.py`; propagation or
   serialization delay is absent.
8. **GPU compute latency:** Not calculated. GPU compute is represented by
   aggregate throughput profiles and layer compute work per token, not by event
   durations.
9. **Workload input:** Existing YAML files define model, topology, placement,
   energy, and CI parameters. Challenge 3 adds local CI trace CSV input, but no
   request-length or arrival trace format is present.
10. **Placement mapping:** `LayerPlacement` maps GPU ids to contiguous layer
    intervals and `build_serving_graph` maps those intervals to graph compute
    nodes. There are no runtime Helix worker processes to receive a placement.
11. **Max-flow relationship:** Max-flow and carbon-flow are aggregate planning
    solvers over the serving graph. They are not schedulers feeding a request
    executor.
12. **Direct reuse:** Topology, `LayerPlacement`, throughput providers, energy
    providers, CI snapshots, and aggregate flow quotas are reusable. A genuine
    request-level adapter cannot be completed without adding the missing
    arrival/queue/execution objects from an external Helix simulator.

## Validation consequence

Request-level integration is therefore **PARTIAL/BLOCKED** by missing core
simulator objects. This stage does not manufacture TTFT, TBT, latency, or SLO
values. The final validation reports throughput, demand satisfaction, quota,
capacity, carbon, stage accounting, and placement/flow diagnostics only.

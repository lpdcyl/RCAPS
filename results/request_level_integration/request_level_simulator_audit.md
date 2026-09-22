# Request-level Helix simulator audit

Date: 2026-09-22
Scope: the original Helix event simulator shipped under `simulator/`, plus the
existing LLaMA-30B single-cluster artifact. This audit is source inspection
and a baseline run only. It does not change the simulator, scheduler, frozen
Challenge 1/2/3 artifacts, or Phase 3/3.5 results.

## Finding

The repository does contain a request-level Helix simulator. The previous
conclusion that only an aggregate simulator was available was caused by an
incomplete audit boundary; it did not include the original `simulator/`
package. The original simulator has arrivals, per-query state, per-iteration
requests, event-driven queueing/transmission/execution, placement-aware paths,
and query completion timestamps. It is therefore suitable as the vanilla
request-level baseline for this phase.

The simulator is not a carbon-aware request scheduler. No claim is made here
that a carbon policy has been inserted into its event loop.

## Source-to-lifecycle trace

1. `simulator/trace_generator/simulator_query_feeder.py:17-67`
   (`OnlineRequestFeeder`) generates Azure Conversation arrivals using a fixed
   seed and calls `QueryManager.issue_query` before advancing the simulator to
   the next arrival. Its final call drains the event queue and asserts that
   all generated queries finished.
2. `simulator/event_simulator/query_manager.py:40-107` (`Query`) stores the
   query creation time, input/output lengths, and an ordered
   `inference_history`. `get_next_iteration` emits one initialization request
   followed by one-token increment requests. `submit_finished_request` records
   each request's source-to-sink times and the copied `PipelineStage` path.
3. `simulator/event_simulator/query_manager.py:154-238` (`QueryManager`) creates
   queries, submits sink-completed requests, issues the next iteration at the
   current sink time, and stores completed queries as
   `finished_queries[query_uid] = (current_time, query)`.
4. `simulator/event_simulator/cluster_simulator.py:508-772` handles a new
   request, asks the configured scheduler for a route/transmission, and moves
   the request through the event queue. `:774-873` records sink arrival and
   invokes the query manager; `:875-1028` starts and finishes compute batches.
5. `simulator/event_simulator/cluster_simulator.py:1035-1412` dispatches the
   event handlers and `simulate` processes events in timestamp order. The
   existing simulator's event semantics are unchanged.
6. `simulator/event_simulator/request.py:57-230` defines `PipelineStage`,
   request location/routing history, per-layer inference history, and the
   pipeline cursor. `NetworkLink.finish_transmission` at
   `simulator/event_simulator/network_link.py:237` appends routing history and
   deposits the request at its next node.

## Compute and network semantics

`simulator/event_simulator/compute_node.py:460-620` obtains batch inference
time/VRAM from the loaded `ModelLayer` profiles and appends per-layer inference
history when a batch completes. `simulator/event_simulator/model.py:72-184`
interpolates prompt/decode profile points; these are profile-derived simulator
inputs, not measurements made during this baseline run.

`simulator/event_simulator/network_link.py:99-258` computes transmission time
from configured latency plus token/activation bytes divided by planned
bandwidth. This is an analytical network model. Model-loading time is also
computed from model size and configured disk speed by the existing layout
loader. Consequently, baseline timings are simulator/profile outputs, not
hardware wall-clock measurements.

## Scheduler and placement

The baseline uses the existing `GlobalFlowScheduler`:

- `simulator/scheduler/global_maxflow/global_maxflow_scheduler.py:50-113`
  follows a precomputed pipeline and uses the original execution policy.
- `simulator/scheduler/global_maxflow/scheduler_core.py:224-338` constructs
  each initialization `PipelineStage` (link UID, target node UID, bandwidth,
  and layers); `:438-505` stores the route and makes increment requests follow
  that route.
- Existing placement loading is in
  `simulator/initial_layout/load_existing_layout.py:151-238`. The selected
  artifact is `artifact_evaluation/single_cluster/layout_llama30b/ilp/a100/`
  with four A100 nodes and contiguous 15-layer intervals (0-14, 15-29,
  30-44, 45-59).

No new scheduling family, dispatcher, migration, hysteresis, SLO threshold, or
carbon decision was added.

## Metric definitions used in this phase

The independent implementation is
`src/integration/helix_request_metrics.py`.

- **TTFT:** `initialization.end_time - query.creation_time`. Helix has no
  explicit streaming `first_token_ready` event. Initialization sink
  completion is the closest defensible boundary because
  `QueryManager.collect_finished_request` immediately issues the first decode
  request at that timestamp. It should be read as a first-token-ready proxy,
  not as proof that a token was streamed before sink completion.
- **TBT:** differences between consecutive decode request sink completion
  timestamps. The first decode completion is excluded. Per-query output is
  mean, p50, p95, and p99 using deterministic linear interpolation. A query
  with one generated token has no consecutive pair; all TBT fields are
  unavailable (`None` in Python and blank in CSV), never zero.
- **E2E:** the `finished_queries` completion timestamp minus query creation
  time. An unfinished query receives no fabricated E2E value.
- **Preserved Helix metrics:** `helix_prompt_latency` is the initialization
  request's sink time minus its source time; each
  `helix_decode_iteration_latency` is the corresponding increment request
  sink time minus source time. The adapter also reports their per-query mean.

The adapter rejects non-finite or non-monotonic timestamps. It accepts
unfinished query objects for diagnostics but marks them incomplete and leaves
E2E unavailable.

## Carbon boundary and verified mappings

`src/integration/helix_adapter.py` is deliberately one-way and explicit:

- `layer_placement_from_helix` reads contiguous
  `ComputeNode.in_vram_model_layers` intervals and maps stable Helix node UIDs
  to carbon GPU IDs (`helix-node-<uid>`).
- `route_from_helix_pipeline` preserves every Helix link UID, target node UID,
  and contiguous layer interval, including the final sink stage.
- `topology_from_helix` can construct `ClusterTopology`, but requires explicit
  region and effective-compute-capacity maps. The original Helix INI files do
  not contain those carbon semantics, so the adapter refuses to guess them.
  Helix link bytes/second are converted to the carbon topology's Mbps unit.

The adapter does not call `CarbonFlowScheduler`, alter a Helix scheduler, or
invoke `DeterministicQuotaDispatcher`.

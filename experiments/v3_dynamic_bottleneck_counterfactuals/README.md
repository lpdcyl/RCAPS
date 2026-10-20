# V3 Dynamic-Bottleneck Counterfactuals

This experiment separates three explanations for V3 tail behavior while preserving each deployment's model placement and request-size sequence.

| Question | Counterfactual | Primary evidence |
| --- | --- | --- |
| Is a C1 single-branch failure KV constrained? | `C1_single/k1`, baseline capacity versus 2x every node's `kv_cache_capacity`, at loads 600 and 1100 | completion/failure status and P95 latency when completed |
| Does communication contention explain the multi-cluster effect? | `C1_multi/k1` and `k3`, baseline versus 2x each deployed-link bandwidth; `k1` also receives a uniformly spaced version of the same trace | P95 latency, throughput, link-dispatch waiting and occupancy |
| How much is lost by committing Decode to the Prompt route with unknown output length? | Frozen V3 multi layout, standard M3 versus a length oracle | P95 latency and throughput gap |

The length oracle sees each live query's true remaining output tokens when it places a new prompt. It does not see future arrivals, move KV state, or reroute Decode. It is therefore a bounded diagnostic for the output-length part of path commitment, not an omniscient online baseline.

The formal protocol uses a fixed 600 s window and three seeds. This horizon was selected after a 1,800 s pilot exposed a simulator-internal event-list `SystemError` in both baseline and relaxed-resource windows, before an experimental assertion. The aborted pilot is retained separately and is excluded from results. `kv` also includes a lower, successful-load condition so latency can be compared even when the high-load baseline hits the simulator's explicit KV-capacity assertion. The runner writes `formal600_index.json`; failures are results for the KV feasibility test and are kept alongside completed windows.

## Claim–evidence matrix

| Planned conclusion | Required observation | Interpretation limit |
| --- | --- | --- |
| KV is the binding feasibility constraint in a condition | baseline fails at KV assertion and 2x capacity completes the paired trace | This isolates simulator KV capacity; it does not measure physical GPU memory pressure. |
| Network contention contributes to tail delay | 2x link rate and/or flattening improves the paired `k1` window, while `k3` changes the response | Link-dispatch wait includes scheduler-delay effects, so it is not called pure link queue time. |
| Decode path commitment has material headroom | length-oracle improvement over standard M3 on identical traces | The gap is only from known output lengths of live sessions; it excludes future-arrival and free-KV-migration oracles. |

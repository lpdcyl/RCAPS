# Challenge 3: Queue-aware DAG scheduling with decode-transfer coalescing

This directory independently implements request scheduling over the placements
from `experiments/critical_graph`. It does not call Helix's max-flow routing or
KV-expectation scheduler. The tested records use the historical policy name
`coalesced_corrected`; new runs use the equivalent `final` policy.

Read the implementation in this order: `routing_dag.py` (layered DAG search),
`scheduler_queue_cost.py` (`SingleTokenQueueCostScheduler`), `scheduler_final.py`
(decode transfer grouping and final correction), then `evaluate.py` (CLI).
Earlier candidates live in `experimental/` and are selected only by their
explicit historical policy names.

## Method

At prompt admission, form a layered compatibility DAG. State `(layer, GPU)`
means layers before `layer` have completed at `GPU`. An edge advances to a
reachable GPU that contains the next contiguous layer range. Its cost, in
seconds, contains profiled prompt service, observed GPU/link backlog,
transmission time, and a one-token decode service for each live KV session on
that GPU. The final policy follows the simulator's doubled execution time for
a decode batch of size one. Forward DAG dynamic programming finds the minimum
cost route without enumerating complete paths. The route is committed at
admission, and subsequent decode tokens reuse it to preserve KV placement.

At every transmission event, ready decode requests sharing their next link
are sent in one transmission object. Prompts remain individual. The scheduler
does not wait for future arrivals. For `k` decodes, the simulator charges one
`latency + sum(payload)/bandwidth` transmission instead of `k` propagation
delays. GPU execution gives decode requests priority within profiled batch and
memory limits. Routing reduces queued work on the chosen pipeline; grouping
reduces repeated propagation delay on that pipeline.

## Fixed-window comparison

Each Helix/candidate pair uses the same placement and cluster files, synthetic
request trace, seed 1, `PYTHONHASHSEED=0`, and Python/NumPy versions. The
simulation runs for 1980 seconds: 180 seconds of warmup and a fixed 1800-second
measurement window, without draining the final backlog. Offered load is 400
tokens/s for the single cluster and 160 tokens/s for multiple clusters. The
three target metrics are output-token throughput, P95 TTFT, and P95 per-query
mean TPOT. `compare.py` verifies trace and placement hashes before comparison.

From the repository root, use one Python environment for the paired runs:

```powershell
$env:PYTHONHASHSEED = '0'
$env:MPLBACKEND = 'Agg'
python -m experiments.queue_dag.evaluate --scenario multi --solution experiments/critical_graph/runs/multi_final/solution.ini --sim-cluster experiments/critical_graph/runs/multi_final/simulator_cluster.ini --offered 160 --duration 1980 --warmup 180 --seed 1 --policy coalesced_corrected --compact --output experiments/queue_dag/runs/multi_coalesced_corrected_hash0_seed1_1800.json
python -m experiments.critical_graph.fixed_window --scenario multi --method helix --solution experiments/critical_graph/runs/multi_final/solution.ini --sim-cluster experiments/critical_graph/runs/multi_final/simulator_cluster.ini --offered 160 --duration 1980 --warmup 180 --seed 1 --compact --output experiments/queue_dag/runs/multi_helix_hash0_seed1_1800.json
python -m experiments.queue_dag.compare --helix experiments/queue_dag/runs/multi_helix_hash0_seed1_1800.json --candidate experiments/queue_dag/runs/multi_coalesced_corrected_hash0_seed1_1800.json
```

For single-cluster runs, use `single`, `single_final`, and offered load `400`.
Optional `--checkpoint-file PATH --checkpoint-every 25` supports long Windows
runs; keep one checkpoint file per scenario and policy.

## Results, 1800-second measurement window

| Scenario | Policy | Output token/s | P95 TTFT (s) | P95 TPOT (s) |
| --- | --- | ---: | ---: | ---: |
| Single | Helix | 90.031 | 4.588 | 1.076 |
| Single | Queue DAG + decode coalescing | 92.642 | 3.825 | 0.658 |
| Multi | Helix | 35.945 | 6.179 | 0.801 |
| Multi | Queue DAG + decode coalescing | 36.223 | 5.965 | 0.704 |

The paired comparison reports are
`runs/single_coalesced_corrected_comparison_hash0_seed1_1800.json` and
`runs/multi_coalesced_corrected_comparison_hash0_seed1_1800.json`. Both report
`all_three_improved: true`. The number of TTFT/TPOT samples is 730 in each
single-cluster run and 283 in each multi-cluster run.

These are single-seed simulator outcomes, not physical-GPU measurements. The
transport gain depends on the simulator's assumption that ready requests
sharing a link pay propagation delay once in a grouped transmission. A real
transport implementation would require separate validation.

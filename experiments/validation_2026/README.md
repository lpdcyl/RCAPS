# 70B three-seed validation

Experiments A and B use seeds 0, 1, 2, a 1,800-second fixed window, and offered
loads of 700 token/s (single cluster) or 320 token/s (three clusters). All
compared RCAPS variants use the same online `QueueAwareDagScheduler` and the
same topology-derived initial placement.

## A: search guidance

`rcaps_coarse` uses the initial placement. `rcaps_full_search` evaluates all
legal local moves with the event-graph/resource-demand score. `rcaps` uses the
same score and moves but screens candidates by predicted critical resources.
Both searches accept up to 16 improving steps. This isolates the candidate
screening rule. Report candidate evaluations and planning time from each
placement's `placement.json` trace. The three-cluster full and guided searches
currently emit identical candidates, so no search-guidance benefit can be
claimed there.

## B: measured bottlenecks

The runner records per-GPU queue request-seconds and busy fraction, outbound
request waiting, link dispatch waiting, link service and occupancy, propagation
time, and crossings between physical regions. Link dispatch waiting includes
scheduler decisions and must not be called pure link contention. Compare
initial and final layouts within each topology. Because the topologies also
have different offered loads, differences across topologies are descriptive.
`verify_protocol.py` checks that adding passive profiling does not change
previously saved simulator outcomes or the request-trace hash.

## Event-graph and resource-analysis removal

`rcaps_static_no_graph` starts from the same topology placement and searches
the same full legal neighborhood for up to 16 improving steps. Its offline
score is the mean isolated-route prefill and decode time, using per-GPU compute
profiles and physical transfer/propagation costs. It has no multi-request
event graph, queue dependency, path-ensemble demand, bottleneck ranking, or
critical-resource candidate screen. The 0.40 and 0.35 latency weights are
renormalized after removing the original 0.25 bottleneck term. The online
scheduler remains RCAPS, including its queue-aware routing; this ablation
isolates the offline placement analysis rather than removing online queue
awareness. Compare it with Helix, topology-only, and full RCAPS by seed.
In the single-cluster topology the static search accepts no move and exports
the same normalized solution and simulator configuration as `rcaps_coarse`.
Seed 0 was re-run to confirm identical simulator outcomes; seeds 1 and 2 reuse
the profiled topology-only results by exact layout equivalence, with provenance
recorded in `summary.json`.

Generate layouts, run experiments, verify, and summarize from the repository root:

```text
python -m rcaps.placement.partition --scenario single --output-dir rcaps/variant_layouts/single_static_no_graph --search-mode static
python -m rcaps.placement.partition --scenario multi --output-dir rcaps/variant_layouts/multi_static_no_graph --search-mode static
python -m experiments.validation_2026.run_ab
python -m experiments.validation_2026.planning_costs
python -m experiments.validation_2026.verify_protocol
python -m experiments.validation_2026.summarize
python -m experiments.validation_2026.figures
```

`run_batch.py` can run independent simulator processes with bounded workers.
Results are paired by seed; three seeds support descriptive consistency, not
a claim of statistical significance.

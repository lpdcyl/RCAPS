# Queue-aware resource-prediction experiment (70B)

This is an **exploratory** placement experiment, not a replacement for the
published RCAPS layout. It uses the same 24 physical GPUs, topology-derived
initial layout, layer-capacity constraints, legal local moves, up to 16 greedy
steps, and unchanged `QueueAwareDagScheduler`. The original RCAPS full-neighborhood
search is the closest placement comparator; its final layout is identical to
the guided RCAPS layout in both topologies.

The new proxy in `rcaps/placement/queue_predictor.py` uses only candidate
placement, GPU profiles, physical links, configured offered load, and the
Azure Conversation input/output length distribution already used by the
simulator's trace generator. It constructs every layer-compatible edge,
estimates a soft route flow, and iterates that flow with an M/G/1 waiting
approximation using the method of successive averages. It scores each
candidate with the original event-graph TTFT/TPOT terms (weights 0.40/0.35)
and a maximum predicted GPU queue-pressure term (weight 0.25). It searches
the **full** original neighborhood so candidate screening is not a confound.
The queue approximation is a heuristic for dynamic batching and session
contention; its values are not calibrated latency predictions.

The proxy **never reads evaluation traces, measured GPU queues, route counts,
or result JSON** during layout generation. Those fields are used only by
`summarize.py` after the new layouts are fixed and simulated. The modeling
choices were developed after examining prior three-seed profiles, so this is
an exploratory test on the same workloads, not an independent held-out
confirmation. No additional random seeds are introduced.

To reproduce from the repository root:

```text
python -m experiments.queue_predictor_2026.generate --scenario single
python -m experiments.queue_predictor_2026.generate --scenario multi
python -m experiments.queue_predictor_2026.run_batch --workers 3
python -m experiments.queue_predictor_2026.summarize
```

The fixed 1800-second offered loads are 700 token/s for the single cluster and
320 token/s for three clusters, with seeds 0, 1, 2. `run.py` checks trace,
arrival count, window, warmup, and offered load against the existing RCAPS
result before writing each new JSON. `summarize.py` additionally checks
exported layout hashes and reports paired per-seed outcomes. Short 60-second
seed-0 compatibility checks were performed before the full runs; their
temporary files are excluded from the repository and all performance claims.

Do not infer online performance from a better GPU rank correlation alone.
The experiment is useful only if the new placement improves full-window
throughput or latency under the paired online runs without an unacceptable
tradeoff. Three seeds provide descriptive evidence, not statistical
significance.

See `RESULTS.md` for the completed, mixed/negative online result. The main
RCAPS placement was not changed.

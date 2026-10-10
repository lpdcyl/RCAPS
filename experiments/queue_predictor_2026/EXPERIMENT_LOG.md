# Queue-aware proxy experiment log

The design is exploratory: its queue approximation was built after inspecting
the existing 0/1/2 online resource profiles. The full-window results below
must not be described as independent held-out confirmation.

## Frozen before the 1800-second runs

- Physical topologies and loads: original single 700 and three-cluster 320
  offered token/s; 24 physical GPUs; LLaMA-2 70B.
- Evaluation: seeds 0, 1, 2; same per-seed request trace as existing RCAPS;
  unchanged online scheduler; 1800-second window and zero warmup.
- Predictor: Azure Conversation dataset mean input/output lengths; soft
  compatible-route flow with temperature 0.2 seconds; 96 successive-average
  iterations; M/G/1 waiting with denominator floor 0.05 and wait cap 30 s.
- Placement: same topology-derived initial state, same full legal neighborhood,
  same 16-step maximum, same 0.40/0.35 event-graph latency terms, and 0.25
  maximum predicted GPU queue-pressure term.
- Rank diagnostic on existing final RCAPS layout: predicted queue-pressure vs
  actual GPU queue rank Spearman ≈0.499 (single) and ≈0.788 (three clusters),
  averaged over seeds 0/1/2. Existing chosen demand proxy's corresponding
  correlations are ≈0.648 and ≈0.587. This motivated testing both topologies;
  it is **not** a claim of online improvement.
- Generated layouts: single cluster accepted 0 moves after 23 candidate
  evaluations (same intervals as topology-only layout); three clusters accepted
  5 moves after 142 candidate evaluations. One 60-second seed-0 compatibility
  run per topology completed; these pilots have no performance role.

The formal three-seed full-window simulation was started only after the above
predictor and layouts were fixed.

## Full-window outcomes

All six new 1800-second runs completed and passed paired trace, workload,
layout-hash, hardware, and physical-link checks. There were no failed cells.

| Topology | Seed 0 | Seed 1 | Seed 2 | Outcome vs original RCAPS |
| --- | --- | --- | --- | --- |
| Single | Complete | Complete | Complete | Throughput, TTFT, TPOT, queue and backlog all worse in every seed |
| Three clusters | Complete | Complete | Complete | Throughput and tails mixed by seed; mean values slightly worse |

The stronger three-cluster hotspot rank correlation did **not** translate
into online benefit. Keep the main RCAPS layout unchanged. Full numeric
results, paired differences, and limitations are in `RESULTS.md` and
`summary.json`.

# Structure ablation run log

All runs use LLaMa70B, `QueueAwareDagScheduler`, seeds 0/1/2, a 1,800-second
fixed window, zero warmup, the same 24-GPU physical topology per scenario,
and seed-paired request traces. Full numeric outcomes are in `summary.json`,
`summary_safe.json`, and `RESULTS.md`.

| Protocol | Scenario | Arm | Seed 0 | Seed 1 | Seed 2 |
| --- | --- | --- | --- | --- | --- |
| 700/320 token/s | Single | S1 all 24 | KV assertion | KV assertion | KV assertion |
| 700/320 token/s | Single | S1 lean 9 | Completed | Completed | Completed |
| 700/320 token/s | Single | S3 prefix 11 | Completed | Completed | Completed |
| 700/320 token/s | Single | S2 prefix 12 | Completed, prior RCAPS record | Completed, prior RCAPS record | Completed, prior RCAPS record |
| 700/320 token/s | Three | S1 all 24 | KV assertion | KV assertion | Completed, high backlog |
| 700/320 token/s | Three | S1 lean 9 | Completed | Completed | Completed |
| 700/320 token/s | Three | S3 prefix 10 | Completed | Completed | Completed |
| 700/320 token/s | Three | S3 prefix 11 | Completed | Completed | Completed |
| 700/320 token/s | Three | S2 prefix 12 | Completed, prior RCAPS record | Completed, prior RCAPS record | Completed, prior RCAPS record |
| 200/80 token/s | Single | S1 all 24 | Completed | Completed | Completed |
| 200/80 token/s | Single | S2 prefix 12 | Completed | Completed | Completed |
| 200/80 token/s | Three | S1 all 24 | Completed | Completed | Completed |
| 200/80 token/s | Three | S2 prefix 12 | Completed | Completed | Completed |

The five KV assertion runs have no 1,800-second metrics; their last logged
progress and exception are in `failures.json`. They are not assigned a zero
throughput. Single-cluster S3 prefix 10 was not run because the fixed suffix
capacities, 69 and 71 layers, cannot each cover the 70-layer remainder.

**Negative and mixed results retained:** the optimized 9-GPU single path has
lower p95 TTFT than S2 in the single-cluster high-load comparison; the
24-GPU single path has lower p95 TPOT than S2 in the single-cluster safe-load
comparison. Prefix 12 improves throughput by only 0.17%/0.21% over prefix 11
in the two topologies, while increasing shared-GPU busy and queue time. The
results support route use and a context-dependent structural tradeoff, not a
claim of universal dual-suffix superiority or statistical significance.

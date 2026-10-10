# Phase-corrected queue-demand experiment (70B)

This experiment changes only the **offline** GPU service-demand estimate used
by the queue-flow predictor. The earlier estimate multiplied all input and
output tokens by the slower of a prompt-token cost and a decode-token cost.
That counted expensive decode service for input tokens and gave some single
cluster GPUs predicted utilization above 3. The corrected estimate is one
profiled prompt pass plus the expected output length times profiled batched
decode service. The M/G/1 queue and soft route-flow approximations are otherwise
unchanged. The old convention remains available as `service_mode="legacy"`
to reproduce the prior experiment; this experiment requests `"phase"`.

The placement uses the same topology-derived initial layout, complete legal
neighborhood, 16-step cap, and event-graph / maximum GPU queue-pressure score
as the earlier queue experiment. It uses the same unchanged
`QueueAwareDagScheduler` for online evaluation. There are no 30B runs.

All six full-window runs use the same physical 24-GPU topologies, offered loads
(700 single, 320 three clusters token/s), 1800-second window, and seeds 0, 1,
2 as the original RCAPS runs. The runner checks trace hashes and protocol
fields; the summary also checks exported layout hashes and physical links.
These seeds were already viewed during predictor development, so the results
are exploratory and cannot establish independent generalization or statistical
significance.

Reproduce from repository root:

```text
python -m experiments.queue_predictor_2026.move_diagnostic
python -m experiments.queue_predictor_2026.phase_audit
python -m experiments.queue_predictor_phase_2026.generate --scenario single
python -m experiments.queue_predictor_phase_2026.generate --scenario multi
python -m experiments.queue_predictor_phase_2026.run_batch --workers 3
python -m experiments.queue_predictor_phase_2026.summarize
python -m experiments.queue_predictor_phase_2026.figures
```

The retrospective audits read measured profiles **only after** fixed layouts
are generated and are not imported by placement generation. GPU rank quality
and placement performance are reported separately in `RESULTS.md`.

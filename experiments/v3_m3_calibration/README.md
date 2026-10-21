# T0.5: M3 Decode coefficient audit

This is a development-seed diagnostic, not a formal 1800-second comparison.
It runs the frozen C1 single-cluster layout and V3 scheduler for 60 simulated
seconds at 350 offered token/s, seed 100, zero warmup, and no tail drain.
`PYTHONHASHSEED=0` and `MPLBACKEND=Agg` are set for reproducibility.

The passive probe wraps `start_execution` and `finish_execution` on compute
nodes. It observes only completed, single-request Decode batches whose start
and finish both lie in the window. For each event it compares the elapsed
FinishExecution duration with the scheduler's one-layer
`_layer_service(node, layer, Increment, 1)`. The report aggregates actual and
profiled durations by A100, L4, and T4. It also records the simulator's
`decode_typical_tokens` and `decode_max_tokens` for every active node.

The probe does not modify simulator times or scheduling. The `formal` phase is
an alias for the same seed-100 diagnostic to satisfy the experiment interface;
it does not create official seed-0/1/2 evidence.

From the repository root:

```powershell
python -m experiments.v3_m3_calibration.run --phase smoke
python -m experiments.v3_m3_calibration.run --phase report
```

Outputs: `runs/dev_seed100.json`, `index.json`, and `RESULTS_CN.md`. Failure
details are retained in `runs/dev_seed100.failure.json`.
An initial probe signature error during development is retained separately as
`runs/dev_seed100.attempt1.failure.json` and indexed; it is not a simulator or
M3 failure.

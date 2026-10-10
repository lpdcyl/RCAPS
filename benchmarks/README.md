# RCAPS benchmark protocol

Run from the repository root with the Python environment in `requirements.txt`.
The published comparisons use the Helix event simulator, two 24-GPU LLaMA-70B
topologies, 1800-second fixed windows, zero warmup, and offered loads of 700
tokens/s (single cluster) or 320 tokens/s (three clusters). A finished window is
not drained. A result includes the seed, generated request-trace hash, layout
and simulator-configuration hashes, software versions, arrival count, throughput,
TTFT/TPOT samples, completion fraction, and end-of-window backlog.

```powershell
python -m benchmarks.manifest
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps helix --seeds 0 1 2 --workers 12
python -m benchmarks.compare --baselines helix --seeds 0 1 2
python -m benchmarks.paired_stats --source benchmark --seeds 0 1 2
python -m benchmarks.audit
```

Each new run also records per-query first-token time, mean inter-token time,
arrival length, and completion status. `benchmarks.compare` verifies paired
query IDs and inputs before reporting P95 latency on the cohort observed in
both methods. This sensitivity analysis complements the original fixed-window
P95; it does not remove censoring of requests without an output sample.

The registered ablations keep the common runner and trace generator:

| Name | Single change |
| --- | --- |
| `rcaps_capacity` | Use VRAM-only initial partition, all 24 GPUs active; ignore RTT and bandwidth in placement |
| `rcaps_no_queue` | Ignore current GPU/link release times in routing cost |
| `rcaps_no_session` | Ignore active KV-session decode service in routing cost |
| `rcaps_no_coalesce` | Transfer ready decodes individually; preserve routing cost |
| `rcaps_coarse` | Use the initial shared-prefix/two-suffix layout before local refinement |
| `rcaps_full_search` | Evaluate every legal local move using the same event-graph objective as RCAPS |
| `rcaps_static_no_graph` | Search the same neighborhood with isolated-route latency, without event-graph or critical-resource analysis |
| `rcaps_alt_demand` | Use ensemble path demand on the three-cluster layout; this is not a distinct single-cluster layout |

For example:

```powershell
python -m benchmarks.run --methods rcaps rcaps_no_queue rcaps_no_session rcaps_no_coalesce rcaps_coarse --scenarios single multi --seeds 0 1 2 --workers 12
python -m benchmarks.run --methods rcaps_capacity --scenarios single multi --seeds 0 1 2 --workers 6
python -m benchmarks.run --methods rcaps_alt_demand --scenarios multi --seeds 0 1 2 --workers 3
python -m benchmarks.compare --baselines rcaps_no_coalesce --scenarios single multi --seeds 0 1 2
python -m benchmarks.compare --main-method rcaps_coarse --baselines rcaps_capacity --seeds 0 1 2
```

Predeclared claims, run counts, failure handling, and statistical analysis are
in [`paper/EXPERIMENT_EXTENSION_PLAN.md`](../paper/EXPERIMENT_EXTENSION_PLAN.md).

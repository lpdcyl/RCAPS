# V3 four-method paired comparison

This experiment compares the frozen RCAPS V3 system with **Helix ILP**, the
Helix artifact's **Swarm**, and **Separate Pipelines (SP)**. It covers C1 single
cluster and C1 three cluster topologies, each with the same 24-GPU pool
(4 A100, 8 L4, 12 T4).

The common loads are 350 offered input-plus-target-output tokens/s for the
single cluster and 160 for three clusters. They were fixed by the earlier
V2 four-method experiment from the Helix artifact's Swarm workload before
these V3 windows were run. Seeds 0/1/2 use paired request traces, 1800-second
fixed windows, no warmup, and no tail drain. P95 latency is measured on
requests observed in the window; completion and backlog are reported to
show truncation effects. These figures must not be mixed numerically with
the 700/320 V3 versus Helix main comparison.

The original 70B online artifact assigns method-specific offered rates:
single cluster Helix/Swarm/SP = 700/350/(240+120+10), and three clusters
= 320/160/(1+120+60) token/s. The common-load table therefore tests
same-load behavior at the Swarm rate; it does not measure Helix's peak
capacity. The separate V3 versus Helix comparison at 700/320 covers the
original Helix online operating points. "Online" and "offline" in the paper
are workload modes; this directory evaluates online serving only. The paper's
prompt/decode stage latencies are not the same metrics as this experiment's
request-level P95 TTFT/TPOT. See `RESULTS_CN.md` for the full provenance and
interpretation boundary.

Helix, Swarm, and SP use their original layouts and schedulers. SP runs three
homogeneous subclusters that partition the 24 GPUs and uses a deterministic
request-count allocation based on the original artifact's subcluster load
ratios; it never consults a request's target output length when assigning
that request. Their existing common-load windows are reused only after the
report script checks layout hashes, trace identity, individual request IDs,
and fixed-window protocol. V3 is newly run at the same loads. Source paths
and SHA-256 values are in `summary.json`.

From the repository root:

```powershell
python -m benchmarks.run --methods rcaps_v3 --scenarios single multi --seeds 100 --offered-single 350 --offered-multi 160 --duration 60 --warmup 0 --results-dir experiments/v3_four_method_comparison/smoke --workers 2
python -m benchmarks.run --methods rcaps_v3 --scenarios single multi --seeds 0 1 2 --offered-single 350 --offered-multi 160 --duration 1800 --warmup 0 --results-dir experiments/v3_four_method_comparison/runs --workers 3
python -m experiments.v3_four_method_comparison.report
```

`RESULTS_CN.md` contains the four-method tables and paired V3 comparisons.
`IEEE_TABLE.tex` is a compact two-topology, two-column paper table (requires
`booktabs`).
The report validates the SP physical topology partition and records the
unfinished request age distribution and same-request latency cohorts in
`summary.json`. Three seeds describe variation only; they do not establish
statistical significance.

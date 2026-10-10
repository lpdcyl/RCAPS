# 70B path-structure ablation

This experiment compares execution-path structures under the **same RCAPS
`QueueAwareDagScheduler`**, physical 24-GPU topology, request trace per seed,
window, and offered load within each comparison. It uses seeds 0, 1, and 2
only. No 30B runs are involved.

## Structures and capacity controls

| Arm | Structure | Physical pool | Active GPUs | Layer replicas | Model-layer capacity used |
| --- | --- | ---: | ---: | ---: | ---: |
| `s1_all24` | One complete serial path | 24 | 24 | 80 | 80/152 = 52.6% |
| `s1_lean` | One complete serial path, hardware-only fastest-capacity choice | 24 | 9 | 80 | 80/83 active capacity = 96.4% |
| `s2_prefix12` | Existing RCAPS shared prefix + two suffixes | 24 | 24 | 148 | 148/152 = 97.4% |
| `s3_prefix11` | Same branch assignment/order as S2, 11-layer prefix | 24 | 24 | 149 | 149/152 = 98.0% |
| `s3_prefix10` | Same branch assignment/order as S2, 10-layer prefix | 24 | 24 | 150 | 150/152 = 98.7% |

The 10-layer prefix is **infeasible in the single-cluster fixed branch
assignment**: the suffixes would each require 70 layers, but their capacities
are 69 and 71. In the three-cluster topology both branches have capacity 70,
so prefix lengths 10, 11, and 12 are feasible. The shared GPU remains the
original A100, whose maximum model capacity is 12 layers.

`s1_all24` controls the number of activated GPUs but requires each request to
traverse all 24 serial stages. `s1_lean` gives the single-path alternative a
short, hardware-efficient route, while explicitly reporting that only 9 GPUs
are activated. S1 assigns at least one layer to each selected GPU and places
remaining layers on the fastest devices based on offline model profiles. The
three-cluster routes keep physical regions contiguous. No online outcome is
used to construct these layouts.

S3 keeps S2's two device sets and their order. Shortening the prefix adds the
new suffix layers to the earliest available capacity in each branch. This
isolates sensitivity of **this skeleton** to prefix length; it is not a new
global placement optimization for each length.

## Loads and measurements

At the original offered loads (single cluster 700, three clusters 320
token/s), S2 reuses the prior 1800-second RCAPS runs; new arms use the same
trace, simulator, scheduler, and 0-second warmup. The 24-GPU S1 can hit a
simulator KV-capacity assertion at these loads. Failed runs are recorded in
`failures.json` and have no full-window performance value. A separate common
safe-load comparison runs only `s1_all24` and S2 at 200/80 offered token/s,
respectively, again paired by seed with the same 1800-second window.

The summaries verify trace hashes, metric protocol, layout hashes, 24 physical
GPU definitions, device hardware fields, and every exported link against the
physical topology. Reported mechanism measures include completed decode
throughput, p95 TTFT/TPOT, completion/backlog, cumulative GPU queue
request-seconds per arrival within the window, shared-GPU busy/queue,
distinct executed routes, route length, suffix use, stitched-route fraction,
and physical-region crossings. The queue figure is an observed window total
divided by arrivals, not a completed-query latency metric.

## Reproduce

From the repository root, first generate the deterministic structures:

```text
python -m experiments.structure_ablation_2026.generate --scenario single --arm s1_all24
python -m experiments.structure_ablation_2026.generate --scenario single --arm s1_lean
python -m experiments.structure_ablation_2026.generate --scenario single --arm s3_prefix11
python -m experiments.structure_ablation_2026.generate --scenario multi --arm s1_all24
python -m experiments.structure_ablation_2026.generate --scenario multi --arm s1_lean
python -m experiments.structure_ablation_2026.generate --scenario multi --arm s3_prefix10
python -m experiments.structure_ablation_2026.generate --scenario multi --arm s3_prefix11
```

Then run both paired protocols and build the reports:

```text
python -m experiments.structure_ablation_2026.run_batch --workers 6
python -m experiments.structure_ablation_2026.collect_failures
python -m experiments.structure_ablation_2026.summarize
python -m experiments.structure_ablation_2026.run_batch --arms s1_all24 s2_prefix12 --single-load 200 --multi-load 80 --output-root experiments/structure_ablation_2026/runs_safe_200_80 --workers 3
python -m experiments.structure_ablation_2026.summarize --safe-load
python -m experiments.structure_ablation_2026.figures
```

The high-load batch exits nonzero when the five recorded KV-capacity failures
occur. The finished cells and failure logs remain available, and the summary
marks incomplete arms by seed. The safe-load batch completes all selected
cells. Each generated layout has `solution.ini`, `simulator_cluster.ini`,
`placement.json`, and `structure.json` for inspection.

See `RESULTS.md` for the numeric interpretation. Three seeds provide paired
descriptive evidence, not a claim of statistical significance. S1 versus S2
changes model-layer replication and per-request serial hop count as well as
route redundancy; the experiment cannot assign all performance differences
uniquely to the latter.

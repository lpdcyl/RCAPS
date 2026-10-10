# Earlier graph pipeline (compatibility baseline)

This is an earlier implementation and is **not** the final placement or
scheduler. Current fixed-window simulation still imports its base model,
scheduler and evaluation adapter; final placement audits also read the 1800 s
Helix baseline JSON files under `runs/long/`. Start current work at
[`../README.md`](../README.md).

This folder is an independent implementation for the first two research challenges.
The proposed method does not call Helix's maximum-flow graph, MILP search, or
MaxFlow/IWRR scheduler. It uses the existing simulator only as an execution
environment and reads its per-layer machine profiles as input measurements.

## Challenge 1: explainable model

An inference request is represented as a layer-ordered event DAG. A compute
vertex covers one contiguous layer interval on one GPU. A directed edge moves
tokens or activations to the next vertex. For a candidate path, the model adds:

* `T_compute`: sum of profiled prefill times for the layers on a node;
* `T_transfer`: link latency plus transferred bytes divided by bandwidth;
* `T_queue`: observed request queue and live query occupancy, each multiplied
  by a documented coefficient.

The path cost estimates the critical path, while the largest stage demand
identifies a likely bottleneck. Routing applies dynamic programming to this DAG
when the first request of a query arrives. Later decode requests follow its
fixed path so their KV cache stays on the same devices. The model deliberately
does not claim to predict GPU energy or carbon emissions without GPU traces.

## Challenge 2: graph placement

`placement.py` constructs a shared prefix and two complete branches. It takes
per-device model capacity from the profile, assigns contiguous layer intervals,
and adds only graph edges that can advance the next uncomputed layer. A
latency-gap graph partition detects the three network regions. Each branch keeps
most of its nodes in one region and crosses from the shared A100 region once.
For the uniform single cluster, a small capacity subset-sum search balances the
two branches. The loader writes a fresh simulator topology from the complete
cluster file, instead of reusing the pruned edges of Helix's ILP result.

`scheduler.py` provides an independent evaluation scheduler: layer-DAG shortest
path for first requests and phase-aware feasible batching. Its presence means
the end-to-end comparison includes both placement and routing differences.
To isolate the placement effect, also run `--method graph` on the Helix solution
as a crossover control.

## Reproduce

From the repository root:

```powershell
python -m experiments.graph_pipeline.placement --variant single --output-dir experiments/graph_pipeline/runs/single_candidate
python -m experiments.graph_pipeline.placement --variant multi --output-dir experiments/graph_pipeline/runs/multi_candidate
python -m experiments.graph_pipeline.evaluate --scenario single --method graph --solution experiments/graph_pipeline/runs/single_candidate/solution.ini --sim-cluster experiments/graph_pipeline/runs/single_candidate/simulator_cluster.ini --offered 400 --duration 600 --warmup 180 --seed 1
python -m experiments.graph_pipeline.evaluate --scenario multi --method graph --solution experiments/graph_pipeline/runs/multi_candidate/solution.ini --sim-cluster experiments/graph_pipeline/runs/multi_candidate/simulator_cluster.ini --offered 160 --duration 600 --warmup 180 --seed 1
python -m experiments.graph_pipeline.evaluate --scenario single --method helix --offered 400 --duration 600 --warmup 180 --seed 1
python -m experiments.graph_pipeline.evaluate --scenario multi --method helix --offered 160 --duration 600 --warmup 180 --seed 1
```

The comparison uses generated output tokens per second, P95 TTFT, P95 TPOT,
completion fraction, and backlog at both measurement boundaries. Both methods
receive the same online trace seed and offered load. Simulated time excludes
initial model loading, and the measurement window is `[start+180, start+600)`.

No physical GPU is required for these simulator results. They establish only
performance within Helix's profile and network assumptions.

## Seed 1 results

600 s simulated time, 180 s warmup. Higher output throughput is better; lower
P95 TTFT and P95 TPOT are better. Offered load is 400 token/s for the single
cluster and 160 token/s for the three-cluster topology.

| Scenario / layout and scheduler | Output token/s | P95 TTFT s | P95 TPOT s |
| --- | ---: | ---: | ---: |
| Single / Helix | 73.77 | 5.24 | 1.04 |
| Single / Helix layout + DAG scheduler | 75.33 | 4.62 | 0.88 |
| Single / graph layout + DAG scheduler | **76.13** | 4.72 | **0.76** |
| Three-cluster / Helix | 29.59 | 11.73 | 1.40 |
| Three-cluster / Helix layout + DAG scheduler | 30.68 | 9.37 | 1.12 |
| Three-cluster / graph layout + DAG scheduler | **34.60** | **5.92** | **0.82** |

Both candidate layouts beat full Helix on the prespecified three metrics. With
the same DAG scheduler, the single-cluster layout improves throughput and TPOT
but has 0.10 s higher TTFT than the Helix layout. The three-cluster layout
improves all three in that control.

Window-bounded P95 end-to-end latency is higher for both candidates (279.35 s
versus 207.26 s single-cluster; 311.99 s versus 145.16 s three-cluster).
The completion fractions are also higher (0.707 versus 0.641 and 0.612 versus
0.448), so this completion-conditioned E2E statistic compares different sets
of queries. No end-to-end latency improvement is claimed here. These are
single-seed simulator results, not a statistical or physical-GPU validation.

The raw seed-1 summary is `runs/comparison_seed1_600.json`; branch-wise model
breakdowns are `runs/single_explanation.json` and `runs/multi_explanation.json`.

## Deterministic refinement and long-window protocol

`refine.py` starts from the feasible graph placement. At each step it enumerates
one-layer transfers along a branch, adjacent stage swaps, feasible reductions
of the shared prefix, and activation of a spare device. Each candidate keeps a
complete 0-to-79 layer cover and respects device capacity. The search accepts
the best strict reduction of a fixed normalized cost: 40% longest prefill path,
35% longest decode path, and 25% largest per-resource demand. The complete
decision trace is saved as `search_trace.json`; there is no random move.

On the uniform single cluster, the search finds no strict improvement and
retains the initial placement. On the three-cluster topology it chooses 11
stage swaps, primarily changing which physical cross-region links are used;
no layer boundary shift is accepted. The surrogate falls from 1.0000 to
0.9666. This is a measured property of these two instances, not a claim that
boundary shifts can never help.

The long-window validation uses seed 1, 180 s warmup, then a full 1800 s
measurement interval (`--duration 1980 --warmup 180`). It compares full Helix,
the refined candidate, and the initial candidate for the three-cluster case.
The single-cluster refined and initial layouts are byte-identical. Commands:

```powershell
python -m experiments.graph_pipeline.refine --scenario single --initial experiments/graph_pipeline/runs/single_candidate/placement.json --output-dir experiments/graph_pipeline/runs/refined/single
python -m experiments.graph_pipeline.refine --scenario multi --initial experiments/graph_pipeline/runs/multi_candidate/placement.json --output-dir experiments/graph_pipeline/runs/refined/multi
python -m experiments.graph_pipeline.evaluate --scenario single --method helix --offered 400 --duration 1980 --warmup 180 --seed 1 --output experiments/graph_pipeline/runs/long/single_helix_seed1_1800.json
python -m experiments.graph_pipeline.evaluate --scenario single --method graph --solution experiments/graph_pipeline/runs/refined/single/solution.ini --sim-cluster experiments/graph_pipeline/runs/refined/single/simulator_cluster.ini --offered 400 --duration 1980 --warmup 180 --seed 1 --output experiments/graph_pipeline/runs/long/single_refined_seed1_1800.json
python -m experiments.graph_pipeline.evaluate --scenario multi --method helix --offered 160 --duration 1980 --warmup 180 --seed 1 --output experiments/graph_pipeline/runs/long/multi_helix_seed1_1800.json
python -m experiments.graph_pipeline.evaluate --scenario multi --method graph --solution experiments/graph_pipeline/runs/multi_candidate/solution.ini --sim-cluster experiments/graph_pipeline/runs/multi_candidate/simulator_cluster.ini --offered 160 --duration 1980 --warmup 180 --seed 1 --no-event-log --output experiments/graph_pipeline/runs/long/multi_initial_seed1_1800.json
python -m experiments.graph_pipeline.evaluate --scenario multi --method graph --solution experiments/graph_pipeline/runs/refined/multi/solution.ini --sim-cluster experiments/graph_pipeline/runs/refined/multi/simulator_cluster.ini --offered 160 --duration 1980 --warmup 180 --seed 1 --output experiments/graph_pipeline/runs/long/multi_refined_seed1_1800.json
python -m experiments.graph_pipeline.compare_long
```

`--no-event-log` disables retention of detailed event records to bound memory
use. A short identical-trace check produced the same numerical metrics with
and without this flag; scheduling and metric calculation do not read the log.

### 1800 s measurement results (seed 1)

| Scenario / method | Output token/s | P95 TTFT s | P95 TPOT s | P95 E2E s* | Completion fraction | Backlog at end |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Single / Helix | 89.06 | 5.54 | 1.19 | 488.23 | 0.848 | 111 |
| Single / graph placement + DAG scheduler | 91.12 | 4.91 | 0.81 | 337.03 | 0.892 | 79 |
| Three-cluster / Helix | 34.52 | 10.85 | 1.68 | 596.33 | 0.824 | 50 |
| Three-cluster / initial graph placement + DAG scheduler | 36.03 | 6.21 | 0.85 | 342.99 | 0.891 | 31 |
| Three-cluster / refined graph placement + DAG scheduler | 35.98 | 5.97 | 0.79 | 337.19 | 0.894 | 30 |

The single-cluster comparison has 732 arrivals and 730 TTFT/TPOT query samples
per method. The three-cluster comparison has 284 arrivals and 283 samples per
method. Against Helix, the refined method improves all three prespecified
metrics in both scenarios. Relative to the initial three-cluster graph layout,
refinement reduces TTFT by 3.86% and TPOT by 7.28%, while output throughput is
0.16% lower. The single-cluster search accepts no move, so its row measures
the original graph placement over the longer window.

*E2E P95 includes only requests created and completed within the measurement
window. The completion fractions differ, so this statistic is conditioned on
different subsets of requests. The result file at
`runs/long/comparison_seed1_1800.json` preserves the full numeric values.
These are one-seed simulator results with no physical GPU confirmation.

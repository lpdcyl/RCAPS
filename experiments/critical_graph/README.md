# Topology-conditioned critical-graph placement

## File map

| File | Role |
| --- | --- |
| `event_graph.py` | Request event DAG and resource critical path (challenge 1). |
| `path_ensemble.py` | Path-ensemble resource demand estimate (challenge 1). |
| `topology.py` | GPU capacities, physical links and placement cost model (challenge 2). |
| `partition.py` | Final capacity-constrained partition generator (challenge 2). |
| `fixed_window.py` | Simulator adapter used to measure candidate placements. |
| `compare_final.py`, `ablation_final.py` | Final placement comparison and ablation audits. |
| `resource_audit.py`, `model_audit.py` | Modeling checks and limitations. |
| `compare.py`, `compare_fixed.py`, `compare_py312.py`, `workload_dag_audit.py` | Earlier comparisons or robustness checks retained with their results. |
| `runs/` | Generated layouts, raw JSON and audit reports; `single_final/` and `multi_final/` are the adopted layouts. |

The repository-wide reading order is in [`../README.md`](../README.md).

This directory independently implements the first two research challenges. It
does not call Helix's max-flow model or placement optimizer. The unchanged
Helix event simulator and GPU profiles provide the execution environment. The
previously implemented layer-DAG scheduler is held fixed for placement
crossovers; online request scheduling is outside this method's scope.

## Method

**Challenge 1: explainable modeling.** `event_graph.py` builds a prefill/decode
event DAG with compute, bandwidth-occupied sending, propagation, and
resource-serialization edges. Max-plus longest paths expose representative
TTFT/TPOT critical resources. `path_ensemble.py` runs forward/backward
log-sum-exp dynamic programming on the layer-compatibility DAG. Its edge
marginals estimate GPU demand from every reachable stitched path without
enumerating complete routes. The link payload matches the simulator:
compute-to-compute sends carry token plus activation; bandwidth is occupied
for payload/bandwidth and propagation adds one RTT.

**Challenge 2: topology-aware placement.** `partition.py` contracts
fast-connected GPU regions, creates two capacity-feasible complete
layer-covering branches, and refines legal layer boundaries or adjacent stage
locations touching a critical resource. A gain priority queue accepts strict
reductions of a normalized score: 40% representative TTFT, 35% representative
TPOT, and 25% largest resource demand. A single fast-connected region uses
path-ensemble demand because stitched routes can merge at a GPU. Multiple
separated regions use canonical-path demand and emphasize the cross-region
critical path. The topology grouping determines this mode before evaluation;
the algorithm does not search whole placements or use the test trace to select
a move. The final generator makes 4 refinement moves in the single-cluster
case and 10 in the three-cluster case.

These are profile-based offline proxies. In particular, representative
critical-path delay is not a calibrated predictor of P95 latency under a long
overloaded trace; final metrics come only from the simulator.

## Protocol and main results

All main runs use LLaMa-70B, the supplied 24-GPU topologies/profiles, seed 1,
and the same generated request sequence within each scenario. The simulation
has a 180-second warmup and a following 1800-second measurement window.
Offered load is 400 tokens/s for one cluster and 160 tokens/s for three
clusters. Output throughput counts completed output tokens in the window;
TTFT and TPOT use requests arriving within it and token events completed
before its end. Completion fraction and end-of-window backlog are recorded to
expose censoring. `fixed_window.py` stops at the horizon instead of draining
the remaining backlog. A completed single-cluster control produced identical
window metrics under the original tail-draining and fixed-window drivers;
`compare_final.py` asserts this before mixing their records.

| Scenario | Placement + scheduler | Output tokens/s | P95 TTFT (s) | P95 TPOT (s) |
| --- | --- | ---: | ---: | ---: |
| Single | Original Helix + MaxFlow | 89.057 | 5.535 | 1.192 |
| Single | Helix placement + layer-DAG scheduler | 90.063 | 5.140 | 0.963 |
| Single | Final critical-graph placement + layer-DAG scheduler | **91.241** | **4.402** | **0.827** |
| Three clusters | Original Helix + MaxFlow | 34.516 | 10.847 | 1.676 |
| Three clusters | Helix placement + layer-DAG scheduler | 34.905 | 9.128 | 1.197 |
| Three clusters | Final critical-graph placement + layer-DAG scheduler | **35.962** | **6.351** | **0.799** |

Against original Helix, the final single-cluster layout improves throughput
2.45% and reduces P95 TTFT/TPOT 20.47%/30.61%; the three-cluster layout
improves them 4.19% and 41.44%/52.32%. Holding the layer-DAG scheduler fixed,
the placement effects are +1.31% throughput and -14.35%/-14.10% TTFT/TPOT
for one cluster, and +3.03% and -30.42%/-33.26% for three clusters.
`runs/comparison_final_seed1_1800.json` contains the exact values, source
paths, configuration hashes, and all three-metric checks. The evaluated
`single_ensemble` and generated `single_final` configurations are byte
identical; the same holds for `multi` and `multi_final`.
The `*_v2` and `*_v3` directories are intermediate, unvalidated model-audit
outputs and are not part of the final comparison.

A second full-window single-cluster placement crossover ran under Python
3.12.14/NumPy 2.3.5. The two layouts had the same request-trace SHA-256. The
new placement improved throughput 1.58% and reduced P95 TTFT/TPOT
14.05%/13.72% under the same layer-DAG scheduler; see
`runs/comparison_py312_seed1_1800.json`. A second full-window candidate run
with the noninteractive Agg backend exited successfully and produced an
identical JSON result. Values from different Python
environments are never mixed within a comparison.

## Modeling evidence and tradeoffs

For a separate 240-second resource-profile window, the measured GPU busy-rank
Spearman correlation of the canonical two-path demand versus the path-ensemble
demand was 0.75 versus 0.86 in one cluster, and 0.68 versus 0.81 in three
clusters. Their top-five busy-GPU overlap improved from 2 to 4 and from 3 to
4, respectively. See `runs/resource_audit_seed1_240.json`. This supports
the path-ensemble model as an explanation of load concentration; it is not a
claim of exact latency prediction.

The final single-cluster placement versus the earlier canonical-only placement
improves the 1800-second throughput 0.93% and reduces TTFT/TPOT
15.97%/10.79%. In the three-cluster 1800-second ablation, canonical refinement
reduces TPOT 3.99% relative to coarse partition, while throughput falls 0.07%
and TTFT rises 0.32%. The 420-second pilot suggested TTFT would improve, so
its direction does not generalize even to the longer window of the same seed.
The full figures and fixed-window/tail-drain equivalence checks are in
`runs/ablation_final_seed1_1800.json`. Applying path-ensemble refinement to
the three-cluster pilot slightly worsened all three metrics relative to
canonical refinement, so the topology-conditioned rule retains canonical
demand there.

The offline model misranked a single-cluster shared-prefix move: it predicted
TTFT worsening, whereas the 420-second simulator pilot showed improvement.
`runs/model_audit_seed1_420.json` records this and the three-cluster
directional agreement. Workload variability, batching, and dynamic queuing
remain outside this offline proxy. These are one-seed simulator results, not
physical-GPU measurements or evidence of robustness across traces. The
topology-conditioned mode was settled after inspecting seed-1 pilots, so
seed-1 should be treated as development evidence; held-out seeds are needed
for a generalizable paper claim.

## Reproduce

From the repository root, with `requirements.txt` installed:

```powershell
python -m unittest experiments.critical_graph.test_core -v
python -m experiments.critical_graph.partition --scenario single --output-dir experiments/critical_graph/runs/single_final
python -m experiments.critical_graph.partition --scenario multi --output-dir experiments/critical_graph/runs/multi_final
python -m experiments.critical_graph.fixed_window --scenario single --method graph --solution experiments/critical_graph/runs/single_final/solution.ini --sim-cluster experiments/critical_graph/runs/single_final/simulator_cluster.ini --offered 400 --duration 1980 --warmup 180 --seed 1 --output experiments/critical_graph/runs/single_final/long_fixed_seed1_1800.json
python -m experiments.graph_pipeline.evaluate --scenario multi --method graph --solution experiments/critical_graph/runs/multi_final/solution.ini --sim-cluster experiments/critical_graph/runs/multi_final/simulator_cluster.ini --offered 160 --duration 1980 --warmup 180 --seed 1 --no-event-log --output experiments/critical_graph/runs/multi_final/long_seed1_1800.json
python -m experiments.critical_graph.compare_final
python -m experiments.critical_graph.compare_py312
python -m experiments.critical_graph.ablation_final
python -m experiments.critical_graph.resource_audit
```

The comparison script uses the preserved successful seed-1 results in
`runs/single_ensemble` and `runs/multi` and verifies that their generated
final configurations have identical hashes. Windows has intermittently
reported native Python access-violation crashes during long simulations;
only runs that wrote results and exited successfully are counted.

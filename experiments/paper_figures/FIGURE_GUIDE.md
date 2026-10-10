# RCAPS paper figures

All PDFs are vector figures; PNGs are 300 dpi previews. Rebuild with
`python -m experiments.paper_figures.build_all` from the repository root and
check with `python -m experiments.paper_figures.verify_figures`. Each numbered
figure has its own Python source. The figures read experiment records from the
repository; plotted measurements are not typed into scripts.

## Main-text candidates

**Preferred combined framework figure:** [Integrated system framework](ccf_integrated_framework.pdf)
([editable SVG](ccf_integrated_framework.svg)). This places the event-DAG
model, placement planner, request scheduler, multi-cluster execution graph,
worker queues/layers/KV cache, and completion feedback in one system view.
It is a schematic; exact layer intervals are in Figs. 04 and 05.

| Figure | Purpose | Protocol and source |
| --- | --- | --- |
| [00 Method overview](fig00_method_overview.pdf) | Schematic of resource-dependency DAG, topology-conditioned layer partition, and queue-aware layered DAG routing | Algorithm schematic; no empirical data |
| [01 Main performance](fig01_main_performance.pdf) | Output throughput, P95 TTFT, P95 TPOT | Official offered loads, seeds 0/1/2, paired 1800 s runs; bars show mean and sample SD from `multiseed/runs/` |
| [02 Completion and backlog](fig02_completion_backlog.pdf) | Show request censoring and remaining work at fixed-window end | Same three-seed official-load runs as Fig. 01 |
| [03 Bottleneck rank agreement](fig03_bottleneck_ranks.pdf) | Test whether analytic resource demand identifies busy GPUs | 24 GPUs/scenario; seed 1; 240 s measurement after 60 s warmup; `resource_audit_seed1_240.json` and paired pilot profiles |
| [04 Single-cluster placement](fig04_single_placement.pdf) | Layer intervals assigned to each GPU type | Official Helix layout versus final partition; zero-based layer IDs |
| [05 Three-cluster placement](fig05_multi_placement.pdf) | Layer intervals and physical cluster boundaries | Official Helix layout versus final partition; physical clusters C1/C2/C3 from `3cluster24.ini` |
| [06 Controlled component effects](fig06_component_attribution.pdf) | Attribute improvements separately to placement and scheduling | Seeds 0/1/2, 1800 s measurement after 180 s warmup; paired benefit means and sample SD; placement fixes early scheduler, scheduling fixes final placement; **panels are independent controls and percentages must not be added** |
| [08 Cross-cluster hops](fig08_cross_cluster_hops.pdf) | Direct topology mechanism in the three-cluster case | Official-load routed requests with a first token in window (582 per arm); each consecutive route pair in different physical partitions adds one hop; mean 3.59 Helix versus 1.03 RCAPS |
| [10 Artifact-compatible latency](fig10_paper_latency.pdf) | Show prompt/decode request latency under published Helix definitions | Three-seed official-load runs; mean and sample SD; distinct from TTFT and TPOT |
| [13 Offered-load sweep](fig13_load_sweep.pdf) | Show throughput and P95 latency across three comparable offered-load points | 0.7/1/1.1 times official load; seeds 0/1/2; 1800 s, zero warmup; mean and sample SD; raw records in `ccfa_validation/runs/` and `multiseed/runs/` |
| [14 RTT sensitivity](fig14_rtt_sensitivity.pdf) | Test three-cluster performance as cross-cluster RTT changes | 0.5/1/2 times original WAN RTT; seeds 0/1/2; 1800 s, zero warmup; mean and sample SD; GPU, bandwidth and layer intervals unchanged |

## Supplementary candidates

| Figure | Purpose | Limitation |
| --- | --- | --- |
| [07 Route concentration](fig07_route_concentration.pdf) | Cumulative share of first-token requests carried by the top-ranked paths | More paths is descriptive, not a quality metric on its own |
| [09 Placement ablation](fig09_placement_ablation.pdf) | Internal refinement effects with both gains and regressions shown | Three paired seeds, development offered loads; mean and sample SD |
| [11 Partition trace](fig11_partition_trace.pdf) | Accepted moves reduce the offline normalized proxy objective | Proxy score is not simulator latency |
| [12 Development-load replication](fig12_development_load.pdf) | Independent lower-load end-to-end comparison | Seeds 0/1/2; 400/160 offered tokens/s, 180 s warmup, 1800 s measurement; mean and sample SD; do not join into a multi-load curve with Fig. 01 |
| [15 Actual single-cluster layer DAG](fig15_single_actual_layer_dag.pdf) ([editable SVG](fig15_single_actual_layer_dag.svg)) | Show the final placement's two designed suffixes, all exported compatibility links, and a real cross-branch transition | Generated directly from `critical_graph/runs/single_final/placement.json` and `simulator_cluster.ini`; structural path count does not imply runtime KV or queue feasibility |

## Reading and integrity notes

- Figs. 01, 02, 06, 09, 10, 12, 13, and 14 use **three paired seeds**. Error bars
  show sample SD across seeds, not confidence intervals. Descriptive route and
  bottleneck panels still show a labeled example seed; three-seed aggregates
  are in `multiseed/RESULTS.md`.
- The official-load experiments have zero warmup, 1800 s measurement, offered
  loads 700/320 tokens/s for one/three clusters, and paired request traces.
- End-to-end latency metrics in Fig. 01 are measured over requests that produce
  the corresponding samples within the fixed window. Fig. 02 reports completion
  and backlog so that censoring remains visible.
- Fig. 03 uses the earlier resource-audit layout, not the final official-load
  placement. Its correlation supports bottleneck ranking only; it is not a
  P95 latency prediction accuracy measurement.
- Fig. 06 uses two different controlled comparisons. It does not present an
  additive causal decomposition of the official-load improvement.
- `route_counts` record one route per query observed by the window accumulator.
  In the official runs their sums match `first_tokens_in_window` (1291/582).
- Final 1800 s run JSONs do not contain queue-length time series or the full
  per-request latency distribution. Time-series or CDF claims require fresh
  instrumented runs and are intentionally absent here.
- The 1.3-times official-load multi-cluster Helix arm fails to route within the
  window in all three seeds; Fig. 13 uses the completed 1.1-times load instead.
  The failure logs are retained in `ccfa_validation/runs/load/high/`.
- Replanning RCAPS at the 0.5- and 2-times RTTs produced the same layer
  intervals as the original topology. Fig. 14 therefore tests RTT sensitivity
  with fixed placements, not adaptive layer-boundary changes.

The paper-ready LaTeX includes and complete captions are in
[`latex_includes.tex`](latex_includes.tex).

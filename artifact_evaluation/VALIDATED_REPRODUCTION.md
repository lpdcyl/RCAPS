# Validated Reproduction Set

Validation date: 2026-09-14

This set keeps the original artifact scripts and simulator logic. No scheduler,
simulator, or ILP formulation changes are part of these results.

## Commands

Run from each scenario directory with the repository root on `PYTHONPATH`:

```text
python step1_gen_cluster.py
python step2_gen_layout.py petals llama70b
python step2_gen_layout.py ilp llama70b
python step3_simulation.py helix llama70b offline
```

For LLaMA-30B, the corresponding original commands use
`step2_gen_layout.py ilp llama30b`; the script sets the ILP limit to 1 second
per homogeneous subcluster, as in the artifact source.

## Results

All listed offline simulations completed successfully.

| Scenario | Model | Helix throughput (tokens/s) |
|---|---|---:|
| single_cluster | llama30b | 328.1 |
| single_cluster | llama70b | 180.8 |
| distributed_clusters | llama30b | 232.7 |
| distributed_clusters | llama70b | 105.4 |
| high_heterogeneity | llama70b | 614.4 |

## ILP incumbents

| Scenario | Model | Best objective | Manual stop |
|---|---|---:|---:|
| single_cluster | llama70b | 952.1074 | about 20 min |
| distributed_clusters | llama70b | 1212.1768 | about 20 min |
| high_heterogeneity | llama70b | 3774.6427 | about 21 min |

The generated layout, simulator cluster, raw solution, and LP model are kept
under the corresponding `layout_*/ilp` directory. The author-provided
reference copy remains under `artifact_evaluation_reference_backup_windows`.

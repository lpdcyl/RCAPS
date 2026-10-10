# RCAPS

**Resource Contention-Aware Placement and Scheduling for Heterogeneous LLM Serving**

RCAPS studies LLaMA-70B serving on heterogeneous 24-GPU clusters. It combines (1) an event graph for computation, communication, and resource contention, (2) a capacity- and topology-constrained shared-prefix/two-suffix placement, and (3) online request routing over the layer-compatible DAG using current GPU/link work and active KV sessions.

## Start here

- [Method and limitations](experiments/METHOD_FRAMEWORK.md)
- [Experiment navigation](experiments/README.md)
- [Placement implementation](experiments/critical_graph/partition.py)
- [Online scheduler](experiments/queue_dag/scheduler_final.py)
- [Main three-seed results](experiments/multiseed/RESULTS.md)
- [Additional validation](experiments/ccfa_validation/RESULTS.md)

## Reproduce

Use a Python environment with the packages in `requirements.txt` and a working Gurobi 13 license. Run from the repository root:

```bash
python -m experiments.critical_graph.partition --scenario single --output-dir experiments/critical_graph/runs/single_final
python -m experiments.critical_graph.partition --scenario multi --output-dir experiments/critical_graph/runs/multi_final
python -m experiments.multiseed.run --dry-run
python -m experiments.multiseed.run --workers 4
python -m experiments.multiseed.aggregate
```

The two adopted `solution.ini`, `simulator_cluster.ini`, and `placement.json` files are included. The `simulator/trace_generator` pickle files are required input traces. Paper data JSON, summary tables, plotting code, and generated PDF/PNG/SVG figures are included. Large checkpoints and run logs are omitted; the commands regenerate them. Real-GPU execution also requires separately obtained model weights and tokenizer files. The reported measurements were made with the Helix event simulator, not physical GPUs.

## Provenance

This repository includes the Helix simulator and baseline configuration code under the original [LICENSE](LICENSE). See [the original Helix README](HELIX_README.md) and [Helix ASPLOS 2025 repository](https://github.com/Thesys-lab/Helix-ASPLOS25). RCAPS method code and experiments are in `experiments/`.


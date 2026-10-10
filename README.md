# RCAPS

**Resource Contention-Aware Placement and Scheduling for Heterogeneous LLM Serving**

RCAPS V1 addresses three connected decisions: matching heterogeneous GPU and network resources, balancing layer sharing with replicated execution paths, and routing requests under current resource contention. It combines topology- and capacity-constrained shared-prefix/two-suffix placement with online routing over a layer-compatible DAG. The event graph and critical-resource search refine placement; ready decode-transfer coalescing is an execution optimization. Measurements use the Helix event simulator on heterogeneous 24-GPU LLaMA-70B configurations.

## Project structure

| Directory | Role |
| --- | --- |
| [`rcaps/`](rcaps/) | Main method: placement, online scheduling, and final deployable layouts in `rcaps/layouts/` |
| [`baselines/`](baselines/) | Baseline adapters; Helix placement and max-flow scheduling are registered here |
| [`benchmarks/`](benchmarks/) | Shared fixed-window simulator protocol, method registry, paired runner, and comparison |
| [`experiments/`](experiments/) | Historical experiments, paper result JSON, analysis, figures, and compatibility entry points |
| [`simulator/`](simulator/) | Original Helix simulator used by all methods |

The V1 research claims and their limits are fixed in [the Chinese framework](paper/RESEARCH_FRAMEWORK_V1_CN.md), with implementation details in [the method framework](experiments/METHOD_FRAMEWORK.md). See [experiment navigation](experiments/README.md), [three-seed results](experiments/multiseed/RESULTS.md), [placement versus scheduler crossover](experiments/validation_2026/CROSS_RESULTS.md), [execution-path structure ablation](experiments/structure_ablation_2026/RESULTS.md), [additional validation](experiments/ccfa_validation/RESULTS.md), [the paper figure guide](experiments/paper_figures/FIGURE_GUIDE.md), and [the benchmark protocol](benchmarks/README.md). Chinese drafts of the [Introduction](paper/INTRODUCTION_CN.md) and [experimental setup](paper/EXPERIMENTAL_SETUP_CN.md) record the paper claims and protocol.

The `research/adaptive-structure-v2` branch adds an experimental optimizer that selects a multi-GPU shared stem and two or three complete suffixes. Its implementation and paired evaluation are documented in [the V2 experiment](experiments/adaptive_v2/README.md). The V1 release is fixed at tag `v1.0.0-research`; V2 does not replace that result.

## Run

Install `requirements.txt` in a Python environment and provide a working Gurobi 13 license for regenerating placement. Run commands from the repository root:

```bash
python -m rcaps.placement.partition --scenario single --output-dir rcaps/layouts/single
python -m rcaps.placement.partition --scenario multi --output-dir rcaps/layouts/multi
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps helix
python -m benchmarks.compare --baselines helix
python -m experiments.paper_figures.build_all
python -m experiments.paper_figures.verify_figures
```

The benchmark runner uses the same offered load, seed, time window, and trace generation for each registered method. Results go to `benchmarks/runs/<scenario>/seed<seed>/<method>.json`. It checks layout identity before reusing a result; `benchmarks.compare` also checks paired trace and protocol fields. To add another baseline, create an adapter like [`baselines/helix.py`](baselines/helix.py) and register it in [`benchmarks/registry.py`](benchmarks/registry.py). The runner and comparison script then accept its name.

The adopted layouts are included. The trace-generator pickle files are required simulator inputs. Paper JSON, summary tables, plotting code, and PDF/PNG/SVG figures are included; large checkpoints and logs are omitted. Real GPU execution requires separately obtained model weights and tokenizer files. Reported results are from the event simulator, not physical GPUs.

Historical records retain their original `green` and `integrated` keys and filenames so published calculations remain reproducible. These names denote the RCAPS method. Old `experiments.critical_graph` and `experiments.queue_dag` imports remain as compatibility entry points.

## Provenance

This repository includes the Helix simulator and baseline configuration code under the original [LICENSE](LICENSE). See [the original Helix README](HELIX_README.md) and [Helix ASPLOS 2025 repository](https://github.com/Thesys-lab/Helix-ASPLOS25).

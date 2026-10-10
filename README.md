# RCAPS

**Resource Contention-Aware Placement and Scheduling for Heterogeneous LLM Serving**

RCAPS combines a resource-dependent event graph, capacity- and topology-constrained shared-prefix/two-suffix placement, and queue-aware routing over the exported layer-compatible DAG. Its measurements use the Helix event simulator on heterogeneous 24-GPU LLaMA-70B configurations.

## Project structure

| Directory | Role |
| --- | --- |
| [`rcaps/`](rcaps/) | Main method: placement, online scheduling, and final deployable layouts in `rcaps/layouts/` |
| [`baselines/`](baselines/) | Baseline adapters; Helix placement and max-flow scheduling are registered here |
| [`benchmarks/`](benchmarks/) | Shared fixed-window simulator protocol, method registry, paired runner, and comparison |
| [`experiments/`](experiments/) | Historical experiments, paper result JSON, analysis, figures, and compatibility entry points |
| [`simulator/`](simulator/) | Original Helix simulator used by all methods |

The current implementation is described in [the method framework](experiments/METHOD_FRAMEWORK.md). See [experiment navigation](experiments/README.md), [three-seed results](experiments/multiseed/RESULTS.md), [additional validation](experiments/ccfa_validation/RESULTS.md), and [the paper figure guide](experiments/paper_figures/FIGURE_GUIDE.md).

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

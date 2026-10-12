# RCAPS

**Resource Contention-Aware Placement and Scheduling for Heterogeneous LLM Serving**

The default RCAPS method is V2. It selects a shared A100 prefix and two or three complete suffixes under heterogeneous GPU, memory, and network constraints, then routes requests over the exported layer-compatible DAG using the existing online scheduler. Measurements use the Helix event simulator on heterogeneous 24-GPU LLaMA-70B configurations. The earlier V1 shared-prefix/two-suffix method is retained as an explicit comparison under the historical method name `rcaps`.

## Project structure

| Directory | Role |
| --- | --- |
| [`rcaps/`](rcaps/) | V2 adaptive placement, shared online scheduler, and adopted layouts in `rcaps/v2_layouts/`; V1 comparison layouts remain in `rcaps/layouts/` |
| [`baselines/`](baselines/) | Baseline adapters; Helix placement and max-flow scheduling are registered here |
| [`benchmarks/`](benchmarks/) | Shared fixed-window simulator protocol, method registry, paired runner, and comparison |
| [`experiments/`](experiments/) | Historical experiments, paper result JSON, analysis, figures, and compatibility entry points |
| [`simulator/`](simulator/) | Original Helix simulator used by all methods |

Start with the [V2 method and paired results](experiments/adaptive_v2/README.md) and the [benchmark protocol](benchmarks/README.md). The [experiment navigation](experiments/README.md) separates V2 evidence from earlier V1 work. V1 claims and limitations remain documented in the [historical framework](paper/RESEARCH_FRAMEWORK_V1_CN.md).

The adopted V2 layouts and three-seed paired results are included in this branch. The V1 release remains available at tag `v1.0.0-research` for provenance; the active benchmark registry exposes V1 only as the `rcaps` comparison method. Older V1 ablations remain in the history and result files but are not active benchmark methods.

## Run

Install `requirements.txt` in a Python environment. A working Gurobi 13 license is required only to regenerate layouts. Run commands from the repository root:

```bash
python -m benchmarks.run --dry-run
python -m benchmarks.run
python -m benchmarks.compare
python -m benchmarks.compare --baselines rcaps
```

Without `--methods`, the runner selects `rcaps_v2` and `helix`. The comparison script defaults to V2 versus Helix; use `--baselines rcaps` for V2 versus the V1 two-suffix method. Both commands use the same offered load, seed, time window, and trace generation. Results go to `benchmarks/runs/<scenario>/seed<seed>/<method>.json`; the runner checks layout identity before reuse, and the comparison script checks paired traces and protocol fields. Existing V2 JSON files retain their historical `role` and `main_method` metadata rather than being rewritten when the registry default changes.

The adopted layouts are included. The trace-generator pickle files are required simulator inputs. Paper JSON, summary tables, plotting code, and PDF/PNG/SVG figures are included; large checkpoints and logs are omitted. Real GPU execution requires separately obtained model weights and tokenizer files. Reported results are from the event simulator, not physical GPUs.

Historical V1 records retain their original `green` and `integrated` keys and filenames so their calculations remain reproducible. Old `experiments.critical_graph` and `experiments.queue_dag` imports remain as compatibility entry points.

## Provenance

This repository includes the Helix simulator and baseline configuration code under the original [LICENSE](LICENSE). See [the original Helix README](HELIX_README.md) and [Helix ASPLOS 2025 repository](https://github.com/Thesys-lab/Helix-ASPLOS25).

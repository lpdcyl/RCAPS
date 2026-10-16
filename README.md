# RCAPS

**Resource Contention-Aware Placement and Scheduling for Heterogeneous LLM Serving**

The default RCAPS method is V3. Its graph-only M1 defines physical resources and legal layer-compatible execution edges. Multistage M2 searches one or two branch boundaries with a static heterogeneous-resource objective; the existing queue-aware DAG scheduler remains M3. The adopted search configuration allows any GPU type in the initial shared segment, although the selected C1 layouts still use A100s there. V2 and V1 remain available as explicit historical comparisons. Measurements use the Helix event simulator on heterogeneous LLaMA-70B configurations.

## Project structure

| Directory | Role |
| --- | --- |
| [`rcaps/`](rcaps/) | Frozen V3 method and layouts in `rcaps/v3/` and `rcaps/v3_layouts/`; V2 and V1 layouts remain available |
| [`baselines/`](baselines/) | Baseline adapters; Helix placement and max-flow scheduling are registered here |
| [`benchmarks/`](benchmarks/) | Shared fixed-window simulator protocol, method registry, paired runner, and comparison |
| [`experiments/`](experiments/) | Historical experiments, paper result JSON, analysis, figures, and compatibility entry points |
| [`simulator/`](simulator/) | Original Helix simulator used by all methods |

Start with the [V3 release and evidence](experiments/v3_release/README_CN.md) and the [benchmark protocol](benchmarks/README.md). The [experiment navigation](experiments/README.md) separates V3 from historical V2 and V1 evidence. V1 claims and limitations remain documented in the [historical framework](paper/RESEARCH_FRAMEWORK_V1_CN.md).

The V3 layouts and audited seed-0/1/2 candidate windows are included in this branch. V2 remains registered as `rcaps_v2`; the V1 release remains available at tag `v1.0.0-research` and as the explicit `rcaps` comparison method.

## Run

Install `requirements.txt` in a Python environment. A working Gurobi 13 license is required only to regenerate layouts. Run commands from the repository root:

```bash
python -m benchmarks.run --dry-run
python -m benchmarks.run
python -m benchmarks.compare
python -m benchmarks.compare --baselines rcaps
```

Without `--methods`, the runner selects `rcaps_v3` and `helix`. The comparison script defaults to V3 versus Helix; use `--baselines rcaps_v2` or `--baselines rcaps` for historical methods. Both commands use the same offered load, seed, time window, and trace generation. Results go to `benchmarks/runs/<scenario>/seed<seed>/<method>.json`; the runner checks layout identity before reuse, and the comparison script checks paired traces and protocol fields. V3 formal windows are explicitly marked as audited reuse from the identical multistage candidate deployment and execution semantics. Existing V2 JSON files retain their historical metadata.

The adopted layouts are included. The trace-generator pickle files are required simulator inputs. Paper JSON, summary tables, plotting code, and PDF/PNG/SVG figures are included; large checkpoints and logs are omitted. Real GPU execution requires separately obtained model weights and tokenizer files. Reported results are from the event simulator, not physical GPUs.

Historical V1 records retain their original `green` and `integrated` keys and filenames so their calculations remain reproducible. Old `experiments.critical_graph` and `experiments.queue_dag` imports remain as compatibility entry points.

## Provenance

This repository includes the Helix simulator and baseline configuration code under the original [LICENSE](LICENSE). See [the original Helix README](HELIX_README.md) and [Helix ASPLOS 2025 repository](https://github.com/Thesys-lab/Helix-ASPLOS25).

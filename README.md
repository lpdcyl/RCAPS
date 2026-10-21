# RCAPS V3

RCAPS V3 is the **current research method** for heterogeneous LLM serving. It
combines a physical-resource and layer-compatibility graph (M1), multistage
shared/replicated placement (M2), and live resource-aware DAG routing (M3).
M1 defines legal execution relationships; performance claims concern M2, M3,
and the complete system. Results are from the Helix event simulator, not a
physical GPU deployment.

## Start here

| Purpose | Entry |
| --- | --- |
| V3 implementation and adopted layouts | [`rcaps/v3/`](rcaps/v3/), [`rcaps/v3_layouts/`](rcaps/v3_layouts/) |
| Fixed-window protocol and baseline adapters | [`benchmarks/README.md`](benchmarks/README.md), [`baselines/`](baselines/) |
| Frozen V3 identity and V3–Helix evidence | [`experiments/v3_release/README_CN.md`](experiments/v3_release/README_CN.md) |
| V3 experiment index | [`experiments/README.md`](experiments/README.md) |
| Paper evidence and claim boundaries | [`paper/V3_EVIDENCE_CN.md`](paper/V3_EVIDENCE_CN.md) |
| Independent code and experiment review | [`REVIEW_GUIDE_CN.md`](REVIEW_GUIDE_CN.md) |

The adopted V3 rule is `multi_any`: M2 searches at most two branch boundaries
and permits any GPU type in the initial shared segment. A selected layout may
still have only one boundary. The C1 single-cluster layout is `1→4→3`; the C1
three-cluster layout is `1→3`.

## Run the current method

Install [`requirements.txt`](requirements.txt), then run from the repository
root. Layout regeneration needs a working Gurobi license; the adopted layouts
are included.

```powershell
python -m experiments.v3_release.verify --allow-diagnostic-probe
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps_v3 helix --seeds 0 1 2
python -m benchmarks.compare --baselines helix --seeds 0 1 2
```

The benchmark defaults are V3 and Helix ILP on the C1 single- and
three-cluster topologies, with offered loads of 700/320 token/s, seeds 0/1/2,
1800-second windows, zero warmup, and no tail drain. Swarm and Separate
Pipelines are separate external comparisons at a common lower load; see the
[four-method report](experiments/v3_four_method_comparison/RESULTS_CN.md).
The runner checks layout identity before reusing a result, and comparison
checks the paired request traces.

On this research branch, `fixed_window.py` also has an opt-in diagnostic
probe. The pinned `--allow-diagnostic-probe` check verifies the unchanged V3
method, layouts, and evidence while explicitly accepting that one runner
variant. The strict verifier still detects the runner's changed file hash.

## Repository scope

The current tree contains the V3 method, its controlled experiments, and
the Helix simulator and artifact inputs needed to reproduce the comparisons.
The paper evidence index separates the high-load and common-load protocols.

This repository includes the original Helix simulator and artifact inputs.
See [`LICENSE`](LICENSE), [`HELIX_README.md`](HELIX_README.md), and the
[Helix ASPLOS 2025 repository](https://github.com/Thesys-lab/Helix-ASPLOS25)
for upstream provenance.

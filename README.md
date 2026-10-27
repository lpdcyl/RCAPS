# RCAPS — integrated method, V4 implementation

The paper's subject is the complete **RCAPS** system. V4 identifies its current
implementation; V3 is an internal historical reference or the verified
S/T-disabled condition. Present external comparisons first, final-system
M2/M3/S/T ablations second, and mechanisms, sensitivity and scope afterward.
See the [current code and evidence overview](paper/RCAPS_V4_SYSTEM_OVERVIEW_20261026_CN.md)
and its [offline verification record](paper/RCAPS_V4_OVERVIEW_AUDIT_20261026.json).

The subsequent validation extension has finished: all 75 registered windows
were attempted, with 63 successful runs and 12 retained failures. See the
[final validation report](experiments/v4_validation/RESULTS_CN.md),
[current evidence status](paper/RCAPS_V4_EVIDENCE_STATUS_CN.md), and
[writing blueprint](paper/RCAPS_WRITING_BLUEPRINT_CN.md). Hardware calibration
and complete higher-load external comparisons remain evidence gaps.

The core supplement is also complete: six session-cost ablations and nine
registered chunk-boundary-cost conditions produced 14 successful windows and
one retained native failure. All 14 accepted results passed the recorded
727 reconciliation checks; nine frozen reference windows are reused.
See the [core results](experiments/v4_core_validation/RESULTS_CN.md),
[publication index](experiments/PUBLISHED_RESULTS_CN.md), and
[Chinese research report](paper/RCAPS_研究主线与实验进展汇报.docx).
The chunk costs are simulation assumptions, not measured hardware overhead.

The earlier registered campaign has 120 successful windows from 122 attempts, with two
native-process failures retained and two explicitly authorized retries.
See the [final Chinese report](experiments/v4_paper/FINAL_RESULTS_CN.md),
[verified numerical tables](experiments/v4_paper/RESULTS_CN.md), and
[failure and recovery audit](experiments/v4_paper/EXECUTION_AUDIT_CN.md).
Broader robustness and real-hardware evidence remain incomplete; the native
crash and historical TypeError root causes remain unresolved.

RCAPS V4 is the **current integrated research method** for heterogeneous LLM
serving. It retains frozen V3's physical-resource and layer-compatibility graph
(M1), multistage shared/replicated placement (M2), and live resource-aware DAG
routing (M3), and adds static sparse edge admission plus fixed 4 MiB Prompt
activation-transfer chunks on slow compute links. Frozen V3 remains an internal
reference and a joint S/T-disabled condition where equivalence is verified.
M1 defines legal execution relationships; performance claims concern M2, M3,
and the complete system. Results are from the Helix event simulator, not a
physical GPU deployment.

## Start here

| Purpose | Entry |
| --- | --- |
| V4 implementation and integrated adapter | [`rcaps/v4/`](rcaps/v4/), [`rcaps/v4_method.py`](rcaps/v4_method.py) |
| V4 formal protocol, queue and failure policy | [`experiments/v4_formal/README.md`](experiments/v4_formal/README.md) |
| Uniform external-baseline resource accounting | [`experiments/v4_external/README.md`](experiments/v4_external/README.md) |
| V4 paper plan | [`paper/V4_EXPERIMENT_PLAN_20261026_CN.md`](paper/V4_EXPERIMENT_PLAN_20261026_CN.md) |
| V3 implementation and adopted layouts | [`rcaps/v3/`](rcaps/v3/), [`rcaps/v3_layouts/`](rcaps/v3_layouts/) |
| Fixed-window protocol and baseline adapters | [`benchmarks/README.md`](benchmarks/README.md), [`baselines/`](baselines/) |
| Frozen V3 identity and V3–Helix evidence | [`experiments/v3_release/README_CN.md`](experiments/v3_release/README_CN.md) |
| V3 experiment index | [`experiments/README.md`](experiments/README.md) |
| Paper evidence and claim boundaries | [`paper/V3_EVIDENCE_CN.md`](paper/V3_EVIDENCE_CN.md) |
| Current complete-system review | [`paper/RCAPS_V4_SYSTEM_OVERVIEW_20261026_CN.md`](paper/RCAPS_V4_SYSTEM_OVERVIEW_20261026_CN.md) |
| Historical V3 code and experiment review | [`REVIEW_GUIDE_CN.md`](REVIEW_GUIDE_CN.md) |

The adopted V3 rule is `multi_any`: M2 searches at most two branch boundaries
and permits any GPU type in the initial shared segment. A selected layout may
still have only one boundary. The C1 single-cluster layout is `1→4→3`; the C1
three-cluster layout is `1→3`.

## Run the current method

For the frozen paper campaign, follow the V4 formal and external batch READMEs
above. All formal windows use seeds **0/1/2**, 1800 seconds, zero warmup and no
tail drain. Historical intermittent runtime failures remain documented; a fresh
failure stops new dispatch rather than being silently retried. The complete
paper claim remains limited to the audited configurations and stated evidence gaps.

Install [`requirements.txt`](requirements.txt), then run from the repository
root. Layout regeneration needs a working Gurobi license; the adopted layouts
are included.

```powershell
python -m experiments.v3_release.verify
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps_v4 rcaps_v3 helix --seeds 0 1 2 --results-dir benchmarks/v4_ad_hoc
```

The shared benchmark defaults are V4 and Helix ILP on the C1 single- and
three-cluster topologies, with offered loads of 700/320 token/s, seeds 0/1/2,
1800-second windows, zero warmup, and no tail drain. Swarm and Separate
Pipelines are separate external comparisons at a common lower load; see the
[four-method report](experiments/v3_four_method_comparison/RESULTS_CN.md).
The runner checks layout identity before reusing a result, and comparison
checks the paired request traces.

`fixed_window.py` includes an opt-in diagnostic probe. The release manifest
records this runner along with the V3 layouts and evidence, so strict
verification covers the current tree.

## Repository scope

The current tree contains V4, frozen V3, their controlled experiments, and
the Helix simulator and artifact inputs needed to reproduce the comparisons.
The paper evidence index separates the high-load and common-load protocols.

This repository includes the original Helix simulator and artifact inputs.
See [`LICENSE`](LICENSE), [`HELIX_README.md`](HELIX_README.md), and the
[Helix ASPLOS 2025 repository](https://github.com/Thesys-lab/Helix-ASPLOS25)
for upstream provenance.

# RCAPS benchmark protocol

Run from the repository root with the Python environment in `requirements.txt`.
The published comparisons use the Helix event simulator, two 24-GPU LLaMA-70B
topologies, 1800-second fixed windows, zero warmup, and offered loads of 700
tokens/s (single cluster) or 320 tokens/s (three clusters). A finished window is
not drained. A result includes the seed, generated request-trace hash, layout
and simulator-configuration hashes, software versions, arrival count, throughput,
TTFT/TPOT samples, completion fraction, and end-of-window backlog.

```powershell
python -m benchmarks.manifest
python -m benchmarks.run --dry-run
python -m benchmarks.run --seeds 0 1 2 --workers 12
python -m benchmarks.compare --baselines helix --seeds 0 1 2
python -m benchmarks.compare --baselines rcaps --seeds 0 1 2
python -m benchmarks.paired_stats --seeds 0 1 2
python -m experiments.v3_release.verify
python -m experiments.v3_release.reuse_formal
```

The default run executes `rcaps_v3` and `helix`; the default comparison uses
V3 as the main method. Its three-seed C1 result files record audited reuse
from the multistage candidate; see `experiments/v3_release/README_CN.md`.
The historical `rcaps` V1 shared-prefix/two-suffix
adapter is available explicitly for comparison. `rcaps_v2_fixed_structure`
is a V2 search constrained to a one-GPU prefix and two suffixes; it is an
ablation of the V2 structure search, not the same method as V1. Existing
result JSON files keep their original registry metadata for provenance.
The formal layout INI files have fixed byte hashes; `.gitattributes` prevents
Git line-ending conversion from changing those hashes on a fresh checkout.

Each new run also records per-query first-token time, mean inter-token time,
arrival length, and completion status. `benchmarks.compare` verifies paired
query IDs and inputs before reporting P95 latency on the cohort observed in
both methods. This sensitivity analysis complements the original fixed-window
P95; it does not remove censoring of requests without an output sample.

The active methods are:

| Name | Role |
| --- | --- |
| `rcaps_v3` | Default main method |
| `helix` | Default external baseline |
| `rcaps_v2` | Explicit historical V2 comparison |
| `rcaps` | Explicit V1 two-suffix comparison |
| `rcaps_v2_fixed_structure` | Explicit V2 structure ablation |

To run the two internal comparisons explicitly:

```powershell
python -m benchmarks.run --methods rcaps rcaps_v2_fixed_structure --scenarios single multi --seeds 0 1 2
python -m benchmarks.compare --baselines rcaps rcaps_v2_fixed_structure --seeds 0 1 2
```

V1-specific ablation code and result files remain for historical provenance,
but they are no longer registered as current benchmark methods. The V2
structure comparison is documented in
[the V2 experiment](../experiments/adaptive_v2/README.md).

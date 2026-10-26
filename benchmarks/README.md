# RCAPS V4 benchmark protocol

The active research method is `rcaps_v4`; frozen `rcaps_v3` is an internal
baseline. The registered external systems are
Helix ILP (`helix`), Swarm (`swarm`), and Separate Pipelines (`separate`).
V4 reuses V3's deployed layouts and route prices, adding static sparse admission
and slow-link 4 MiB transfer chunks. The frozen paper runs use the dedicated
[`v4_formal`](../experiments/v4_formal/README.md) and
[`v4_external`](../experiments/v4_external/README.md) manifests, which include
full runtime/data hashes and preserve every failed attempt.

The primary C1 comparison uses the Helix event simulator, 24 heterogeneous
GPUs, offered loads of 700 token/s (single cluster) and 320 token/s (three
clusters), paired seeds 0/1/2, 1800-second windows, zero warmup, and no tail
drain. All methods in a comparison must use the same topology, offered load,
seed, request trace, and measurement window. The four-method common-load
experiment instead uses 350/160 token/s and reports its results separately.

```powershell
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps_v4 rcaps_v3 helix --seeds 0 1 2 --results-dir benchmarks/v4_ad_hoc
python -m experiments.v3_release.verify
```

The runner reuses a window only when its method, protocol, and deployment
hashes match. The comparison checks paired trace hashes and request identities,
then reports throughput, P95 TTFT/TPOT, completion, backlog, and latency on
the jointly observed cohort. P95 values come from samples observed within the
fixed window; unfinished requests must be considered when interpreting them.
Seed-level variation from three seeds is descriptive, not a significance claim.

V3's adopted INI files are in `rcaps/v3_layouts/`. Their identity and source
candidate are recorded in `experiments/v3_release/manifest.json`. The frozen
V3 code and layout byte hashes must not be changed as part of document cleanup.

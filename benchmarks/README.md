# RCAPS V3 benchmark protocol

The active research method is `rcaps_v3`. The registered external systems are
Helix ILP (`helix`), Swarm (`swarm`), and Separate Pipelines (`separate`).
The repository has one RCAPS method identity, `rcaps_v3`.

The primary C1 comparison uses the Helix event simulator, 24 heterogeneous
GPUs, offered loads of 700 token/s (single cluster) and 320 token/s (three
clusters), paired seeds 0/1/2, 1800-second windows, zero warmup, and no tail
drain. All methods in a comparison must use the same topology, offered load,
seed, request trace, and measurement window. The four-method common-load
experiment instead uses 350/160 token/s and reports its results separately.

```powershell
python -m benchmarks.manifest --output paper/V3_RUN_MANIFEST.json
python -m benchmarks.run --dry-run
python -m benchmarks.run --methods rcaps_v3 helix --seeds 0 1 2
python -m benchmarks.compare --baselines helix --seeds 0 1 2
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

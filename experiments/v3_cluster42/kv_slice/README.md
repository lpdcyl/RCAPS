# Executed-layer KV admission study

This is a CPU event simulation on the 42-compute-node / 64-physical-GPU cluster,
not a deployment on real GPUs. `DESIGN_CN.md` explains the mechanism;
`protocol.json` records selection and final acceptance rules.

From the repository root in PowerShell:

```powershell
$env:PYTHONHASHSEED = '0'
python -m experiments.v3_cluster42.test_kv_admission
python -m experiments.v3_cluster42.slice_plan
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_slice --phase screening
python -m experiments.v3_cluster42.capacity_report --root experiments/v3_cluster42/kv_slice
```

Screening is seed 101, 600 seconds, zero warmup, no tail drain. The shared Helix
baseline lives at `../kv_capacity/runs/screening/helix_seed101.json`. Its trace
SHA-256 is `11f7fbb50d27f24927f929316e356b754f6f427f13c75fdfa5847c347c4eec6e`.
The three candidates can also run in separate processes using `--candidate`.
Existing outputs with matching run identity are reused. Use a new name/root
when changing an implementation or layout; never overwrite prior evidence.

Only after screening passes all three performance criteria, commit the chosen
name to `formal.candidate` in the protocol. Then run:

```powershell
python -m experiments.v3_cluster42.kv_candidate_run --root experiments/v3_cluster42/kv_slice --phase formal
python -m experiments.v3_cluster42.capacity_report --root experiments/v3_cluster42/kv_slice
```

Formal runs use seeds 0, 1, 2 at 1800 seconds, paired with the original Helix
2150-load formal results. A missing or failed window never passes. The report
checks trace/window/cluster identity, layout hash, candidate and admission mode,
and counts physical devices from the registered layout's machine types.

The legacy JSON field `active_gpus` counts compute nodes. Counts here are:

| Candidate | Compute nodes | Physical GPUs |
|---|---:|---:|
| Helix full pool | 42 | 64 |
| c400k_slice_w3_b1 | 31 | 53 |
| c600k_slice_w2_b20 | 17 | 38 |
| c600k_slice_w3_b12 | 40 | 62 |

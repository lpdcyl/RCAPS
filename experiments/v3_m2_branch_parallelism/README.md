# M2 shared-prefix replica-branch ablation

This experiment tests a **single** boundary at layer 48. The physical resource
pool, prefix assignment, request trace, simulator, M1 graph construction, and
M3 live routing costs are fixed within each case. From one frozen `1 -> 3`
parent, `k1`, `k2`, and `k3` retain nested complete suffix replicas. `k1`
contains one copy of every model layer and is the zero-replication control.
The released Helix placements also contain copied layers, so they cannot
serve as a zero-replication control for this mechanism question.

`C1_single/equal_gpu_k2` uses the same 24 GPUs and prefix as `C1_single/k3`,
but forms two suffix replicas. This comparison controls active GPU count,
while the number of deployed layer copies and layer assignment still differ.

## Files

- `parents/*.json`: frozen parent states copied from the candidate bank or
  released V3 layout; no dependency on an untracked candidate bank at rerun.
- `plan.json`: exported layout hashes, physical input hashes, canonical path
  counts, branch GPU lists, and static resource structure.
- `formal_protocol.json`: preselected 700/320 token/s, seed 1/2/3 comparison.
- `adaptive_protocol.json`: separately declared 600 token/s, seed 4/5/6
  supplement after single-path KV failure at 700 token/s.
- `runs/explore`: seed-0 load scan; `runs/formal`: independent seed runs.
- `runs/subsets`: all other one- and two-branch choices at the key load.
- `runs/full_dag`: same deployment and trace with the full M1-compatible DAG.
- `run_manifest.json`: hash ledger for the planned 65 windows, including
  capacity-failure logs and trace-pairing checks.
- `analysis.json`, `FINDINGS_CN.md`, `PAPER_TEXT_EN.md`, and
  `figure_branch_parallelism.*`: derived reports, suggested paper wording,
  and paper figure. Raw request samples remain in each run JSON.

## Reproduce

From the repository root:

```powershell
python -m experiments.v3_m2_branch_parallelism.run --phase prepare
python -m experiments.v3_m2_branch_parallelism.run --phase smoke --workers 3
python -m experiments.v3_m2_branch_parallelism.run --phase explore --case C1_single --seed 0 --workers 4
python -m experiments.v3_m2_branch_parallelism.run --phase explore --case C1_multi --seed 0 --workers 3
python -m experiments.v3_m2_branch_parallelism.run --phase formal --case C1_single --load 700 --seed 1 --seed 2 --seed 3 --workers 4
python -m experiments.v3_m2_branch_parallelism.run --phase formal --case C1_multi --load 320 --seed 1 --seed 2 --seed 3 --workers 3
python -m experiments.v3_m2_branch_parallelism.run --phase formal --case C1_single --load 600 --seed 4 --seed 5 --seed 6 --workers 3
python -m experiments.v3_m2_branch_parallelism.subsets --workers 2
python -m experiments.v3_m2_branch_parallelism.transfer --workers 2
python -m experiments.v3_m2_branch_parallelism.report
python -m experiments.v3_m2_branch_parallelism.audit
python -m experiments.v3_m2_branch_parallelism.plot
```

Existing output files are reused only when identity hashes match. A window
that hits the simulator's `Exceed KV-cache capacity!` assertion is recorded
as a failure log, not as a zero-throughput sample. The `formal_index.json`
file is a live progress index and may be overwritten when separate case
commands run concurrently; `report.py` audits the raw run files directly.

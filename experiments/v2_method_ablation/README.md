# V2 whole-method ablation

This experiment leaves `rcaps_v2`, its two official layouts, and previous
formal records unchanged. The two new controls are registered as ablations,
so the default benchmark still runs only V2 and Helix.

| Comparison | Conditional question | Control |
| --- | --- | --- |
| V2 vs `rcaps_v2_capacity_only` | Does the complete resource-aware placement procedure matter when adaptive structure and online scheduling remain? | The same 1–4 A100 shared-stem, 2/3-suffix feasible family and 4-per-family shortlist/16-step local search use only GPU layer capacity and physical-link existence. Device order is capacity-first; layer assignment balances occupied capacity; ranking minimizes maximum occupancy and then sum of squared occupancies. Compute service profiles, link latency/bandwidth, and event-DAG scores are unavailable during selection. |
| V2 vs `rcaps_v2_fixed_structure` | Does adaptive shared/replicated structure matter with the V2 placement evaluator and scheduler? | Existing one-A100, 12-layer shared stem and two-suffix V2 search. |
| V2 vs `rcaps_v2_static_routes` | Does the whole online scheduling method matter on the same V2 placement? | Rotate equally among the three canonical legal routes at prompt admission, fix that route for Decode, and transmit ready requests individually. No live resource-state path cost or Decode transfer coalescing. |

Each effect is conditional on the two methods that remain enabled. M1 can
change the chosen shared/replicated structure, and M3 removes routing and
coalescing together. These comparisons cannot identify the independent effect
of any internal component or be added together.

For an advisor-facing view with only three-seed aggregate values, see
`MENTOR_BRIEF_CN.md`. `REPORT_CN.md` retains per-seed audit details.

## Incremental ladder

The advisor's build-up comparison adds two controls while keeping V2 frozen:

| Stage | Placement | Online scheduler |
| --- | --- | --- |
| Base | Capacity-only search, constrained to one A100 shared stem, 12 shared layers and two suffixes | Capacity-safe static legal-path rotation and per-request transfers |
| A | Existing V2 resource-aware **fixed-structure** layout | Same capacity-safe static scheduler |
| A+B | Existing V2 adaptive layout | Same capacity-safe static scheduler |
| A+B+C | Existing V2 adaptive layout | Original V2 dynamic scheduler |

The base and A stages share the fixed structural family, and A+B and A+B+C
share byte-identical layout files. The static scheduler uses deterministic
round-robin paths and never reads GPU or link backlog for path selection. A
hard admission guard reserves each admitted query's trace-defined target KV tokens
to avoid simulator capacity assertions under sustained overload. The guard
can defer prompts but never changes their round-robin path. It is shared by
the first three stages. In all six formal A+B windows it fired zero times;
query samples, routes, resource waits and core metrics were identical to the
previous unguarded static-path runs, so the observed C-stage difference is
unaffected by admission decisions.
The simulator exposes the target output length to this experiment; real online
serving would need a declared maximum or another reservation bound. The large
single-cluster latency differences for the first two stages are conditional
on this conservative admission mechanism.
The earlier leave-one-out controls remain separate and are not substituted
for any ladder stage. An unguarded fixed-structure attempt failed at the
simulator's KV capacity assertion; its logs are retained in
`attempts_pre_kv_guard/` and its partial windows are excluded.

```powershell
python -m experiments.v2_method_ablation.capacity_only --scenario single --variant fixed --output-dir experiments/v2_method_ablation/layouts/single_fixed_capacity
python -m experiments.v2_method_ablation.capacity_only --scenario multi --variant fixed --output-dir experiments/v2_method_ablation/layouts/multi_fixed_capacity
python -m experiments.v2_method_ablation.run_incremental --workers 4
python -m experiments.v2_method_ablation.incremental_report
```

`incremental_report.py` checks each layout and result hash, fixed-structure
conditions, formal protocol, trace identity, and every request ID before
writing `incremental_summary.json` and `INCREMENTAL_REPORT_CN.md`. Absolute
metrics and adjacent paired changes are summarized as mean ± sample standard
deviation across three seeds. The JSON retains per-seed values and per-run log
hashes for audit.

## Reproduce

From the repository root:

```powershell
python -m experiments.v2_method_ablation.capacity_only --scenario single --output-dir experiments/v2_method_ablation/layouts/single
python -m experiments.v2_method_ablation.capacity_only --scenario multi --output-dir experiments/v2_method_ablation/layouts/multi
python -m experiments.v2_method_ablation.report --prepare
python -m benchmarks.run --methods rcaps_v2_capacity_only rcaps_v2_static_routes --scenarios single multi --seeds 0 1 2 --duration 1800 --warmup 0 --workers 2 --results-dir experiments/v2_method_ablation/runs
python -m experiments.v2_method_ablation.report --report
```

`--prepare` checks current layout hashes, physical feasibility, protocol,
trace hash and paired request identities before copying the 18 existing formal
V2, Helix and fixed-structure records. `reuse_manifest.json` records their
sources and byte hashes. The new full-window runs write separate JSON records
and per-run logs. `--report` refuses mismatched layouts or traces; failed runs
must be fixed and rerun rather than supplied with partial-window metrics.

Formal results use 70B, the two original 24-GPU topologies, offered loads 700
and 320 token/s, seeds 0/1/2, a 1800-second window with zero warmup and no
tail drain. Seeds 100/101 are reserved for development checks. Seed 1 was used
in earlier development, so the three formal seeds describe paired variation
and do not establish statistical significance or real-cluster performance.

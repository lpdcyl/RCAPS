# RCAPS V2 whole-method replacement comparisons

This experiment implements three complete alternative methods around the
unchanged V2 system. The design and interpretation limits are in
`PROTOCOL_CN.md`. Existing fine-grained and additive-ladder experiments remain
separate.

From the repository root:

```powershell
python -m experiments.v2_method_comparisons.placement --scenario single --variant static_resource
python -m experiments.v2_method_comparisons.placement --scenario multi --variant static_resource
python -m experiments.v2_method_comparisons.placement --scenario single --variant beam_search
python -m experiments.v2_method_comparisons.placement --scenario multi --variant beam_search
python -m benchmarks.run --methods rcaps_v2_static_resource_model rcaps_v2_beam_placement rcaps_v2_live_pipeline --scenarios single multi --seeds 100 101 --duration 60 --warmup 0 --workers 2 --results-dir experiments/v2_method_comparisons/smoke
python -m benchmarks.run --methods rcaps_v2_static_resource_model rcaps_v2_beam_placement rcaps_v2_live_pipeline --scenarios single multi --seeds 100 101 --duration 300 --warmup 0 --workers 2 --results-dir experiments/v2_method_comparisons/stress
python -m benchmarks.run --methods rcaps_v2_static_resource_model rcaps_v2_beam_placement rcaps_v2_live_pipeline --scenarios single multi --seeds 0 1 2 --duration 1800 --warmup 0 --workers 2 --results-dir experiments/v2_method_comparisons/runs
python -m experiments.v2_method_comparisons.report
```

`benchmarks.run` writes individual logs and result JSON files and skips
matching complete results on repeat runs. The report audits each available
formal window, matching the physical layout, exact trace, request IDs, and
protocol before computing paired metrics. A failed window retains its log and
has no imputed metrics. The prior simple alternatives and original V2 records
come from `experiments/v2_method_ablation/runs/`, after the same audit.

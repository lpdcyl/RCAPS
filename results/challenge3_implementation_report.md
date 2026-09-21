# Challenge 3 implementation report

## Files added

- `src/carbon/trace.py`: deterministic piecewise-constant CSV CI provider.
- `src/scheduler/carbon_flow_scheduler.py`: interval-level dynamic flow
  scheduler using the existing carbon flow solver.
- `src/scheduler/request_dispatcher.py`: deterministic quota-to-request
  dispatcher with explicit quota accounting.
- `src/scheduler/slow_placement.py`: optional slow CBGP controller with
  structural evidence, persistence, and minimum dwell checks.
- `src/scheduler/config.py`: frozen Challenge 3 YAML loader and validation.
- `tests/test_challenge3.py`: trace boundary, scheduler, quota, and capacity
  invariants.
- `experiments/exp_challenge3.py`: formal 135-point study and summaries.
- `experiments/challenge3_figures/`: reproducible paper-style PDF/preview
  figure scripts.

## Solver compatibility change

The existing placement MILP API now accepts optional `mip_rel_gap` and
`time_limit_seconds` arguments. Their defaults remain exact and unlimited, so
all earlier callers and historical experiments retain their behavior. Only the
Challenge 3 bounded comparator supplies the optional values.

## Verification status

The final test suite contains 75 passing tests. Phase 3.5 and Challenge 2
regressions were re-executed after the implementation and matched their formal
scientific outputs. No source, test, configuration, or result file from
Challenge 1 or Challenge 2 was edited.

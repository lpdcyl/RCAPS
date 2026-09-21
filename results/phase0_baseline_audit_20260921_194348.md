# Phase 0 Baseline Audit

Audit time: 2026-09-21 19:43:48 +08:00

This is a new audit artifact. No Phase 3 or Phase 3.5 result was overwritten.

## 1. 本阶段目标

Audit the current repository before any Stage-aware Carbon Modeling, CBGP, or
request-dispatch implementation. Verify the existing module relationships,
test baseline, Phase 3.5 artifacts, saved numerical invariants, and placement
boundary classifications.

No Phase 1/2/3 implementation from the new plan was started.

## 2. 实际修改文件

- Added `results/phase0_baseline_audit_20260921_194348.md`.
- No source, configuration, test, or historical Phase 3/3.5 result was changed.

## 3. 当前模块结构与调用关系

Current source packages:

- `src/utils`: YAML loading and bandwidth/unit conversion.
- `src/graph`: physical topology, layer placement, and logical serving graph.
- `src/simulator`: configuration-driven construction and Phase 1 validation.
- `src/optimizer/maxflow.py`: validated maximum-flow/min-cut baseline.
- `src/carbon/model.py`: configured compute-energy and per-GPU carbon costs.
- `src/optimizer/carbon_flow.py`: fixed-placement carbon-aware flow LP and
  Region/cross-Region flow metrics.
- `src/optimizer/placement_milp.py`: throughput-optimal Helix placement and
  joint Placement+Routing carbon Oracle.
- `src/analysis`: Routing Gap, signature breakpoints, and three-point fixed-cost
  placement-boundary validation.
- `experiments/phase3_common.py` and `experiments/phase35_common.py`: shared
  configuration and experiment orchestration.
- `experiments/exp_phase35.py`: staged rho, GPU, network, and energy sensitivity.

Observed call direction:

```text
YAML config -> simulation/topology/model objects -> serving graph
            -> max-flow or fixed-placement carbon-flow LP
            -> throughput/carbon placement MILP
            -> breakpoint/gap analysis -> experiment CSV/figures
```

There is currently no `src/scheduler`, CI trace abstraction, bottleneck
diagnostic, placement-candidate generator, or CBGP implementation. That is
consistent with stopping at Phase 0.

## 4. 运行命令

```powershell
python -m pytest -q
python --version
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pytest -q
```

The audit also read the README, every YAML configuration's top-level structure,
the public definitions/import relationships under `src`, `experiments`, and
`tests`, and independently recomputed the Phase 3.5 CSV invariants.

## 5. 测试结果

- System interpreter: Python 3.10.16.
- Result: **49 passed in 9.51s**.
- Project metadata requires Python 3.11 or newer.
- Repository `.venv`: Python 3.12.14, but `pytest` is not installed there.
- `.venv\Scripts\python.exe -m pytest -q` therefore stops with
  `No module named pytest`; this is an environment setup failure, not a failing
  test assertion.

## 6. Phase 3.5 文件与复算结果

The four expected files all exist:

- `results/phase35_report.md`
- `results/phase35_summary.csv`
- `results/phase35_validated_boundaries.csv`
- `configs/phase35_sensitivity.yaml`

Independent checks on `phase35_summary.csv`:

- 930 rows; all required Phase 3.5 columns present; zero null cells.
- `joint_carbon <= routing_carbon + 1e-10` at every point.
- Maximum `joint_carbon - routing_carbon`: 0.
- Recomputed Gap maximum absolute error: `5.55e-15`.
- Recomputed `F_target - rho * F_H` maximum absolute error: 0.
- Routing and joint Region-share sum maximum error: `1.11e-16`.
- The 1%, 3%, and 5% Routing-sufficiency flags all match their thresholds.
- Symmetric rho-0.95 control: 31 points, `F_H=164`, `F_target=155.8`, maximum
  Gap `0.424355%`.
- Global maximum Gap: `18.390738%`, `high_asymmetric`, rho 0.95, cross-Region
  capacity 20 token/s (2.56 Mbps), CI ratio 4.0, scenario-specific `F_H=136`
  and `F_target=129.2`.

Independent checks on `phase35_validated_boundaries.csv`:

- 309 rows; all required boundary columns present; zero null cells.
- Every serialized old/new signature parses and actually changes.
- `delta_left * delta_right < 0` reproduces all saved `cost_crossing` values.
- Endpoint relative differences below `1e-4` reproduce all saved `degenerate`
  values.
- `cost_crossing and not degenerate` reproduces every saved validated boundary.
- Counts: 45 raw crossings, 42 validated non-degenerate boundaries, 248
  degenerate/equivalent switches.

Audited artifact SHA-256 values:

- `phase35_summary.csv`:
  `a3b54ecb7d94b261dbe738d46e47aea7dd6f4ec1dc6ab61b6745e3fbc2de5c70`
- `phase35_validated_boundaries.csv`:
  `34a3718a833e32a0dfb8a9562a5a57e6d339a8e4381137cfb51c9ab6692b2af8`
- `phase35_report.md`:
  `0b5a4be91ab0088a520ab3f6bc0e6ca0f1a179dc51bd7718eaaf222c80c0ea1f`
- `phase35_sensitivity.yaml`:
  `b12b31ae3cfc5044a11bb086044eae0ce30f69becc7589e52e7b1e8e18937ce1`

No Windows absolute-path literal was found in README, Python, YAML, test, or
Phase 3.5 report files.

## 7. 与计划不一致的地方及原因

The expected Phase 3.5 files and numerical record match the repository. No
Phase 3.5 result discrepancy was found.

The only material mismatch is the execution environment: the interpreter with
installed test dependencies is Python 3.10.16, below the declared Python 3.11
minimum, while the supported Python 3.12 project virtual environment has not
had `requirements.txt` installed. The audit did not mutate the environment
because this phase authorizes inspection and reporting only.

No Git metadata is present in `carbon-helix-sim` or its workspace parent, so a
commit-level version/diff comparison is unavailable. File presence, timestamps,
content, numerical recomputation, and SHA-256 values were used instead.

## 8. 下一阶段是否满足进入条件

**Conditionally not yet.** The code and saved Phase 3.5 results pass all audited
invariants, but the regression suite should first be reproduced in the declared
supported environment. Minimal environment fix:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

After that supported-interpreter run passes, the baseline is ready for
Challenge 1. Per the instruction, work stops here pending explicit confirmation.

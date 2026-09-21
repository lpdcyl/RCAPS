# Phase 0.5 Environment Validation

Validation date: 2026-09-21 (Asia/Shanghai)

## Scope

This validation only confirms the runnable dependency environment and baseline
regression. No source, experiment, configuration, test, or historical Phase 3
or Phase 3.5 result was modified. Phase 1 work was not started.

## Commands executed

The original project-venv commands were attempted first:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The `.venv` interpreter is Python 3.12.14, but direct PyPI TCP connectivity was
unavailable and the installation could not complete. The user then explicitly
allowed use of any runnable environment and identified the existing `gllm`
Conda environment. The equivalent validation commands were:

```powershell
conda activate gllm
python --version
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -q
git status --short
```

The commands were executed through the environment's Python executable, which
is equivalent to activating `gllm` for these non-interactive commands.

## Python and project dependencies

- Environment: Conda `gllm`
- Python: 3.10.20
- pip: 26.0.1
- `pip install -r requirements.txt`: successful, exit code 0
- All project requirements were already installed and satisfy the declared
  package-version ranges:
  - networkx 3.4.2
  - PyYAML 6.0.3
  - pandas 2.3.3
  - scipy 1.15.3
  - matplotlib 3.10.9
  - pytest 9.0.3

`pip check` reports pre-existing conflicts for the unrelated `xuance` package
against NumPy, OpenCV, and SciPy. Per explicit user direction, `xuance` is out
of scope and was neither used nor changed. No conflict exists among the direct
dependencies declared by this project.

## Baseline regression

Final command result:

```text
.................................................                        [100%]
49 passed in 9.65s
```

- Collected tests: 49
- Passed: 49
- Failed: 0
- Skipped: 0
- Pytest warnings: 0

## Repository status

`git status --short` reports that this directory and its parents contain no Git
metadata. A Git working-tree status is therefore unavailable.

## Source and result integrity

- No file under `src/`, `experiments/`, `configs/`, or `tests/` was changed.
- No Phase 3 or Phase 3.5 historical result was changed.
- The only artifact added in Phase 0.5 is this validation report.
- Stage-aware Carbon Modeling, CBGP, scheduler, CI trace, migration, and
  hysteresis were not started.

## Decision

**Phase 0 is formally complete. The project is allowed to enter Phase 1.**

Execution stops after this report as required.

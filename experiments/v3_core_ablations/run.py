"""Run the frozen C1 V3 2×2 ablation without touching released results.

Usage: python -m experiments.v3_core_ablations.run --phase audit|smoke|formal|low
Formal runs A/B. C/D are audited for reuse; C is rerun only on audit failure.
"""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.analysis import path_use
from experiments.m2_multistage_candidate.placement import digest, validate
from experiments.m2_multistage_candidate.prepare import files
from rcaps.placement.topology import TopologyModel
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler

from .adapters import StaticGraphDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CANDIDATE = ROOT / "experiments/m2_multistage_candidate"
CASES = ("C1_single", "C1_multi")
CELLS = {"A": ("single_any", "static"), "B": ("multi_any", "static"),
         "C": ("single_any", "live"), "D": ("multi_any", "live")}
LOADS = {"high": {"C1_single": 700.0, "C1_multi": 320.0},
         "low": {"C1_single": 350.0, "C1_multi": 160.0}}
RUNTIME_FILES = ("rcaps/v3/resource_graph.py", "rcaps/v3/scheduler.py",
                 "rcaps/scheduling/routing_dag.py",
                 "rcaps/scheduling/scheduler_queue_cost.py",
                 "rcaps/scheduling/scheduler_final.py", "benchmarks/fixed_window.py")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    part.replace(path)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _layout(case: str, cell: str) -> Path:
    variant, _ = CELLS[cell]
    return CANDIDATE / "layouts" / case / variant


def _source(phase: str, case: str, cell: str, seed: int) -> Path:
    return HERE / "runs" / phase / case / f"seed{seed}" / f"{cell}.json"


def _runtime_hash() -> dict:
    return {name: digest(ROOT / name) for name in RUNTIME_FILES}


def audit() -> dict:
    offline = _read(CANDIDATE / "offline_audit.json")
    manifest = _read(ROOT / "experiments/v3_release/manifest.json")
    for name, expected in manifest["code_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Released V3 code differs from manifest: {name}")
    result = {"runtime_sha256": _runtime_hash(), "cases": {}}
    for case in CASES:
        physical, _, topology = files(case)
        model = TopologyModel(physical)
        result["cases"][case] = {"physical": _relative(physical),
                                 "physical_sha256": digest(physical), "layouts": {}}
        assert digest(physical) == offline[case]["physical_sha256"]
        for variant in ("single_any", "multi_any"):
            layout = CANDIDATE / "layouts" / case / variant
            record = _read(layout / "placement.json")
            checked = validate(model, record["state"])
            from experiments.m2_multistage_candidate.prepare import _audit_export
            exported = _audit_export(layout, checked)
            expected = offline[case]["variants"][variant]
            assert digest(layout / "solution.ini") == expected["solution_sha256"]
            assert digest(layout / "simulator_cluster.ini") == expected["sim_cluster_sha256"]
            assert checked["dag"].path_count() > 0
            result["cases"][case]["layouts"][variant] = {
                "solution_sha256": expected["solution_sha256"],
                "sim_cluster_sha256": expected["sim_cluster_sha256"],
                "structure": {key: expected[key] for key in ("widths", "boundaries",
                    "layer_copies", "active_gpus", "idle_gpus", "candidate_evaluations",
                    "search_wall_s", "compatible_paths")},
                "dag_edges": exported["exported_edges"],
                "complete_paths": checked["dag"].path_count()}
        v3 = manifest["layouts"][topology]
        assert v3["solution_sha256"] == result["cases"][case]["layouts"]["multi_any"]["solution_sha256"]
        assert v3["sim_cluster_sha256"] == result["cases"][case]["layouts"]["multi_any"]["sim_cluster_sha256"]
    _write(HERE / "audit.json", result)
    return result


def _run_one(phase: str, case: str, cell: str, seed: int) -> str:
    duration = 60 if phase == "smoke" else 1800
    load = "low" if phase == "low" else "high"
    variant, routing = CELLS[cell]
    layout = _layout(case, cell)
    output = _source(phase, case, cell, seed)
    physical, _, topology = files(case)
    identity = {"case": case, "cell": cell, "variant": variant, "routing": routing,
                "scenario": topology, "seed": seed, "duration_s": duration,
                "warmup_s": 0, "offered_tokens_per_s": LOADS[load][case],
                "physical_sha256": digest(physical),
                "solution_sha256": digest(layout / "solution.ini"),
                "sim_cluster_sha256": digest(layout / "simulator_cluster.ini"),
                "runtime_sha256": _runtime_hash(),
                "static_adapter_sha256": digest(HERE / "adapters.py") if routing == "static" else None,
                "evaluation_protocol": "fixed_window_no_tail_drain"}
    if output.exists():
        row = _read(output)
        if all(row.get(key) == value for key, value in identity.items()) and \
                len(row.get("query_samples", {})) == row.get("arrivals"):
            return _relative(output)
        raise ValueError(f"Existing result identity mismatch: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            redirect_stdout(log), redirect_stderr(log):
        try:
            model = TopologyModel(physical)
            row = fixed_window_run(
                topology, "queue_dag", LOADS[load][case], duration, 0, seed,
                layout / "solution.ini", layout / "simulator_cluster.ini",
                profile_resources=phase != "smoke",
                scheduler_factory=(StaticGraphDagScheduler if routing == "static"
                                   else GraphModeledQueueAwareDagScheduler),
                compact=True, record_query_samples=True,
                physical_cluster=physical, machine_counts=model.machine_counts)
            row.update(identity)
            row["query_samples_schema"] = 1
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Missing request-level samples")
            row["path_use_audit"] = path_use(case, variant, row)
            _write(output, row)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return _relative(output)


def _historical(case: str, cell: str, seed: int, phase: str) -> tuple[Path, str]:
    variant, _ = CELLS[cell]
    if cell == "D" and phase == "formal":
        path = ROOT / "benchmarks/runs" / case.removeprefix("C1_") / f"seed{seed}" / "rcaps_v3.json"
        index = _read(ROOT / "experiments/v3_release/formal_reuse_index.json")
        entry = next(item for item in index if item["scenario"] == case.removeprefix("C1_") and item["seed"] == seed)
        return path, entry["released_sha256"]
    candidate_phase = "smoke" if phase == "smoke" else "formal"
    entry = _read(CANDIDATE / f"{candidate_phase}_index.json")[case][variant]["sources"][str(seed)]
    return ROOT / entry["source"], entry["sha256"]


def _audit_reuse(case: str, cell: str, seed: int, phase: str) -> dict:
    path, expected_hash = _historical(case, cell, seed, phase)
    if digest(path) != expected_hash:
        raise ValueError(f"Historical raw hash mismatch: {path}")
    row = _read(path)
    variant, _ = CELLS[cell]
    layout = _layout(case, cell)
    physical, _, topology = files(case)
    duration = 60 if phase == "smoke" else 1800
    expected = {"scenario": topology, "seed": seed, "offered_tokens_per_s": LOADS["high"][case],
                "duration_s": duration, "warmup_s": 0,
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "physical_sha256": digest(physical),
                "solution_sha256": digest(layout / "solution.ini"),
                "sim_cluster_sha256": digest(layout / "simulator_cluster.ini"),
                "query_samples_schema": 1}
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"Historical record differs on {key}: {path}")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"Historical samples incomplete: {path}")
    if phase == "formal":
        from experiments.m2_multistage_candidate.run import execution_sha256
        candidate_entry = _read(CANDIDATE / "formal_index.json")[case][variant]["sources"][str(seed)]
        candidate = ROOT / candidate_entry["source"]
        if digest(candidate) != candidate_entry["sha256"]:
            raise ValueError(f"Candidate result hash changed: {candidate}")
        past = _read(candidate)
        if past.get("execution_sha256") != execution_sha256():
            raise ValueError(f"Candidate execution code differs: {candidate}")
        for key in MATCH_FIELDS:
            if row.get(key) != past.get(key):
                raise ValueError(f"Released V3 protocol differs: {key}")
        common_cohort(row, past)
        for key in ("output_throughput_tokens_per_s", "ttft_p95_s",
                    "tpot_p95_s", "completion_fraction", "backlog_at_window_end",
                    "route_counts", "query_samples"):
            if row.get(key) != past.get(key):
                raise ValueError(f"Reused execution differs: {key}")
    return {"source": _relative(path), "sha256": expected_hash,
            "trace_sha256": row["trace_sha256"], "reused": True}


def _smoke_parity(case: str, cell: str) -> dict:
    new = _read(_source("smoke", case, cell, 100))
    old_path, _ = _historical(case, cell, 100, "smoke")
    old = _read(old_path)
    for key in MATCH_FIELDS:
        if new.get(key) != old.get(key):
            raise ValueError(f"Smoke protocol mismatch: {case}/{cell}/{key}")
    common_cohort(new, old)
    keys = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
            "completion_fraction", "backlog_at_window_end", "route_counts")
    different = [key for key in keys if new.get(key) != old.get(key)]
    return {"same_execution": not different, "different_fields": different,
            "new": _relative(_source("smoke", case, cell, 100)),
            "historical": _relative(old_path)}


def _jobs(phase: str, workers: int) -> dict:
    audit()
    result = {"phase": phase, "jobs": {}, "failures": {}}
    if phase == "smoke":
        spec = [(case, cell, 100) for case in CASES for cell in ("A", "B", "C")]
    elif phase == "formal":
        smoke = _read(HERE / "smoke_index.json")
        if any(item.get("status") != "passed" for item in smoke["jobs"].values()):
            raise ValueError("Smoke gate has failures")
        spec = [(case, cell, seed) for case in CASES for cell in ("A", "B") for seed in (0, 1, 2)]
        # A failed C parity requires a new C result. D must pass release audit.
        for case in CASES:
            if not smoke["reuse_parity"][case]["C"]["same_execution"]:
                spec.extend((case, "C", seed) for seed in (0, 1, 2))
    else:
        formal = _read(HERE / "formal_index.json")
        if not any(key.endswith("/A") or key.endswith("/B") for key in formal["failures"]):
            raise ValueError("Low-load fallback requires a high-load static failure")
        spec = [(case, cell, seed) for case in CASES for cell in CELLS for seed in (0, 1, 2)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(_run_one, phase, *item): item for item in spec}
        for future in as_completed(tasks):
            case, cell, seed = tasks[future]
            key = f"{case}/{cell}/seed{seed}"
            try:
                source = ROOT / future.result()
                result["jobs"][key] = {"status": "passed", "source": _relative(source),
                                       "sha256": digest(source),
                                       "trace_sha256": _read(source)["trace_sha256"]}
                print("PASS", key, flush=True)
            except Exception as exc:
                result["jobs"][key] = {"status": "failed", "error": repr(exc)}
                result["failures"][f"{case}/{cell}"] = repr(exc)
                print("FAIL", key, repr(exc), flush=True)
            _write(HERE / f"{phase}_index.json", result)
    if phase == "smoke":
        result["reuse_parity"] = {}
        for case in CASES:
            result["reuse_parity"][case] = {"C": _smoke_parity(case, "C")}
        _write(HERE / "smoke_index.json", result)
    if phase == "formal":
        result["reuse"] = {}
        for case in CASES:
            for cell in ("C", "D"):
                for seed in (0, 1, 2):
                    key = f"{case}/{cell}/seed{seed}"
                    if key in result["jobs"]:
                        continue
                    try:
                        result["reuse"][key] = _audit_reuse(case, cell, seed, "formal")
                    except Exception as exc:
                        result["failures"][f"{case}/{cell}"] = repr(exc)
                        print("REUSE FAIL", key, repr(exc), flush=True)
        _write(HERE / "formal_index.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("audit", "smoke", "formal", "low"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "audit":
        print(json.dumps(audit(), indent=2))
    else:
        print(json.dumps(_jobs(args.phase, args.workers)["failures"], indent=2))


if __name__ == "__main__":
    main()

"""Export and evaluate nested single-boundary replica layouts.

Run from the repository root with ``python -m experiments.v3_m2_branch_parallelism.run``.
The primary comparison uses canonical paths, leaving M3's live route price intact.
"""

from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.prepare import _audit_export, files
from experiments.v3_pathspace_ablation.run import (
    CanonicalGraphDagScheduler, canonical_edges,
)
from rcaps.v3.placement import (
    digest, normalize, objective, save, signature, validate,
)
from rcaps.v3.resource_graph import LayerCompatibilityDag
from rcaps.v3.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = ("C1_single", "C1_multi")
EXPLORE_LOADS = {"C1_single": (350., 700., 1100.),
                 "C1_multi": (160., 320., 500.)}
SEEDS = (0, 1, 2)
RUNTIME = ("rcaps/v3/placement.py", "rcaps/v3/resource_graph.py",
           "rcaps/v3/scheduler.py", "rcaps/v3/routing.py",
           "rcaps/v3/queue_cost.py", "rcaps/v3/online_scheduler.py",
           "benchmarks/fixed_window.py",
           "experiments/v3_pathspace_ablation/run.py")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parent(case: str) -> dict:
    destination = HERE / "parents" / f"{case}.json"
    if destination.exists():
        return read(destination)
    if case == "C1_multi":
        source = ROOT / "rcaps/v3_layouts/multi/placement.json"
        state = normalize(read(source)["state"])
        selection = {"source": relative(source), "source_sha256": digest(source),
                     "selection": "frozen V3 single-boundary layout"}
    else:
        source = ROOT / "experiments/v3_method_validation/m2_candidates/C1_single/full.json"
        bank = read(source)
        candidates = []
        for item in bank["candidates"].values():
            state = normalize(item["state"])
            segments = state["segments"]
            if (len(segments) == 2 and segments[0]["end"] == 48 and
                    [len(s["replicas"]) for s in segments] == [1, 3] and
                    segments[0]["replicas"][0] == [6, 9, 10, 17] and
                    len(state["lengths"]) == 24):
                candidates.append((objective(item["metrics"], bank["reference"]),
                                   signature(state), state))
        if not candidates:
            raise ValueError("No matching C1_single single-boundary parent")
        score, _, state = min(candidates)
        selection = {"source": relative(source), "source_sha256": digest(source),
                     "selection": "minimum frozen static objective, signature tie break",
                     "static_score": score, "eligible_candidates": len(candidates)}
    record = {"case": case, "state": state, **selection}
    write(destination, record)
    return record


def select(state: dict, branches: tuple[int, ...]) -> dict:
    selected = normalize(state)
    suffix = selected["segments"][1]
    suffix["replicas"] = [suffix["replicas"][index] for index in branches]
    used = set(selected["segments"][0]["replicas"][0])
    used.update(node for replica in suffix["replicas"] for node in replica)
    selected["lengths"] = {node: n for node, n in selected["lengths"].items()
                           if node in used}
    return selected


def variants(case: str) -> dict[str, dict]:
    state = parent(case)["state"]
    result = {f"k{k}": select(state, tuple(range(k))) for k in (1, 2, 3)}
    if case == "C1_single":
        equal = ROOT / "experiments/m2_multistage_candidate/layouts/C1_single/single_any/placement.json"
        result["equal_gpu_k2"] = normalize(read(equal)["state"])
    return result


def prepare() -> dict:
    plan = {"protocol": "fixed_window_no_tail_drain", "boundary_layer": 48,
            "selection_frozen_before_simulation": True,
            "runtime_sha256": {name: digest(ROOT / name) for name in RUNTIME},
            "runner_sha256": digest(HERE / "run.py"), "cases": {}}
    for case in CASES:
        physical, template, scenario = files(case)
        model = TopologyModel(physical)
        parent_record = parent(case)
        case_record = {"scenario": scenario, "physical": relative(physical),
                       "physical_sha256": digest(physical),
                       "template_sha256": digest(template),
                       "parent": parent_record, "variants": {}}
        for label, state in variants(case).items():
            checked = validate(model, state)
            if len(state["segments"]) != 2 or state["segments"][0]["end"] != 48:
                raise ValueError(f"Wrong boundary: {case}/{label}")
            destination = HERE / "layouts" / case / label
            metadata = {"experiment": "M2 branch parallelism", "case": case,
                        "variant": label, "parent_signature": signature(parent_record["state"])}
            export = save(model, template, state, destination, metadata)
            _audit_export(destination, checked)
            allowed = canonical_edges(state, checked["dag"])
            reduced = LayerCompatibilityDag(checked["dag"].spans,
                                            tuple(allowed), checked["dag"].layers)
            expected_paths = len(state["segments"][1]["replicas"])
            if reduced.path_count() != expected_paths:
                raise ValueError(f"Canonical paths != branch count: {case}/{label}")
            case_record["variants"][label] = {
                "state_signature": signature(state),
                "solution_sha256": export["solution_sha256"],
                "sim_cluster_sha256": export["sim_cluster_sha256"],
                "active_gpus": export["active_gpus"],
                "layer_copies": export["layer_copies"],
                "canonical_paths": reduced.path_count(),
                "full_dag_paths": checked["dag"].path_count(),
                "branch_gpu_ids": state["segments"][1]["replicas"],
                "prefix_gpu_ids": state["segments"][0]["replicas"][0]}
        plan["cases"][case] = case_record
    write(HERE / "plan.json", plan)
    return plan


def run_one(case: str, label: str, load: float, seed: int, phase: str) -> str:
    plan = read(HERE / "plan.json")
    if digest(HERE / "run.py") != plan["runner_sha256"]:
        raise ValueError("Runner changed after plan freeze")
    info = plan["cases"][case]["variants"][label]
    physical, _, scenario = files(case)
    model = TopologyModel(physical)
    deployment = HERE / "layouts" / case / label
    if digest(deployment / "solution.ini") != info["solution_sha256"] or \
            digest(deployment / "simulator_cluster.ini") != info["sim_cluster_sha256"]:
        raise ValueError("Deployment changed after plan freeze")
    state = read(deployment / "placement.json")["state"]
    checked = validate(model, state)
    allowed = frozenset((a if isinstance(a, str) else a + 2,
                         b if isinstance(b, str) else b + 2)
                        for a, b in canonical_edges(state, checked["dag"]))
    duration = 60 if phase == "smoke" else 1800
    output = HERE / "runs" / phase / case / label / f"load{load:g}_seed{seed}.json"
    identity = {"case": case, "variant": label, "phase": phase,
                "offered_tokens_per_s": load, "seed": seed, "duration_s": duration,
                "solution_sha256": info["solution_sha256"],
                "sim_cluster_sha256": info["sim_cluster_sha256"],
                "runner_sha256": plan["runner_sha256"],
                "canonical_paths": info["canonical_paths"]}
    if output.exists():
        if all(read(output).get(k) == v for k, v in identity.items()):
            return relative(output)
        raise ValueError(f"Existing run identity changed: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", load, duration, 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=phase != "smoke", compact=True,
                record_query_samples=True, physical_cluster=physical,
                machine_counts=model.machine_counts,
                scheduler_factory=partial(CanonicalGraphDagScheduler,
                                          allowed_edges=allowed))
            row.update(identity)
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Incomplete request samples")
            if len(row["route_counts"]) > info["canonical_paths"]:
                raise ValueError("Unexpected cross-replica route")
            write(output, row)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return relative(output)


def run_phase(phase: str, workers: int, cases: tuple[str, ...],
              labels: tuple[str, ...], loads: tuple[float, ...],
              seeds: tuple[int, ...]) -> dict:
    plan = read(HERE / "plan.json")
    if phase != "smoke":
        smoke = read(HERE / "smoke_index.json")
        if smoke["failures"]:
            raise ValueError("Smoke gate failed")
    jobs = [(case, label, load, seed) for case in cases
            for label in labels if label in plan["cases"][case]["variants"]
            for load in loads for seed in seeds]
    result = {"phase": phase, "jobs": {}, "failures": {}}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, case, label, load, seed, phase):
                   (case, label, load, seed) for case, label, load, seed in jobs}
        for future in as_completed(futures):
            case, label, load, seed = futures[future]
            key = f"{case}/{label}/load{load:g}/seed{seed}"
            try:
                path = ROOT / future.result()
                row = read(path)
                result["jobs"][key] = {"source": relative(path),
                                       "sha256": digest(path),
                                       "trace_sha256": row["trace_sha256"],
                                       "status": "passed"}
                print("PASS", key, flush=True)
            except Exception as exc:
                result["failures"][key] = repr(exc)
                result["jobs"][key] = {"status": "failed", "error": repr(exc)}
                print("FAIL", key, repr(exc), flush=True)
            write(HERE / f"{phase}_index.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "smoke", "explore", "formal"),
                        required=True)
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--variant", action="append")
    parser.add_argument("--load", type=float, action="append")
    parser.add_argument("--seed", type=int, action="append")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.phase == "prepare":
        result = prepare()
        print(json.dumps({case: item["variants"] for case, item in result["cases"].items()},
                         indent=2))
        return
    cases = tuple(args.case or CASES)
    labels = tuple(args.variant or ("k1", "k2", "k3", "equal_gpu_k2"))
    if args.load:
        loads = tuple(args.load)
    elif args.phase == "smoke":
        loads = (700.,)
    else:
        if len(cases) != 1:
            raise ValueError("Use --case or explicit --load for multi-case run")
        loads = EXPLORE_LOADS[cases[0]]
    seeds = tuple(args.seed or ((100,) if args.phase == "smoke" else SEEDS))
    outcome = run_phase(args.phase, args.workers, cases, labels, loads, seeds)
    print(json.dumps({"passed": len(outcome["jobs"]) - len(outcome["failures"]),
                      "failures": outcome["failures"]}, indent=2))


if __name__ == "__main__":
    main()

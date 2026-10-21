"""Fixed-M3 online comparison of weighted- and LP-selected placements."""

from __future__ import annotations

import argparse
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from statistics import mean

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_joint_routing_candidate.joint import case_inputs
from rcaps.v3.placement import digest
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler

from .diagnose import CASES, HERE, ROOT, SEEDS, SOURCE


RUNS = HERE / "runs"
SENSITIVITY_INDEX = SOURCE / "formal_index.json"
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s",
           "tpot_p95_s", "completion_fraction", "backlog_at_window_end")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def selected(case: str, method: str) -> dict:
    plan = read(HERE / "selection_manifest.json")["cases"][case]
    label = plan[f"{method}_selected"]
    return next(row for row in plan["candidates"] if row["label"] == label)


def run_lp(case: str, offered: int, seed: int, duration: int) -> tuple[dict, Path]:
    row = selected(case, "linear")
    layout = ROOT / row["label"]
    model, physical, _ = case_inputs(case)
    destination = (RUNS / case / f"load{offered}" /
                   f"seed{seed}_{duration}s.json")
    identity = {"case": case, "layout": row["label"], "seed": seed,
                "offered_tokens_per_s": offered, "duration_s": duration,
                "solution_sha256": row["solution_sha256"],
                "sim_cluster_sha256": row["sim_cluster_sha256"],
                "physical_sha256": digest(physical),
                "scheduler_sha256": digest(ROOT / "rcaps/v3/scheduler.py"),
                "benchmark_sha256": digest(ROOT / "benchmarks/fixed_window.py")}
    if destination.exists():
        old = read(destination)
        if any(old.get(key) != value for key, value in identity.items()):
            raise ValueError(f"Existing result identity changed: {destination}")
        return old, destination
    if digest(layout / "solution.ini") != row["solution_sha256"] or \
            digest(layout / "simulator_cluster.ini") != row["sim_cluster_sha256"]:
        raise ValueError("Selected layout changed")
    started = time.perf_counter()
    try:
        result = fixed_window_run(
            "single" if case == "C1_single" else "multi", "queue_dag",
            offered, duration, 0, seed, layout / "solution.ini",
            layout / "simulator_cluster.ini", physical_cluster=physical,
            machine_counts=model.machine_counts,
            scheduler_factory=GraphModeledQueueAwareDagScheduler,
            compact=True, record_query_samples=True)
        if not result.get("route_counts") or result["arrivals"] != len(result["query_samples"]):
            raise ValueError("Missing route or request samples")
        result["status"] = "completed"
    except Exception as error:
        result = {"status": "failed", "error": repr(error),
                  "traceback": traceback.format_exc()}
    result.update(identity)
    result["wall_s"] = time.perf_counter() - started
    write(destination, result)
    return result, destination


def weighted_result(case: str, offered: int, seed: int) -> tuple[dict, Path]:
    row = selected(case, "weighted")
    jobs = read(SENSITIVITY_INDEX)["jobs"]
    matches = []
    for key, item in jobs.items():
        parts = key.split("/")
        if len(parts) != 4 or parts[0] != case or parts[2] != str(offered) or \
                parts[3] != f"seed{seed}":
            continue
        if (item["identity"]["solution_sha256"],
                item["identity"]["sim_cluster_sha256"]) != (
                row["solution_sha256"], row["sim_cluster_sha256"]):
            continue
        if item["status"] in ("passed", "reused"):
            matches.append(item)
    if not matches:
        raise ValueError(f"No frozen weighted result for {case}/{offered}/seed{seed}")
    item = matches[0]
    path = ROOT / item["source"]
    if digest(path) != item["sha256"]:
        raise ValueError(f"Frozen weighted result changed: {path}")
    result = read(path)
    if result["trace_sha256"] != item["trace_sha256"]:
        raise ValueError("Frozen trace identity changed")
    return result, path


def released_result(case: str, offered: int, seed: int) -> tuple[dict, Path]:
    item = read(SENSITIVITY_INDEX)["jobs"][
        f"{case}/beam64_budget500/{offered}/seed{seed}"]
    if item["status"] not in ("passed", "reused"):
        raise ValueError("Released V3 control is incomplete")
    path = ROOT / item["source"]
    if digest(path) != item["sha256"]:
        raise ValueError(f"Released V3 control changed: {path}")
    result = read(path)
    if result["trace_sha256"] != item["trace_sha256"]:
        raise ValueError("Released V3 trace identity changed")
    return result, path


def smoke() -> dict:
    rows = []
    for case, loads in CASES.items():
        offered = loads[-1]
        result, path = run_lp(case, offered, 100, 60)
        rows.append({"case": case, "offered": offered,
                     "status": result["status"],
                     "source": path.relative_to(ROOT).as_posix(),
                     "routes": len(result.get("route_counts", {})),
                     "error": result.get("error")})
    output = {"passed": all(row["status"] == "completed" and row["routes"] > 0
                            for row in rows), "rows": rows}
    write(HERE / "smoke_manifest.json", output)
    return output


def formal(workers: int = 4) -> dict:
    if not read(HERE / "smoke_manifest.json")["passed"]:
        raise ValueError("Smoke gate did not pass")
    if workers < 1:
        raise ValueError("At least one worker is required")
    jobs = [(case, offered, seed, 1800)
            for case, loads in CASES.items()
            for offered in loads for seed in SEEDS]
    # Check all historical controls before launching any new long windows.
    controls = {(case, offered, seed): weighted_result(case, offered, seed)
                for case, offered, seed, _ in jobs}
    outcomes = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_lp, *job): job for job in jobs}
        for future in as_completed(futures):
            case, offered, seed, _ = futures[future]
            outcomes[(case, offered, seed)] = future.result()
            print(f"completed {case}/{offered}/seed{seed}: "
                  f"{outcomes[(case, offered, seed)][0]['status']}", flush=True)
    rows = []
    for case, offered, seed, _ in jobs:
        lp, lp_path = outcomes[(case, offered, seed)]
        if lp["status"] != "completed":
            raise ValueError(f"LP-selected run failed: {lp_path}: {lp.get('error')}")
        old, old_path = controls[(case, offered, seed)]
        if lp["trace_sha256"] != old["trace_sha256"]:
            raise ValueError(f"Request traces differ: {case}/{offered}/seed{seed}")
        rows.append({"case": case, "offered": offered, "seed": seed,
                     "linear_source": lp_path.relative_to(ROOT).as_posix(),
                     "linear_sha256": digest(lp_path),
                     "weighted_source": old_path.relative_to(ROOT).as_posix(),
                     "weighted_sha256": digest(old_path),
                     "trace_sha256": lp["trace_sha256"],
                     "linear": {key: lp.get(key) for key in METRICS},
                     "weighted": {key: old.get(key) for key in METRICS}})
    output = {"status": "complete", "selection_manifest_sha256":
              digest(HERE / "selection_manifest.json"), "rows": rows}
    write(HERE / "formal_manifest.json", output)
    return output


def report() -> dict:
    data = read(HERE / "formal_manifest.json")
    if data["status"] != "complete":
        raise ValueError("Formal windows are incomplete")
    result = {"selection_manifest_sha256": data["selection_manifest_sha256"],
              "cases": {}}
    for case, loads in CASES.items():
        result["cases"][case] = {}
        for offered in loads:
            rows = [row for row in data["rows"]
                    if row["case"] == case and row["offered"] == offered]
            if len(rows) != len(SEEDS):
                raise ValueError("Missing formal seed")
            deltas = {metric: [row["linear"][metric] - row["weighted"][metric]
                               for row in rows] for metric in METRICS
                      if all(row["linear"][metric] is not None and
                             row["weighted"][metric] is not None for row in rows)}
            released = []
            for row in rows:
                control, _ = released_result(case, offered, row["seed"])
                if control["trace_sha256"] != row["trace_sha256"]:
                    raise ValueError("Released V3 and LP request traces differ")
                released.append(control)
            result["cases"][case][str(offered)] = {
                "seeds": [row["seed"] for row in rows],
                "weighted_mean": {metric: mean(row["weighted"][metric] for row in rows)
                                  for metric in deltas},
                "linear_mean": {metric: mean(row["linear"][metric] for row in rows)
                                for metric in deltas},
                "released_v3_mean": {
                    metric: mean(control[metric] for control in released)
                    for metric in deltas},
                "paired_deltas_linear_minus_weighted": {
                    metric: {"mean": mean(values), "by_seed": values}
                    for metric, values in deltas.items()},
                "paired_deltas_linear_minus_released_v3": {
                    metric: {"mean": mean(row["linear"][metric] - control[metric]
                                    for row, control in zip(rows, released)),
                             "by_seed": [row["linear"][metric] - control[metric]
                                         for row, control in zip(rows, released)]}
                    for metric in deltas}}
    write(HERE / "selection_results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("smoke", "formal", "report"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    output = {"smoke": smoke, "formal": lambda: formal(args.workers),
              "report": report}[args.phase]()
    if args.phase == "report":
        for case, loads in output["cases"].items():
            for offered, row in loads.items():
                print(case, offered,
                      {key: round(value["mean"], 4) for key, value in
                       row["paired_deltas_linear_minus_weighted"].items()})
    else:
        print(args.phase, output.get("passed", output.get("status")))

"""Independent M2 capacity / M3 live-route co-design experiment.

M1 stays a legality graph. M2 compares capacity-feasible placements and then
selects with short, independent training traces under the proposed M3. The
full length seed 0/1/2 windows are held out for paired validation.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import traceback
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from rcaps.v3.placement import digest, validate as validate_layout
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler

from .capacity import solve, workload_classes
from .capacity_route import CapacityGuidedM3
from .joint import (ARRIVAL_MODES, CASES, HERE, ROOT, VALIDATION_SECONDS,
                    VALIDATION_SEEDS, arrival_trace, case_inputs, read, relative,
                    observed_edge_counts, result_path, reused_formal, run_cell, write)


BASE = HERE / "capacity_joint"
TRAIN_SEED = 100
TRAIN_SECONDS = 300
SMOKE_SECONDS = 60
TRAIN_OFFERED = {"C1_single": 350.0, "C1_multi": 160.0}


def train_trace(case: str, mode: str):
    rate = TRAIN_OFFERED[case]
    trace = arrival_trace(rate, TRAIN_SECONDS, TRAIN_SEED, mode)
    if trace is None:
        trace = OnlineRequestFeeder(cluster_token_throughput=rate,
                                    start_time=0, duration=TRAIN_SECONDS,
                                    seed=TRAIN_SEED).trace
    return trace


def prepare(case: str) -> dict:
    model, physical, template = case_inputs(case)
    entries = list(read(HERE / "plans" / f"{case}.json")["layouts"])
    search_path = BASE / "plans" / f"{case}_capacity_search.json"
    if search_path.exists():
        entries.extend(read(search_path)["selected"])
    classes = workload_classes(train_trace(case, "uniform"))
    scored = []
    for item in entries:
        directory = ROOT / item["layout"]
        state = read(directory / "placement.json")["state"]
        checked = validate_layout(model, state)
        if digest(directory / "solution.ini") != item["solution_sha256"] or \
                digest(directory / "simulator_cluster.ini") != item["sim_cluster_sha256"]:
            raise ValueError(f"Placement changed: {item['label']}")
        started = time.perf_counter()
        lp = solve(model, template, state, classes)
        if not lp["success"]:
            raise ValueError(f"Capacity LP failed: {item['label']}: {lp['message']}")
        scored.append({"layout": item["label"], "path": item["layout"],
                       "solution_sha256": item["solution_sha256"],
                       "sim_cluster_sha256": item["sim_cluster_sha256"],
                       "widths": item["widths"],
                       "legal_edges": len(checked["dag"].edges),
                       "legal_paths": checked["dag"].path_count(),
                       "lp_wall_s": time.perf_counter() - started,
                       "lp": lp})
    scored.sort(key=lambda row: (-row["lp"]["requests_per_s"], row["layout"]))
    # Include all exact LP ties at the second-place rate; naming must not
    # decide whether a single-boundary control is evaluated online.
    cutoff = scored[min(1, len(scored) - 1)]["lp"]["requests_per_s"]
    shortlisted = {row["layout"] for row in scored
                   if row["lp"]["requests_per_s"] >= cutoff - 1e-9}
    shortlisted.add("released_v3")
    result = {"case": case, "physical_sha256": digest(physical),
              "template_sha256": digest(template),
              "training_seed": TRAIN_SEED, "training_duration_s": TRAIN_SECONDS,
              "training_offered_tokens_per_s": TRAIN_OFFERED[case],
              "workload_classes": [vars(row) for row in classes],
              "capacity_ranked": scored, "shortlist": sorted(shortlisted)}
    write(BASE / "plans" / f"{case}.json", result)
    return result


def run_guided(case: str, candidate: dict, seed: int, duration: int,
               mode: str, offered: float) -> tuple[dict, Path]:
    model, physical, _ = case_inputs(case)
    directory = ROOT / candidate["path"]
    if digest(directory / "solution.ini") != candidate["solution_sha256"] or \
            digest(directory / "simulator_cluster.ini") != candidate["sim_cluster_sha256"]:
        raise ValueError("The tested placement changed")
    output = (BASE / "runs" / case / candidate["layout"] /
              f"{mode}_seed{seed}_{duration}s_{int(offered)}.json")
    identity = {"case": case, "layout": candidate["layout"], "seed": seed,
                "duration_s": duration, "arrival_mode": mode,
                "offered_tokens_per_s": offered,
                "physical_sha256": digest(physical),
                "solution_sha256": candidate["solution_sha256"],
                "sim_cluster_sha256": candidate["sim_cluster_sha256"],
                "lp_rate": candidate["lp"]["requests_per_s"]}
    if duration == VALIDATION_SECONDS:
        identity["routing_code_sha256"] = digest(HERE / "capacity_route.py")
        identity["capacity_code_sha256"] = digest(HERE / "capacity.py")
    if output.exists():
        old = read(output)
        if all(old.get(key) == value for key, value in identity.items()):
            return old, output
        raise ValueError(f"Run identity changed: {output}")
    weighted_output = sum(row["output_tokens"] * row["probability"]
                          for row in candidate["lp"]["workload_classes"])
    started = time.perf_counter()
    try:
        row = fixed_window_run(
            CASES[case][0], "queue_dag", offered, duration, 0, seed,
            directory / "solution.ini", directory / "simulator_cluster.ini",
            physical_cluster=physical, machine_counts=model.machine_counts,
            scheduler_factory=partial(CapacityGuidedM3,
                                      lp=candidate["lp"],
                                      typical_output_tokens=round(weighted_output)),
            compact=True, record_query_samples=True,
            trace_override=arrival_trace(offered, duration, seed, mode))
        if row["arrivals"] != len(row["query_samples"]):
            raise ValueError("Missing query samples")
        graph = validate_layout(model, read(directory / "placement.json")["state"])["dag"]
        observed_edge_counts(row["route_counts"], graph)
        row["status"] = "completed"
    except Exception as error:
        row = {"status": "failed", "error": repr(error),
               "traceback": traceback.format_exc()}
    row.update(identity)
    row["wall_s"] = time.perf_counter() - started
    write(output, row)
    return row, output


def smoke(case: str) -> dict:
    plan = read(BASE / "plans" / f"{case}.json")
    entries = {row["layout"]: row for row in plan["capacity_ranked"]}
    rows = []
    for label in plan["shortlist"]:
        candidate = entries[label]
        result, path = run_guided(case, candidate, TRAIN_SEED,
                                  SMOKE_SECONDS, "uniform", TRAIN_OFFERED[case])
        rows.append({"layout": label, "status": result["status"],
                     "path": relative(path), "sha256": digest(path),
                     "routes": len(result.get("route_counts", {})),
                     "trace_sha256": result.get("trace_sha256")})
    if len({row["trace_sha256"] for row in rows}) != 1:
        raise ValueError("Smoke request traces differ")
    output = {"case": case, "rows": rows,
              "passed": all(row["status"] == "completed" and
                            row["routes"] > 0 for row in rows)}
    write(BASE / "plans" / f"{case}_smoke.json", output)
    return output


def choose(case: str) -> dict:
    gate = read(BASE / "plans" / f"{case}_smoke.json")
    if not gate["passed"]:
        raise ValueError("Smoke gate failed")
    plan = read(BASE / "plans" / f"{case}.json")
    entries = {row["layout"]: row for row in plan["capacity_ranked"]}
    rows = []
    for label in plan["shortlist"]:
        candidate = entries[label]
        outcomes = []
        for mode in ARRIVAL_MODES:
            result, path = run_guided(case, candidate, TRAIN_SEED,
                                      TRAIN_SECONDS, mode, TRAIN_OFFERED[case])
            outcomes.append({"mode": mode, "status": result["status"],
                             "path": relative(path), "sha256": digest(path),
                             "trace_sha256": result.get("trace_sha256"),
                             "throughput": result.get("output_throughput_tokens_per_s"),
                             "completion": result.get("completion_fraction"),
                             "ttft_p95_s": result.get("ttft_p95_s"),
                             "tpot_p95_s": result.get("tpot_p95_s")})
        valid = all(row["status"] == "completed" for row in outcomes)
        # Predeclared lexicographic objective. Completion protects against
        # fixed-window censoring before latency comparisons.
        rank = ((-min(row["completion"] for row in outcomes),
                 max(row["tpot_p95_s"] for row in outcomes),
                 max(row["ttft_p95_s"] for row in outcomes),
                 -min(row["throughput"] for row in outcomes),
                 -candidate["lp"]["requests_per_s"], label)
                if valid else (math.inf, math.inf, math.inf,
                               math.inf, math.inf, label))
        rows.append({"layout": label, "rank": rank, "outcomes": outcomes})
    for mode in ARRIVAL_MODES:
        traces = {outcome["trace_sha256"] for row in rows for outcome in row["outcomes"]
                  if outcome["mode"] == mode and outcome["status"] == "completed"}
        if len(traces) != 1:
            raise ValueError(f"Planning traces differ for {mode}")
    winner = min(rows, key=lambda row: row["rank"])
    output = {"case": case, "criterion":
              "maximin completion, then worst P95 TPOT, then worst P95 TTFT, then maximize minimum throughput, then LP rate",
              "training_seed": TRAIN_SEED, "winner": winner["layout"], "rows": rows}
    write(BASE / "plans" / f"{case}_selected.json", output)
    return output


def diagnose_m3(case: str) -> dict:
    """Same chosen placement and training requests, original versus guided M3."""
    selected = read(BASE / "plans" / f"{case}_selected.json")
    plan = read(BASE / "plans" / f"{case}.json")
    item = next(row for row in plan["capacity_ranked"]
                if row["layout"] == selected["winner"])
    model, physical, _ = case_inputs(case)
    directory = ROOT / item["path"]
    outcomes = []
    for mode in ARRIVAL_MODES:
        guided, guided_path = run_guided(case, item, TRAIN_SEED, TRAIN_SECONDS,
                                         mode, TRAIN_OFFERED[case])
        output = (BASE / "runs" / case / item["layout"] /
                  f"original_m3_{mode}_seed{TRAIN_SEED}_{TRAIN_SECONDS}s.json")
        if output.exists():
            original = read(output)
        else:
            original = fixed_window_run(
                CASES[case][0], "queue_dag", TRAIN_OFFERED[case], TRAIN_SECONDS,
                0, TRAIN_SEED, directory / "solution.ini",
                directory / "simulator_cluster.ini", physical_cluster=physical,
                machine_counts=model.machine_counts,
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                compact=True, record_query_samples=True,
                trace_override=arrival_trace(TRAIN_OFFERED[case], TRAIN_SECONDS,
                                             TRAIN_SEED, mode))
            original["status"] = "completed"
            write(output, original)
        if guided["status"] != "completed" or original["status"] != "completed":
            raise ValueError("M3 diagnostic window failed")
        if guided["trace_sha256"] != original["trace_sha256"]:
            raise ValueError("M3 diagnostic traces differ")
        outcomes.append({"mode": mode, "original_source": relative(output),
                         "original_sha256": digest(output),
                         "guided_source": relative(guided_path),
                         "guided_sha256": digest(guided_path),
                         "simulator_wall_delta_s":
                             guided.get("wall_s", 0.0) - original.get("wall_s", 0.0),
                         "throughput_delta":
                             guided["output_throughput_tokens_per_s"] -
                             original["output_throughput_tokens_per_s"],
                         "ttft_p95_delta_s": guided["ttft_p95_s"] -
                             original["ttft_p95_s"],
                         "tpot_p95_delta_s": guided["tpot_p95_s"] -
                             original["tpot_p95_s"],
                         "completion_delta": guided["completion_fraction"] -
                             original["completion_fraction"]})
    result = {"case": case, "selected_layout": selected["winner"],
              "seed": TRAIN_SEED, "outcomes": outcomes}
    write(BASE / "plans" / f"{case}_m3_diagnostic.json", result)
    return result


def validate(case: str) -> dict:
    selected = read(BASE / "plans" / f"{case}_selected.json")
    plan = read(BASE / "plans" / f"{case}.json")
    candidate = next(row for row in plan["capacity_ranked"]
                     if row["layout"] == selected["winner"])
    released = next(row for row in read(HERE / "plans" / f"{case}.json")["layouts"]
                    if row["label"] == "released_v3")
    model, _, _ = case_inputs(case)
    frozen_state = read(ROOT / released["layout"] / "placement.json")["state"]
    frozen_edges = frozenset(validate_layout(model, frozen_state)["dag"].edges)
    rows = []
    for seed in VALIDATION_SEEDS:
        for mode in ARRIVAL_MODES:
            reused = (reused_formal(case, released, "full", seed, frozen_edges)
                      if mode == "uniform" else None)
            if reused is None:
                baseline = run_cell(
                    case, released, "full", seed, VALIDATION_SECONDS,
                    frozen_edges, mode)
                baseline_path = result_path(case, released, "full", seed,
                                            VALIDATION_SECONDS, mode, frozen_edges)
            else:
                baseline, baseline_path = reused
            rows.append({"arm": "released_v3", "seed": seed, "mode": mode,
                         "layout": "released_v3", "status": baseline["status"],
                         "path": relative(baseline_path),
                         "sha256": digest(baseline_path),
                         "trace_sha256": baseline.get("trace_sha256"),
                         "reused": reused is not None,
                         "throughput": baseline.get("output_throughput_tokens_per_s"),
                         "completion": baseline.get("completion_fraction"),
                         "ttft_p95_s": baseline.get("ttft_p95_s"),
                         "tpot_p95_s": baseline.get("tpot_p95_s"),
                         "backlog": baseline.get("backlog_at_window_end")})
            result, path = run_guided(case, candidate, seed,
                                      VALIDATION_SECONDS, mode, CASES[case][1])
            rows.append({"arm": "capacity_joint", "seed": seed, "mode": mode,
                         "layout": selected["winner"],
                         "status": result["status"], "path": relative(path),
                         "sha256": digest(path),
                         "reused": False,
                         "trace_sha256": result.get("trace_sha256"),
                         "throughput": result.get("output_throughput_tokens_per_s"),
                         "completion": result.get("completion_fraction"),
                         "ttft_p95_s": result.get("ttft_p95_s"),
                         "tpot_p95_s": result.get("tpot_p95_s"),
                         "backlog": result.get("backlog_at_window_end")})
            if (baseline["status"] == "completed" and
                    result["status"] == "completed" and
                    baseline["trace_sha256"] != result["trace_sha256"]):
                raise ValueError(f"Validation trace differs: {case}/{seed}/{mode}")
    output = {"case": case, "winner": selected["winner"], "rows": rows}
    write(BASE / "validation" / f"{case}.json", output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "smoke", "choose",
                                          "diagnose-m3", "validate"))
    parser.add_argument("--case", choices=CASES, required=True)
    args = parser.parse_args()
    result = {"prepare": prepare, "smoke": smoke, "choose": choose,
              "diagnose-m3": diagnose_m3,
              "validate": validate}[args.phase](args.case)
    print(json.dumps({"phase": args.phase, "case": args.case,
                      "winner": result.get("winner"),
                      "passed": result.get("passed")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

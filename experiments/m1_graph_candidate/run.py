"""Audit seed 0/1/2 formal records; rerun only invalid or changed windows."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m1_simplification.evidence import (LOADS, SEEDS,
                                                    choose as old_choose,
                                                    digest, paired)
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

from .route_parity import main as verify_route_parity
from .scheduler import GraphModeledQueueAwareDagScheduler


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SYSTEMS = ("m1_graph_candidate", "v2_reference")


def execution_signature(system: str) -> str:
    paths = [ROOT / "rcaps/scheduling/scheduler_queue_cost.py",
             ROOT / "rcaps/scheduling/scheduler_final.py"]
    if system == "m1_graph_candidate":
        paths.extend((ROOT / "rcaps/placement/resource_graph.py",
                      HERE / "scheduler.py"))
    return hashlib.sha256("".join(digest(path) for path in paths)
                          .encode()).hexdigest()


def layout(name: str, system: str) -> tuple[Path, Path]:
    if system == "m1_graph_candidate":
        directory = HERE / "layouts" / name
    elif system == "v2_reference":
        directory = ROOT / "rcaps/v2_layouts" / f"{name}_adaptive"
    else:
        raise ValueError(system)
    return directory / "solution.ini", directory / "simulator_cluster.ini"


def local_path(name: str, seed: int, system: str) -> Path:
    return HERE / "runs" / name / f"seed{seed}" / f"{system}.json"


def valid_local(path: Path, name: str, seed: int, system: str) -> dict:
    row = json.loads(path.read_text(encoding="utf-8"))
    solution, cluster = layout(name, system)
    expected = {"system": system, "method": "queue_dag", "scenario": name,
                "seed": seed, "offered_tokens_per_s": LOADS[name],
                "duration_s": 1800, "warmup_s": 0,
                "evaluation_protocol": "fixed_window_no_tail_drain",
                "query_samples_schema": 1,
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster),
                "execution_sha256": execution_signature(system)}
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"{path}: {key} mismatch")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"{path}: incomplete query samples")
    for key in ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                "completion_fraction", "backlog_at_window_end"):
        if row.get(key) is None:
            raise ValueError(f"{path}: missing {key}")
    return row


def reuse_gate(name: str, parity: dict, layout_audit: dict) -> bool:
    candidate = layout(name, "m1_graph_candidate")
    historical = ROOT / "experiments/m1_simplification/layouts" / name
    stress_path = HERE / "stress_route_parity.json"
    if not stress_path.exists():
        return False
    stress = json.loads(stress_path.read_text(encoding="utf-8"))
    stress_rows = [row for row in stress.get("rows", ())
                   if row.get("scenario") == name]
    stress_passed = (len(stress_rows) == 2 and
                     {row.get("seed") for row in stress_rows} == {100, 101} and
                     all(row.get("passed") and row.get("duration_s") == 300 and
                         row.get("trace_kind") == "offered_load" and
                         row.get("solution_sha256") == digest(candidate[0]) and
                         row.get("sim_cluster_sha256") == digest(candidate[1])
                         for row in stress_rows))
    expected_graph_sources = {
        "resource_graph": digest(ROOT / "rcaps/placement/resource_graph.py"),
        "scheduler_adapter": digest(HERE / "scheduler.py"),
        "routing_implementation": digest(ROOT / "rcaps/scheduling/scheduler_queue_cost.py"),
        "scheduler_final": digest(ROOT / "rcaps/scheduling/scheduler_final.py")}
    expected_layout_sources = {
        "resource_graph": expected_graph_sources["resource_graph"],
        "static_resource": digest(ROOT / "rcaps/placement/static_resource.py"),
        "adaptive": digest(ROOT / "rcaps/placement/adaptive.py")}
    return (stress_passed and
            parity["source_sha256"] == expected_graph_sources and
            layout_audit[name].get("source_sha256") == expected_layout_sources and
            parity[name]["passed"] and
            parity[name]["solution_sha256"] == digest(candidate[0]) and
            parity[name]["sim_cluster_sha256"] == digest(candidate[1]) and
            layout_audit[name]["same_static_score"] and
            layout_audit[name]["same_static_reference"] and
            layout_audit[name]["same_layout_semantics"] and
            all(layout_audit[name]["same_deployment_sha256"].values()) and
            digest(candidate[0]) == digest(historical / "solution.ini") and
            digest(candidate[1]) == digest(historical / "simulator_cluster.ini"))


def choose(name: str, seed: int, system: str, gate: bool) -> tuple[dict | None, dict]:
    local = local_path(name, seed, system)
    rejected = []
    if local.exists():
        try:
            row = valid_local(local, name, seed, system)
            return row, {"source": str(local.relative_to(ROOT)).replace("\\", "/"),
                         "source_kind": "local_rerun", "sha256": digest(local)}
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            rejected.append(str(error))
    if system == "m1_graph_candidate" and gate:
        old, source = old_choose(name, seed, "m1_static_candidate")
        if old is not None:
            return old, {"source": source["source"],
                         "source_kind": "audited_static_reuse",
                         "sha256": source["source_sha256"],
                         "rejected_local": rejected}
    if system == "v2_reference":
        old, source = old_choose(name, seed, "v2_reference")
        if old is not None:
            return old, {"source": source["source"],
                         "source_kind": "audited_v2_reuse",
                         "sha256": source["source_sha256"],
                         "rejected_local": rejected}
    return None, {"source": None, "source_kind": "missing_or_mismatched",
                  "rejected_local": rejected}


def run_local(name: str, seed: int, system: str) -> None:
    solution, cluster = layout(name, system)
    output = local_path(name, seed, system)
    output.parent.mkdir(parents=True, exist_ok=True)
    scheduler = (GraphModeledQueueAwareDagScheduler if system ==
                 "m1_graph_candidate" else QueueAwareDagScheduler)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            redirect_stdout(log), redirect_stderr(log):
        print(f"Formal fallback {name}/seed{seed}/{system}", flush=True)
        try:
            row = fixed_window_run(name, "queue_dag", LOADS[name], 1800, 0,
                                   seed, solution, cluster,
                                   profile_resources=True,
                                   scheduler_factory=scheduler, compact=True,
                                   record_query_samples=True)
            row.update({"system": system, "query_samples_schema": 1,
                        "solution_sha256": digest(solution),
                        "sim_cluster_sha256": digest(cluster),
                        "execution_sha256": execution_signature(system)})
            temporary = output.with_suffix(".json.part")
            temporary.write_text(json.dumps(row, indent=2) + "\n",
                                 encoding="utf-8")
            valid_local(temporary, name, seed, system)
            temporary.replace(output)
            print(f"Complete: {output}", flush=True)
        except Exception:
            traceback.print_exc(file=log)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    verify_route_parity()
    parity = json.loads((HERE / "route_parity.json").read_text(encoding="utf-8"))
    audit = json.loads((HERE / "layout_audit.json").read_text(encoding="utf-8"))
    layout_sources = {
        "resource_graph": digest(ROOT / "rcaps/placement/resource_graph.py"),
        "static_resource": digest(ROOT / "rcaps/placement/static_resource.py"),
        "adaptive": digest(ROOT / "rcaps/placement/adaptive.py")}
    if any(audit[name].get("source_sha256") != layout_sources for name in LOADS):
        raise ValueError("Layout audit is stale; rerun m1_graph_candidate.prepare")
    rows = []
    for name in LOADS:
        gate = reuse_gate(name, parity, audit)
        for seed in SEEDS:
            selected = {system: choose(name, seed, system, gate)
                        for system in SYSTEMS}
            missing = [system for system in SYSTEMS
                       if selected[system][0] is None]
            if not args.dry_run:
                for system in missing:
                    run_local(name, seed, system)
                    selected[system] = choose(name, seed, system, gate)
                try:
                    paired(selected["m1_graph_candidate"][0],
                           selected["v2_reference"][0])
                except ValueError:
                    for system in SYSTEMS:
                        run_local(name, seed, system)
                        selected[system] = choose(name, seed, system, gate)
                    paired(selected["m1_graph_candidate"][0],
                           selected["v2_reference"][0])
            row = {"scenario": name, "seed": seed, "reuse_gate": gate,
                   "sources": {system: selected[system][1]
                               for system in SYSTEMS},
                   "action": ("rerun " + ", ".join(missing)
                              if missing else "reuse")}
            rows.append(row)
            print(json.dumps(row))
    if not args.dry_run:
        (HERE / "run_index.json").write_text(json.dumps(rows, indent=2) + "\n",
                                             encoding="utf-8")


if __name__ == "__main__":
    main()

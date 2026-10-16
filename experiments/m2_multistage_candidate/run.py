"""Run audited 60-second smoke and seed-0/1/2 formal M2 comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m1_graph_candidate.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.placement.topology import TopologyModel

from .analysis import path_use
from .placement import HERE, ROOT, digest
from .prepare import CASES, LOADS, VARIANTS, files


FORMAL_CASES = ("C1_single", "C1_multi", "C2", "C3")
SOURCE_FILES = (ROOT / "rcaps/placement/resource_graph.py",
                ROOT / "rcaps/scheduling/scheduler_queue_cost.py",
                ROOT / "rcaps/scheduling/scheduler_final.py",
                ROOT / "experiments/m1_graph_candidate/scheduler.py")


def execution_sha256() -> str:
    return hashlib.sha256("".join(digest(path) for path in SOURCE_FILES)
                          .encode()).hexdigest()


def identity(case: str, variant: str, duration: int, seed: int) -> dict:
    physical, _, topology = files(case)
    layout = HERE / "layouts" / case / variant
    solution, cluster = layout / "solution.ini", layout / "simulator_cluster.ini"
    return {"case": case, "scenario": topology, "variant": variant,
            "offered_tokens_per_s": LOADS[case], "duration_s": duration,
            "warmup_s": 0, "seed": seed,
            "physical_sha256": digest(physical),
            "solution_sha256": digest(solution),
            "sim_cluster_sha256": digest(cluster),
            "execution_sha256": execution_sha256(),
            "evaluation_protocol": "fixed_window_no_tail_drain"}


def _result_path(phase: str, case: str, variant: str, seed: int) -> Path:
    return HERE / "runs" / phase / case / f"seed{seed}" / f"{variant}.json"


def _run_one(phase: str, case: str, variant: str, seed: int) -> Path:
    duration = 60 if phase == "smoke" else 1800
    output = _result_path(phase, case, variant, seed)
    expected = identity(case, variant, duration, seed)
    if output.exists():
        saved = json.loads(output.read_text(encoding="utf-8"))
        if all(saved.get(key) == value for key, value in expected.items()) and len(
                saved.get("query_samples", {})) == saved.get("arrivals"):
            path_use(case, variant, saved)
            return output
        raise ValueError(f"Existing result differs from requested inputs: {output}")
    physical, _, topology = files(case)
    layout = HERE / "layouts" / case / variant
    model = TopologyModel(physical)
    profile = (ROOT / "examples/simulation/config/machine_profile.ini"
               if case not in ("C1_single", "C1_multi") else None)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    with log_path.open("w", encoding="utf-8") as log, \
            redirect_stdout(log), redirect_stderr(log):
        print(f"{phase} {case}/{variant}/seed{seed}", flush=True)
        try:
            row = fixed_window_run(
                topology, "queue_dag", LOADS[case], duration, 0, seed,
                layout / "solution.ini", layout / "simulator_cluster.ini",
                profile_resources=phase == "formal",
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                compact=True, record_query_samples=True,
                physical_cluster=physical, machine_profile=profile,
                machine_counts=model.machine_counts)
            row.update(expected)
            row["query_samples_schema"] = 1
            if len(row["query_samples"]) != row["arrivals"]:
                raise ValueError("Incomplete request identity samples")
            row["path_use_audit"] = path_use(case, variant, row)
            temporary = output.with_suffix(".json.part")
            temporary.write_text(json.dumps(row, indent=2) + "\n",
                                 encoding="utf-8")
            temporary.replace(output)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return output


def _smoke_gate(audit: dict) -> None:
    smoke_index = HERE / "smoke_index.json"
    if not smoke_index.exists():
        raise ValueError("Run every case's smoke checks before formal windows")
    records = json.loads(smoke_index.read_text(encoding="utf-8"))
    for case in CASES:
        for variant, item in audit[case]["variants"].items():
            if item["status"] != "feasible":
                continue
            record = records.get(case, {}).get(variant)
            if not record or record.get("status") != "passed":
                raise ValueError(f"Smoke result missing or failed: {case}/{variant}")
            source = ROOT / record["source"]
            if digest(source) != record["sha256"]:
                raise ValueError(f"Smoke source changed: {source}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("smoke", "formal"))
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    audit = json.loads((HERE / "offline_audit.json").read_text(encoding="utf-8"))
    if args.phase == "formal":
        _smoke_gate(audit)
    cases = ((args.case,) if args.case else
             (CASES if args.phase == "smoke" else FORMAL_CASES))
    if args.phase == "formal" and any(case not in FORMAL_CASES for case in cases):
        parser.error("Formal comparison is frozen to C1 single/multi and C2/C3")
    index_path = HERE / f"{args.phase}_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    seeds = (100,) if args.phase == "smoke" else (0, 1, 2)
    for case in cases:
        if case not in audit:
            raise ValueError(f"Offline audit missing {case}")
        case_index = index.setdefault(case, {})
        seen = {}
        for variant in VARIANTS:
            item = audit[case]["variants"][variant]
            if item["status"] != "feasible":
                case_index[variant] = {"status": "infeasible",
                                       "reason": item.get("reason")}
                continue
            pair = (item["solution_sha256"], item["sim_cluster_sha256"])
            sources = {}
            for seed in seeds:
                if (pair, seed) in seen:
                    source = seen[pair, seed]
                    reused = True
                else:
                    source = _run_one(args.phase, case, variant, seed)
                    seen[pair, seed] = source
                    reused = False
                row = json.loads(source.read_text(encoding="utf-8"))
                expected = identity(case, variant, 60 if args.phase == "smoke" else 1800,
                                    seed)
                for key, value in expected.items():
                    if key in ("variant",) and reused:
                        continue
                    if row.get(key) != value:
                        raise ValueError(f"Identity mismatch {source}: {key}")
                sources[str(seed)] = {"source": str(source.relative_to(ROOT)).replace("\\", "/"),
                                      "sha256": digest(source), "reused": reused,
                                      "trace_sha256": row["trace_sha256"]}
            case_index[variant] = {"status": "passed", "sources": sources,
                                   "source": sources[str(seeds[0])]["source"],
                                   "sha256": sources[str(seeds[0])]["sha256"]}
            print(case, variant, "reuse" if all(v["reused"] for v in sources.values())
                  else "run", flush=True)
        # Equal seeds in one resource pool must have identical arrival traces.
        for seed in seeds:
            hashes = {case_index[variant]["sources"][str(seed)]["trace_sha256"]
                      for variant in VARIANTS if case_index[variant]["status"] == "passed"}
            if len(hashes) != 1:
                raise ValueError(f"Trace mismatch in {case}/seed{seed}")
        index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(index_path)


if __name__ == "__main__":
    main()

"""Check whether the branch result persists with V3's full M1 DAG routing."""

from __future__ import annotations

import argparse
import contextlib
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.prepare import files
from rcaps.v3.placement import digest
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def one(case: str, variant: str, seed: int) -> str:
    plan = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
    info = plan["cases"][case]["variants"][variant]
    physical, _, scenario = files(case)
    deployment = HERE / "layouts" / case / variant
    if digest(deployment / "solution.ini") != info["solution_sha256"] or \
            digest(deployment / "simulator_cluster.ini") != info["sim_cluster_sha256"]:
        raise ValueError("Deployment changed after plan freeze")
    load = 700. if case == "C1_single" else 320.
    output = HERE / "runs" / "full_dag" / case / variant / f"load{load:g}_seed{seed}.json"
    if output.exists():
        row = json.loads(output.read_text(encoding="utf-8"))
        if (row["solution_sha256"] == info["solution_sha256"] and
                row["offered_tokens_per_s"] == load and row["seed"] == seed):
            return str(output)
        raise ValueError("Existing run identity changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", load, 1800, 0, seed,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=GraphModeledQueueAwareDagScheduler)
            row.update({"case": case, "variant": variant, "routing": "full_m1_dag",
                        "solution_sha256": info["solution_sha256"],
                        "sim_cluster_sha256": info["sim_cluster_sha256"],
                        "transfer_runner_sha256": digest(HERE / "transfer.py")})
            temporary = output.with_suffix(".json.part")
            temporary.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
            temporary.replace(output)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return str(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    jobs = (("C1_single", "k2", 0), ("C1_single", "k3", 0),
            ("C1_multi", "k2", 0))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, *job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                print("PASS", job, future.result(), flush=True)
            except Exception as exc:
                print("FAIL", job, repr(exc), flush=True)
                raise


if __name__ == "__main__":
    main()

"""Evaluate a score-independent structure sample to check ranking accuracy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from rcaps.placement import adaptive
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OFFERED = {"single": 700.0, "multi": 320.0}
SEEDS = (100, 101)
DURATION = 600


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(scenario: str) -> dict:
    return json.loads((HERE / "modeling_candidates" / f"{scenario}.json").read_text(
        encoding="utf-8"))


def materialize(scenario: str) -> list[str]:
    data = manifest(scenario)
    physical, template = scenario_files(scenario)
    model = TopologyModel(physical)
    by_id = {row["id"]: row for row in data["entries"]}
    for candidate_id in data["diagnostic_ids"]:
        row = by_id[candidate_id]
        destination = HERE / "layouts" / "diagnostic" / scenario / candidate_id
        state = {**row["state"],
                 "lengths": {int(node): length for node, length in
                             row["state"]["lengths"].items()}}
        adaptive.save(model, template, state, destination,
                      {"experiment": "modeling_ranking_diagnostic",
                       "candidate_id": candidate_id,
                       "scores": row["scores"]})
    return data["diagnostic_ids"]


def one(scenario: str, candidate_id: str, seed: int) -> None:
    if candidate_id not in manifest(scenario)["diagnostic_ids"] or seed not in SEEDS:
        raise ValueError("Candidate or seed is outside the frozen diagnostic set")
    directory = HERE / "layouts" / "diagnostic" / scenario / candidate_id
    solution, cluster = directory / "solution.ini", directory / "simulator_cluster.ini"
    output = HERE / "diagnostic_runs" / scenario / candidate_id / f"seed{seed}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    identity = {"system": "rcaps_v2_model_diagnostic", "scenario": scenario,
                "candidate_id": candidate_id, "seed": seed,
                "offered_tokens_per_s": OFFERED[scenario], "duration_s": DURATION,
                "warmup_s": 0, "query_samples_schema": 1,
                "solution_sha256": digest(solution),
                "sim_cluster_sha256": digest(cluster)}
    if output.is_file():
        previous = json.loads(output.read_text(encoding="utf-8"))
        if all(previous.get(key) == value for key, value in identity.items()):
            print(f"skip {output}", flush=True)
            return
        raise ValueError(f"Existing diagnostic has different identity: {output}")
    record = fixed_window_run(
        scenario, "queue_dag", OFFERED[scenario], DURATION, 0, seed,
        solution, cluster, profile_resources=True,
        scheduler_factory=QueueAwareDagScheduler, compact=True,
        record_query_samples=True)
    record.update(identity)
    temporary = output.with_suffix(".json.part")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"done {output}", flush=True)


def all_runs(scenario: str, workers: int) -> None:
    ids = materialize(scenario)
    jobs = [(candidate_id, seed) for candidate_id in ids for seed in SEEDS]

    def launch(candidate_id: str, seed: int) -> tuple[str, int, int]:
        command = [sys.executable, "-u", "-m",
                   "experiments.v2_core_ablations.diagnostic_run",
                   "--scenario", scenario, "--candidate-id", candidate_id,
                   "--seed", str(seed)]
        log = HERE / "diagnostic_runs" / scenario / candidate_id / f"seed{seed}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = "0"
        env["MPLBACKEND"] = "Agg"
        with log.open("w", encoding="utf-8") as stream:
            stream.write("Command: " + subprocess.list2cmdline(command) + "\n\n")
            stream.flush()
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    check=False)
        return candidate_id, seed, result.returncode

    failed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(launch, *job) for job in jobs]
        for future in as_completed(futures):
            candidate_id, seed, code = future.result()
            print(f"{scenario}/{candidate_id}/seed{seed}: "
                  f"{'done' if code == 0 else f'failed ({code})'}", flush=True)
            if code:
                failed.append((candidate_id, seed))
    if failed:
        raise RuntimeError(f"Diagnostic failures: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=OFFERED, required=True)
    parser.add_argument("--candidate-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.candidate_id is None:
        all_runs(args.scenario, args.workers)
    elif args.seed is None:
        parser.error("--seed required with --candidate-id")
    else:
        one(args.scenario, args.candidate_id, args.seed)

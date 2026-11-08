"""Event-simulator fitness for the HexGen GA+DP development implementation.

The paper uses a simulator to score partition SLO attainment. Here the
candidate population is evolved on held-out development seeds, using the
same fixed-window event simulator that will later evaluate formal seeds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import traceback
from pathlib import Path

from benchmarks.layout import scenario
from rcaps.v3.topology import TopologyModel

from .evaluate import evaluate
from .hexgen_layout import DEFAULTS, export, initial_partition, mutate, place_layers


HERE = Path(__file__).resolve().parent
SEEDS = (100, 101)
SETTINGS = {
    "single24": {"offered": 350.0, "ttft": 6.0, "tpot": 0.6},
    "multi24": {"offered": 160.0, "ttft": 10.0, "tpot": 0.8},
    "high_heterogeneity42": {"offered": 1000.0, "ttft": 10.0, "tpot": 0.8},
}


def canonical(partition) -> str:
    return json.dumps([list(group) for group in partition], separators=(",", ":"))


def candidate_id(partition) -> str:
    return hashlib.sha256(canonical(partition).encode()).hexdigest()[:16]


def score(result: dict, limits: dict) -> dict:
    good_tokens = sum(
        item["output_tokens"] for item in result["query_samples"].values()
        if item["completed"] and item["ttft_s"] is not None
        and item["tpot_s"] is not None
        and item["ttft_s"] <= limits["ttft"]
        and item["tpot_s"] <= limits["tpot"]
    )
    return {"goodput_tokens_per_s": good_tokens / (result["duration_s"] - result["warmup_s"]),
            "output_throughput_tokens_per_s": result["output_throughput_tokens_per_s"],
            "completion_fraction": result["completion_fraction"],
            "trace_sha256": result["trace_sha256"]}


def search(case: str, output: Path, generations: int = 4,
           population_size: int = 6, seed: int = 2403) -> dict:
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    physical, template = DEFAULTS[case]
    model = TopologyModel(physical)
    limits = SETTINGS[case]
    rng = random.Random(seed)
    max_replicas = min(4, sum(model.capacity.values()) // model.layers)
    candidates = {}

    def assess(partition):
        key = candidate_id(partition)
        if key in candidates:
            return candidates[key]
        folder = output / "candidates" / key
        record = {"partition": [list(group) for group in partition],
                  "candidate_id": key, "status": "pending"}
        candidates[key] = record
        try:
            layouts = [place_layers(model, group) for group in partition]
            generated = export(model, template,
                               {"layouts": layouts, "static_fitness": None,
                                "candidate_count": 1, "ga_seed": seed,
                                "generations": generations,
                                "population_size": population_size,
                                "fitness_limitation": "candidate ranked by event simulation separately"},
                               folder)
            scores = []
            for development_seed in SEEDS:
                result = evaluate(folder / "manifest.json", limits["offered"],
                                  duration=180, warmup=30, seed=development_seed)
                metrics = score(result, limits)
                scores.append(metrics)
                path = folder / f"dev_seed{development_seed}.json"
                path.write_text(json.dumps({"status": "development_result", "score": metrics,
                                            "candidate_manifest_sha256": hashlib.sha256(
                                                (folder / "manifest.json").read_bytes()).hexdigest(),
                                            "run": result}, indent=2) + "\n", encoding="utf-8")
            record.update(status="success", scores=scores,
                          mean_goodput=sum(row["goodput_tokens_per_s"] for row in scores) / len(scores),
                          mean_output=sum(row["output_throughput_tokens_per_s"] for row in scores) / len(scores),
                          manifest=str(folder / "manifest.json"),
                          pipeline_count=len(generated["pipelines"]))
        except BaseException as error:
            record.update(status="failed", error_type=type(error).__name__,
                          error=str(error), traceback=traceback.format_exc())
            (output / "candidates" / f"{key}.failure.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    population = set()
    for count in range(1, max_replicas + 1):
        for _ in range(population_size):
            partition = initial_partition(model, count, rng)
            if partition is not None:
                population.add(partition)
    if not population:
        raise ValueError("No memory-feasible partition")
    for generation in range(generations):
        for partition in sorted(population):
            assess(partition)
        viable = [item for item in population if candidates[candidate_id(item)]["status"] == "success"]
        if not viable:
            break
        elite = sorted(viable, key=lambda item: (
            -candidates[candidate_id(item)]["mean_goodput"],
            -candidates[candidate_id(item)]["mean_output"], item))[:population_size]
        population = set(elite)
        for parent in elite:
            for _ in range(2):
                population.add(mutate(model, parent, rng))
        print(f"generation={generation + 1} candidates={len(candidates)} "
              f"best={candidate_id(elite[0])} goodput={candidates[candidate_id(elite[0])]['mean_goodput']:.3f}",
              flush=True)
    successful = [row for row in candidates.values() if row["status"] == "success"]
    if not successful:
        raise RuntimeError("All candidates failed; see candidate failure records")
    best = min(successful, key=lambda row: (-row["mean_goodput"], -row["mean_output"], row["candidate_id"]))
    summary = {"status": "development_selection", "case": case,
               "official_hexgen_commit": "949414d1be18e504752508c0559cb966ddf999f4",
               "search_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "planner_source_sha256": hashlib.sha256((HERE / "hexgen_layout.py").read_bytes()).hexdigest(),
               "evaluator_source_sha256": hashlib.sha256((HERE / "evaluate.py").read_bytes()).hexdigest(),
               "ga_seed": seed, "development_seeds": list(SEEDS),
               "duration_s": 180, "warmup_s": 30, "limits": limits,
               "generations": generations, "population_size": population_size,
               "candidate_count": len(candidates),
               "success_count": len(successful), "selected_candidate_id": best["candidate_id"],
               "selected_manifest": best["manifest"],
               "candidates": list(candidates.values())}
    (output / "SELECTION.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=DEFAULTS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generations", type=int, default=4)
    parser.add_argument("--population", type=int, default=6)
    parser.add_argument("--seed", type=int, default=2403)
    args = parser.parse_args()
    result = search(args.case, args.output, args.generations, args.population, args.seed)
    print(json.dumps({key: result[key] for key in
                      ("case", "candidate_count", "success_count", "selected_candidate_id",
                       "selected_manifest")}, indent=2))


if __name__ == "__main__":
    main()

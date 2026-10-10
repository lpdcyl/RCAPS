"""Measure full GREEN placement generation with process CPU and wall time."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import gurobipy

from experiments.critical_graph.partition import initial_partition, refine, save, scenario
from experiments.critical_graph.topology import TopologyModel


HERE = Path(__file__).resolve().parent


def measure(name: str, repetitions: int) -> dict:
    cluster, template = scenario(name)
    samples = []
    for trial in range(repetitions):
        wall_start, cpu_start = time.perf_counter(), time.process_time()
        model = TopologyModel(cluster)
        coarse = initial_partition(model)
        final, trace = refine(model, coarse)
        result = save(model, template, final, HERE / "runs/planner" / name, trace)
        samples.append({
            "trial": trial,
            "wall_s": time.perf_counter() - wall_start,
            "process_cpu_s": time.process_time() - cpu_start,
            "accepted_moves": len(trace) - 1,
            "solution": result["solution"],
        })
    return {"scenario": name, "algorithm": "complete_green_placement_generation",
            "gurobi_version": ".".join(map(str, gurobipy.gurobi.version())),
            "samples": samples}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    if args.repetitions < 1 or gurobipy.gurobi.version()[0] != 13:
        parser.error("Need positive repetitions and Gurobi 13")
    records = {name: measure(name, args.repetitions) for name in ("single", "multi")}
    output = HERE / "runs/planner/overhead.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()

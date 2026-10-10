"""Generate layouts using phase-corrected compute demand and the old objective."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.queue_predictor_2026.generate import LOADS, refine_queue
from rcaps.placement.partition import initial_partition, save, scenario
from rcaps.placement.queue_predictor import predict
from rcaps.placement.topology import TopologyModel


HERE = Path(__file__).resolve().parent


def generate(name: str) -> dict:
    physical, template = scenario(name)
    model = TopologyModel(physical)
    state, trace = refine_queue(model, initial_partition(model), LOADS[name],
                                max_steps=16, service_mode="phase")
    destination = HERE / "layouts" / name
    saved = save(model, template, state, destination, trace,
                 algorithm="phase-corrected queue-flow placement, full-neighborhood search")
    prediction = predict(model, state, LOADS[name], service_mode="phase")
    (destination / "queue_prediction.json").write_text(json.dumps({
        "service_mode": "phase",
        "offered_tokens_per_s": LOADS[name],
        "gpu_visit_probability": prediction.gpu_visit_probability,
        "gpu_utilization": prediction.gpu_utilization,
        "gpu_wait_s": prediction.gpu_wait_s,
        "gpu_queue_pressure": prediction.gpu_queue_pressure,
        "link_utilization": prediction.link_utilization,
        "link_wait_s": prediction.link_wait_s,
        "max_queue_pressure": prediction.max_queue_pressure,
        "total_queue_pressure": sum(prediction.gpu_queue_pressure.values()),
        "mean_route_cost_s": prediction.mean_route_cost_s,
        "iterations": prediction.iterations,
    }, indent=2) + "\n", encoding="utf-8")
    return {"scenario": name, "steps": len(trace) - 1,
            "candidate_evaluations": trace[0]["candidate_evaluations"],
            "planning_s": trace[0]["planning_s"],
            "initial_score": trace[0]["score"],
            "final_score": trace[-1]["score"],
            "solution": saved["solution"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, choices=LOADS)
    args = parser.parse_args()
    print(json.dumps(generate(args.scenario), indent=2))

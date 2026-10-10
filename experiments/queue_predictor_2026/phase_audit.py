"""Compare resource service conventions on pre-existing fixed layouts."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from experiments.validation_2026.hotspot_audit import (placement_state,
                                                       profile_values, spearman)
from rcaps.placement.partition import scenario
from rcaps.placement.queue_predictor import predict
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
LOADS = {"single": 700.0, "multi": 320.0}


def audit() -> dict:
    report = {}
    for name, load in LOADS.items():
        model = TopologyModel(scenario(name)[0])
        report[name] = {}
        for arm, layout, results, filename in (
            ("coarse", ROOT / "rcaps/variant_layouts" / f"{name}_coarse",
             ROOT / "experiments/validation_2026/runs70b", "rcaps_coarse.json"),
            ("original", ROOT / "rcaps/layouts" / name,
             ROOT / "experiments/validation_2026/runs70b", "rcaps.json"),
            ("queue_max", ROOT / "experiments/queue_predictor_2026/layouts" / name,
             ROOT / "experiments/queue_predictor_2026/runs70b", "rcaps_queue_predictor.json"),
        ):
            state = placement_state(layout)
            row = {}
            for mode in ("legacy", "phase"):
                prediction = predict(model, state, load, service_mode=mode)
                correlations = []
                for seed in (0, 1, 2):
                    actual = json.loads((results / name / f"seed{seed}" / filename).read_text(encoding="utf-8"))
                    queue = profile_values(actual, "gpu_queue_request_s", model.types)
                    busy = profile_values(actual, "gpu_busy_fraction", model.types)
                    correlations.append({
                        "queue": spearman(prediction.gpu_queue_pressure, queue),
                        "busy": spearman(prediction.gpu_utilization, busy),
                    })
                row[mode] = {
                    "queue_rank_spearman": mean(x["queue"] for x in correlations),
                    "busy_rank_spearman": mean(x["busy"] for x in correlations),
                    "max_gpu_utilization": max(prediction.gpu_utilization.values()),
                    "max_gpu_queue_pressure": prediction.max_queue_pressure,
                    "total_gpu_queue_pressure": sum(prediction.gpu_queue_pressure.values()),
                    "mean_route_cost_s": prediction.mean_route_cost_s,
                }
            report[name][arm] = row
    return report


if __name__ == "__main__":
    result = audit()
    target = Path(__file__).with_name("phase_audit.json")
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, arms in result.items():
        for arm, modes in arms.items():
            for mode, values in modes.items():
                print(name, arm, mode, *(f"{key}={value:.3f}" for key, value in values.items()))
    print(target)

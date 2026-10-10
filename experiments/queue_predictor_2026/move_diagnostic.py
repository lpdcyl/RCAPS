"""Retrospective layout-direction audit for the analytic queue proxy.

Evaluation profiles are read only after all compared layouts have been fixed.
This file must never be imported by placement generation.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from experiments.validation_2026.hotspot_audit import placement_state
from rcaps.placement.partition import scenario
from rcaps.placement.queue_predictor import predict
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOADS = {"single": 700.0, "multi": 320.0}


def audit() -> dict:
    output = {}
    for name, load in LOADS.items():
        model = TopologyModel(scenario(name)[0])
        layouts = {
            "coarse": ROOT / "rcaps/variant_layouts" / f"{name}_coarse",
            "original": ROOT / "rcaps/layouts" / name,
            "queue_max": HERE / "layouts" / name,
        }
        predictions = {}
        for arm, layout in layouts.items():
            state = placement_state(layout)
            queue = predict(model, state, load)
            graph = model.measure(state, demand_mode="ensemble" if name == "single" else "canonical")
            predictions[arm] = {
                "max_gpu_queue_pressure": queue.max_queue_pressure,
                "total_gpu_queue_pressure": sum(queue.gpu_queue_pressure.values()),
                "total_link_wait_s": sum(queue.link_wait_s.values()),
                "mean_route_cost_s": queue.mean_route_cost_s,
                "event_ttft_s": graph.ttft_s,
                "event_tpot_s": graph.tpot_s,
            }
        measurements = {}
        for arm, filename, base in (
            ("coarse", "rcaps_coarse.json", ROOT / "experiments/validation_2026/runs70b"),
            ("original", "rcaps.json", ROOT / "experiments/validation_2026/runs70b"),
            ("queue_max", "rcaps_queue_predictor.json", HERE / "runs70b"),
        ):
            runs = [json.loads((base / name / f"seed{seed}" / filename).read_text(encoding="utf-8"))
                    for seed in (0, 1, 2)]
            measurements[arm] = {
                "seeds": [{
                    "seed": seed,
                    "gpu_queue_per_arrival": sum(run["gpu_queue_request_s"].values()) / run["arrivals"],
                    "throughput": run["output_throughput_tokens_per_s"],
                    "ttft_p95_s": run["ttft_p95_s"],
                    "tpot_p95_s": run["tpot_p95_s"],
                    "completion_fraction": run["completion_fraction"],
                    "backlog": run["backlog_at_window_end"],
                    "trace_sha256": run["trace_sha256"],
                } for seed, run in enumerate(runs)],
            }
            measurements[arm]["mean"] = {
                key: mean(row[key] for row in measurements[arm]["seeds"])
                for key in ("gpu_queue_per_arrival", "throughput", "ttft_p95_s",
                            "tpot_p95_s", "completion_fraction", "backlog")
            }
        for seed in (0, 1, 2):
            traces = {measurements[arm]["seeds"][seed]["trace_sha256"] for arm in layouts}
            if len(traces) != 1:
                raise AssertionError(f"Trace mismatch: {name} seed {seed}")
        output[name] = {"predictions": predictions, "measurements": measurements}
    return output


if __name__ == "__main__":
    result = audit()
    target = HERE / "move_diagnostic.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, data in result.items():
        print(name)
        for arm in data["predictions"]:
            p = data["predictions"][arm]
            m = data["measurements"][arm]["mean"]
            print(f"{arm:10s} predicted max={p['max_gpu_queue_pressure']:.3f} "
                  f"sum={p['total_gpu_queue_pressure']:.3f} "
                  f"route={p['mean_route_cost_s']:.3f} "
                  f"event_ttft={p['event_ttft_s']:.3f} "
                  f"actual_queue={m['gpu_queue_per_arrival']:.3f} "
                  f"throughput={m['throughput']:.3f} "
                  f"ttft={m['ttft_p95_s']:.3f} tpot={m['tpot_p95_s']:.3f}")
    print(target)

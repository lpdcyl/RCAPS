"""Audit whether the offline event-graph proxy predicts local move directions.

This is deliberately an audit, not a method selector: it reads placements and
simulator results already produced by the documented experiments.
"""

from __future__ import annotations

import json
from pathlib import Path

from .partition import scenario
from .topology import TopologyModel


RUNS = Path(__file__).resolve().parent / "runs"


def state_from_placement(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    intervals = {int(node): (int(span[0]), int(span[1]))
                 for node, span in data["intervals"].items()}
    shared = int(data["shared"])
    return {"shared": shared, "shared_length": intervals[shared][1],
            "paths": [[int(node) for node in branch] for branch in data["branches"]],
            "lengths": {node: end - start for node, (start, end) in intervals.items()
                        if node != shared}}


def percent(new: float, old: float) -> float:
    return 100 * (new / old - 1)


def pair(name: str, old_dir: str, new_dir: str,
         old_result: str, new_result: str) -> dict:
    model = TopologyModel(scenario(name)[0])
    before = model.measure(state_from_placement(RUNS / old_dir / "placement.json"),
                           demand_mode="canonical")
    after = model.measure(state_from_placement(RUNS / new_dir / "placement.json"),
                          demand_mode="canonical")
    observed_before = json.loads((RUNS / old_dir / old_result).read_text(encoding="utf-8"))
    observed_after = json.loads((RUNS / new_dir / new_result).read_text(encoding="utf-8"))
    protocol = ("scenario", "seed", "duration_s", "warmup_s", "arrivals",
                "offered_tokens_per_s")
    if any(observed_before[key] != observed_after[key] for key in protocol):
        raise ValueError(f"Incomparable pilot results: {old_dir} vs {new_dir}")
    return {
        "scenario": name, "from": old_dir, "to": new_dir,
        "measurement_s": observed_before["duration_s"] - observed_before["warmup_s"],
        "seed": observed_before["seed"],
        "model": {
            "ttft_proxy_change_percent": percent(after.ttft_s, before.ttft_s),
            "tpot_proxy_change_percent": percent(after.tpot_s, before.tpot_s),
            "max_resource_demand_change_percent": percent(
                after.bottleneck_s, before.bottleneck_s),
            "before_bottleneck_resource": before.bottleneck_resource,
            "after_bottleneck_resource": after.bottleneck_resource,
        },
        "simulator": {
            "p95_ttft_change_percent": percent(
                observed_after["ttft_p95_s"], observed_before["ttft_p95_s"]),
            "p95_tpot_change_percent": percent(
                observed_after["tpot_p95_s"], observed_before["tpot_p95_s"]),
            "output_throughput_change_percent": percent(
                observed_after["output_throughput_tokens_per_s"],
                observed_before["output_throughput_tokens_per_s"]),
        },
    }


def main() -> None:
    audit = {
        "single_shared_prefix_push": pair(
            "single", "single", "single_sharedpush", "pilot_seed1_420.json",
            "pilot_fixed_seed1_420.json"),
        "multi_critical_path_refinement": pair(
            "multi", "multi_coarse", "multi", "pilot_seed1_420.json",
            "pilot_final_seed1_420.json"),
    }
    output = RUNS / "model_audit_seed1_420.json"
    output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()

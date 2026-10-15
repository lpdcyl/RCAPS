"""Time both offline evaluators on the same six development layouts."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from rcaps.placement import adaptive
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel

from .placement import ROOT, static_measure


HERE = Path(__file__).resolve().parent
REPEATS = 5


def candidate_states(scenario: str) -> list[dict]:
    path = (ROOT / "experiments" / "v2_core_ablations" /
            "modeling_candidates" / f"{scenario}.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in manifest["entries"]}
    states = []
    for candidate_id in manifest["diagnostic_ids"]:
        entry = entries[candidate_id]
        state = entry["state"]
        state["lengths"] = {int(key): value for key, value in state["lengths"].items()}
        states.append(state)
    if len(states) != 6:
        raise ValueError(f"Expected six frozen development candidates: {path}")
    return states


def main() -> None:
    output = {"repeats_per_candidate": REPEATS, "scenarios": {}}
    for scenario in ("single", "multi"):
        physical, _ = scenario_files(scenario)
        model = TopologyModel(physical)
        states = candidate_states(scenario)
        times = {"static_resource": [], "event_dag": []}
        for state in states:
            for _ in range(REPEATS):
                for name, function in (("static_resource", static_measure),
                                       ("event_dag", adaptive.measure)):
                    start = time.perf_counter()
                    function(model, state)
                    times[name].append(1000 * (time.perf_counter() - start))
        output["scenarios"][scenario] = {
            name: {"evaluations": len(values),
                   "median_ms": statistics.median(values),
                   "mean_ms": statistics.mean(values),
                   "min_ms": min(values), "max_ms": max(values)}
            for name, values in times.items()}
    target = HERE / "evaluator_timing.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()

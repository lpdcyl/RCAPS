"""Recompute placement-search cost and check exported layouts are unchanged."""

from __future__ import annotations

import json
from pathlib import Path

from rcaps.placement.partition import (initial_partition, refine, refine_static,
                                       scenario as placement_scenario)
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main() -> None:
    result = {}
    for scenario in ("single", "multi"):
        model = TopologyModel(placement_scenario(scenario)[0])
        initial = initial_partition(model)
        data = {}
        for method, search in (("rcaps_full_search", "full"),
                               ("rcaps", "guided"),
                               ("rcaps_static_no_graph", "static")):
            if search == "static":
                state, trace = refine_static(model, initial)
            else:
                state, trace = refine(model, initial, guided=search == "guided")
            folder = (ROOT / "rcaps/layouts" / scenario if search == "guided" else
                      ROOT / "rcaps/variant_layouts" /
                      f"{scenario}_{'full_search' if search == 'full' else 'static_no_graph'}")
            stored = json.loads((folder / "placement.json").read_text(encoding="utf-8"))
            intervals = {str(node): list(span)
                         for node, span in model.intervals(state).items()}
            if intervals != stored["intervals"]:
                raise AssertionError(f"Recomputed layout differs: {scenario}, {method}")
            data[method] = {"candidate_evaluations": trace[0]["candidate_evaluations"],
                            "planning_s": trace[0]["planning_s"],
                            "accepted_steps": len(trace) - 1}
        result[scenario] = data
    destination = HERE / "placement_costs.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()

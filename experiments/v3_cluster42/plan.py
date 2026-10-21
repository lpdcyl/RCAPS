"""Plan a V3 layout for the 42-node Helix high-heterogeneity cluster.

The frozen V3 M2 search (rcaps/v3/search.py, Beam 64, 500 evaluations per
phase, multi_any) runs unchanged. Planning inputs differ from C1 only where
C1 had frozen choices: there is no frozen seed or reference state for this
cluster, so the reference is the cheapest legal single-boundary initializer
produced by the frozen ``initial_states`` and no seed is passed. The Helix
ILP simulator file is the export template (node attributes only; links are
rewritten from the M1 DAG by ``placement.save``).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from rcaps.v3.placement import measure, save
from rcaps.v3.search import cheap_cost, initial_states, search
from rcaps.v3.topology import TopologyModel

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "artifact_evaluation/high_heterogeneity"
PHYSICAL = BASE / "config/cluster42.ini"
TEMPLATE = BASE / "layout_llama70b/ilp/simulator_cluster.ini"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    started = time.perf_counter()
    model = TopologyModel(PHYSICAL)
    states, info = initial_states(model, a100_prefix=False, multistage=False)
    if not states:
        raise SystemExit(f"No legal single-boundary initializer: {info}")
    reference = min(states, key=lambda state: cheap_cost(model, state))
    result = search(model, reference, a100_prefix=False)["multi"]
    elapsed = time.perf_counter() - started
    if result["status"] != "feasible":
        raise SystemExit(f"V3 search infeasible: {result}")
    metadata = {key: value for key, value in result.items() if key not in ("state", "status")}
    metadata.update({"version": "RCAPS V3", "candidate_variant": "multi_any",
                     "case": "cluster42", "physical": PHYSICAL.relative_to(ROOT).as_posix(),
                     "physical_sha256": digest(PHYSICAL),
                     "template": TEMPLATE.relative_to(ROOT).as_posix(),
                     "template_sha256": digest(TEMPLATE),
                     "reference_state": reference, "reference_metrics": measure(model, reference),
                     "planning_wall_s": elapsed})
    saved = save(model, TEMPLATE, result["state"], HERE / "layout", metadata)
    print(json.dumps({"widths": saved.get("widths"), "planning_wall_s": elapsed,
                      "segments": [(s["start"], s["end"], len(s["replicas"]))
                                   for s in result["state"]["segments"]]}, indent=2))


if __name__ == "__main__":
    main()

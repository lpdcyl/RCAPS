"""Verify the frozen V3 code, layouts, and candidate provenance.

Use --write-manifest only when deliberately establishing a new release. The
default command checks the saved manifest and never modifies released files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.m2_multistage_candidate.prepare import files
from rcaps.placement.topology import TopologyModel
from rcaps.v3.placement import validate
from rcaps.v3_method import layout


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
CASES = {"C1_single": "single", "C1_multi": "multi",
         "C2": "C2", "C3": "C3", "C4": "C4", "C5": "C5"}
CORE = (
    "rcaps/v3/resource_graph.py", "rcaps/v3/placement.py",
    "rcaps/v3/search.py", "rcaps/v3/plan.py",
    "rcaps/v3/planning_inputs.json", "rcaps/v3/scheduler.py",
    "rcaps/v3_method.py",
    "rcaps/placement/adaptive.py", "rcaps/placement/topology.py",
    "rcaps/scheduling/scheduler_final.py",
    "rcaps/scheduling/scheduler_queue_cost.py",
    "rcaps/scheduling/routing_dag.py", "benchmarks/fixed_window.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot() -> dict:
    layouts = {}
    for case, scenario in CASES.items():
        original = ROOT / "experiments/m2_multistage_candidate/layouts" / case / "multi_any"
        solution, simulator = layout(scenario, ROOT)
        source_record = json.loads((original / "placement.json").read_text(encoding="utf-8"))
        released_record = json.loads((solution.parent / "placement.json").read_text(encoding="utf-8"))
        if source_record["state"] != released_record["state"]:
            raise ValueError(f"V3 state differs from candidate: {case}")
        for name, target in (("solution.ini", solution),
                             ("simulator_cluster.ini", simulator)):
            if digest(original / name) != digest(target):
                raise ValueError(f"V3 deployment differs from candidate: {case}/{name}")
        physical, _, _ = files(case)
        model = TopologyModel(physical)
        checked = validate(model, released_record["state"])
        if checked["dag"].path_count() != source_record["compatible_paths"]:
            raise ValueError(f"V3 execution paths differ: {case}")
        if len(checked["dag"].edges) != source_record["compatibility_edges"]:
            raise ValueError(f"V3 execution edges differ: {case}")
        layouts[scenario] = {
            "case": case, "candidate_variant": "multi_any",
            "source": str(original.relative_to(ROOT)).replace("\\", "/"),
            "state_sha256": digest(solution.parent / "placement.json"),
            "physical_source": str(physical.relative_to(ROOT)).replace("\\", "/"),
            "physical_sha256": digest(physical),
            "solution_sha256": digest(solution),
            "sim_cluster_sha256": digest(simulator),
            "widths": released_record["widths"],
            "compatible_paths": checked["dag"].path_count(),
            "compatibility_edges": len(checked["dag"].edges),
        }
    evidence = ROOT / "experiments/m2_multistage_candidate/summary.json"
    return {
        "version": "RCAPS V3",
        "method": "rcaps_v3",
        "selection_rule": "multi_any: at most two boundaries, unrestricted initial GPU type, one shared search phase plus 500 evaluations for the multistage extension",
        "m1": "graph-only physical resources and layer-compatible execution DAG",
        "m2": "bounded multistage shared-replicated placement with static 0.40/0.35/0.25 objective",
        "m3": "unchanged queue-aware DAG scheduler with graph-edge adapter",
        "code_sha256": {name: digest(ROOT / name) for name in CORE},
        "layouts": layouts,
        "formal_candidate_evidence": {
            "source": str(evidence.relative_to(ROOT)).replace("\\", "/"),
            "sha256": digest(evidence),
            "seeds": [0, 1, 2], "duration_s": 1800,
            "formal_cases": ["C1_single", "C1_multi", "C2", "C3"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    current = snapshot()
    if args.write_manifest:
        MANIFEST.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"wrote {MANIFEST}")
    else:
        saved = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if current != saved:
            raise ValueError("V3 release manifest drifted; inspect code, layouts, or evidence")
        print(f"V3 release verified: {len(current['layouts'])} layouts")


if __name__ == "__main__":
    main()

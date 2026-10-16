"""Generate the graph-only-M1 candidate without touching frozen deployments."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.m1_simplification.prepare import digest, semantics
from experiments.v2_core_ablations.audit_layouts import audit as audit_layout
from rcaps.placement import adaptive, static_resource
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.resource_graph import from_topology, layer_dag
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def generate(name: str) -> dict:
    physical, template = scenario_files(name)
    model = TopologyModel(physical)
    state, metadata = adaptive.optimize(
        model, name, fixed_structure=False, evaluator=static_resource.measure)
    spans = adaptive.intervals(model, state)
    resources = from_topology(model)
    dag = layer_dag(resources, spans, (state["stem"][0],))
    metadata["evaluation_owner"] = "M2"
    metadata["M1"] = "physical resource graph and layer-compatible DAG only"
    destination = HERE / "layouts" / name
    record = adaptive.save(model, template, state, destination, metadata,
                           compatibility_dag=dag)
    previous = ROOT / "experiments/m1_simplification/layouts" / name
    old = json.loads((previous / "placement.json").read_text(encoding="utf-8"))
    same_score = abs(record["score"] - old["score"]) <= 1e-12
    same_reference = all(abs(record["reference"][key] -
                             old["reference"][key]) <= 1e-12
                         for key in ("ttft_s", "tpot_s", "bottleneck_s"))
    same_semantics = semantics(record) == semantics(old)
    hashes = {filename: digest(destination / filename) ==
              digest(previous / filename)
              for filename in ("solution.ini", "simulator_cluster.ini")}
    if not (same_score and same_reference and same_semantics and all(hashes.values())):
        raise ValueError(f"Graph candidate differs from audited static search: {name}")
    return {"scenario": name, "M1": "resource graph and compatibility DAG",
            "M2": "unchanged strong static evaluator and adaptive search",
            "gpu_count": len(resources.gpus),
            "physical_directed_edges": len(resources.links),
            "compatibility_edges": len(dag.edges),
            "compatible_paths": dag.path_count(),
            "canonical_suffixes": len(state["branches"]),
            "shared_gpus": len(state["stem"]),
            "shared_layers": state["prefix_layers"],
            "candidate_evaluations": metadata["candidate_evaluations"],
            "planning_s": metadata["planning_s"],
            "static_score": metadata["score"],
            "same_static_score": same_score,
            "same_static_reference": same_reference,
            "same_layout_semantics": same_semantics,
            "same_deployment_sha256": hashes,
            "source_sha256": {
                "resource_graph": digest(ROOT / "rcaps/placement/resource_graph.py"),
                "static_resource": digest(ROOT / "rcaps/placement/static_resource.py"),
                "adaptive": digest(ROOT / "rcaps/placement/adaptive.py")},
            "layout_audit": audit_layout(destination / "solution.ini",
                                         destination / "simulator_cluster.ini", name)}


def main() -> None:
    result = {name: generate(name) for name in ("single", "multi")}
    output = HERE / "layout_audit.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

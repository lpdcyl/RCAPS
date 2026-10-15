"""Build reproducible single-cluster resource pools and V2 placements.

The network is the original complete 1 ms / 1000 mbps single-cluster graph.
Only GPU counts and types vary. All generated artifacts stay in this directory.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from configparser import ConfigParser
from pathlib import Path

from rcaps.placement import adaptive
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "examples/simulation"
COUNTS = {
    "C1": {"A100": 4, "L4": 8, "T4": 12},
    "C2": {"A100": 2, "L4": 10, "T4": 12},
    "C3": {"A100": 6, "L4": 6, "T4": 12},
    "C4": {"A100": 4, "L4": 6, "T4": 8},
    "C5": {"A100": 4, "L4": 10, "T4": 16},
}


def types_for(case: str) -> list[str]:
    original = ConfigParser()
    original.read(BASE / "config/single24.ini")
    kinds = [original[f"ComputeNode-{i}"]["type"] for i in range(24)]
    target = COUNTS[case]
    if case in ("C2", "C3"):
        source, dest = (("A100", "L4") if case == "C2" else ("L4", "A100"))
        indexes = [i for i, kind in enumerate(kinds) if kind == source][-2:]
        for index in indexes:
            kinds[index] = dest
    elif case == "C4":
        keep = {kind: 0 for kind in target}
        selected = []
        for kind in kinds:
            if keep[kind] < target[kind]:
                selected.append(kind)
                keep[kind] += 1
        kinds = selected
    elif case == "C5":
        kinds += ["L4", "L4", "T4", "T4", "T4", "T4"]
    assert dict(Counter(kinds)) == target
    return kinds


def build_files(case: str) -> tuple[Path, Path]:
    kinds = types_for(case)
    out = HERE / "pools" / case
    out.mkdir(parents=True, exist_ok=True)
    physical = ConfigParser()
    physical["NodeNames"] = {"total_compute_nodes": str(len(kinds))}
    all_nodes = list(range(len(kinds)))
    physical["SourceNode"] = {"connected_nodes": repr(all_nodes)}
    physical["SinkNode"] = {"connected_nodes": repr(all_nodes)}
    for i, kind in enumerate(kinds):
        physical[f"ComputeNode-{i}"] = {
            "type": kind,
            "connected_nodes": repr(["source", *[j for j in all_nodes if j != i], "sink"]),
        }
    for i in all_nodes:
        for left, right in (("source", i), (i, "sink")):
            physical[f"Link-{left}-{right}"] = {
                "bandwidth": "1000 * mbps", "latency": "1 * MilliSec"}
    for i in all_nodes:
        for j in range(i + 1, len(kinds)):
            physical[f"Link-{i}-{j}"] = {
                "bandwidth": "1000 * mbps", "latency": "1 * MilliSec"}
    physical_path = out / "physical.ini"
    with physical_path.open("w", encoding="utf-8") as stream:
        physical.write(stream)

    original = ConfigParser()
    original.read(BASE / "layouts/ilp/simulator_cluster.ini")
    template = ConfigParser()
    template["Coordinator"] = dict(original["Coordinator"])
    template["MachineTypes"] = dict(original["MachineTypes"])
    template["ComputeNodes"] = {"names": repr([f"compute_node_{i+2}" for i in all_nodes])}
    examples = {}
    for section in original.sections():
        if section.startswith("compute_node_"):
            kind = ast.literal_eval(original[section]["machine_type"])
            examples.setdefault(kind, dict(original[section]))
    for i, kind in enumerate(kinds):
        template[f"compute_node_{i+2}"] = examples[kind].copy()
    template["Links"] = {"names": "[]"}
    template_path = out / "template.ini"
    with template_path.open("w", encoding="utf-8") as stream:
        template.write(stream)
    return physical_path, template_path


def plan(case: str) -> dict:
    physical, template = build_files(case)
    model = TopologyModel(physical)
    summary = {"case": case, "counts": model.machine_counts,
               "capacities": {kind: model.manager.get_max_num_layers(kind)
                              for kind in model.machine_counts},
               "total_layer_capacity": sum(model.capacity.values()),
               "model_layers": model.layers,
               "network": "complete, 1 ms, 1000 mbps per link"}
    for name, branch_counts in (("adaptive", (2, 3)), ("fixed_branches", (2,))):
        state, metrics = adaptive.optimize(
            model, "single", fixed_structure=False, branch_counts=branch_counts,
            use_frozen_reference=False)
        dest = HERE / "layouts" / case / name
        record = adaptive.save(model, template, state, dest, metrics)
        summary[name] = {key: record[key] for key in
                         ("stem", "prefix_layers", "branches", "intervals",
                          "score", "candidate_evaluations", "planning_s")}
        summary[name]["total_layer_copies"] = sum(
            end - start for start, end in record["intervals"].values())
    try:
        state, metrics = adaptive.optimize(
            model, "single", fixed_structure=True,
            use_frozen_reference=False)
    except ValueError as error:
        summary["fixed_structure"] = {"status": "infeasible", "reason": str(error)}
    else:
        record = adaptive.save(model, template, state,
                               HERE / "layouts" / case / "fixed_structure", metrics)
        summary["fixed_structure"] = {key: record[key] for key in
                                      ("stem", "prefix_layers", "branches",
                                       "intervals", "score", "candidate_evaluations",
                                       "planning_s")}
        summary["fixed_structure"]["total_layer_copies"] = sum(
            end - start for start, end in record["intervals"].values())
    (HERE / "pools" / case / "plan.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*", choices=COUNTS, default=list(COUNTS))
    args = parser.parse_args()
    for case in args.cases:
        print(json.dumps(plan(case), indent=2), flush=True)

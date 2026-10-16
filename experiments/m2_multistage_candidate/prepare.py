"""Plan and export the four controlled M2 variants in an isolated directory."""

from __future__ import annotations

import argparse
import ast
import json
import math
from configparser import ConfigParser
from pathlib import Path

from rcaps.placement import adaptive, static_resource
from rcaps.placement.partition import scenario as original_scenario
from rcaps.placement.topology import TopologyModel

from .placement import HERE, ROOT, digest, from_legacy, measure, save, validate
from .search import search


CASES = ("C1_single", "C1_multi", "C2", "C3", "C4", "C5")
VARIANTS = ("single_a100", "multi_a100", "single_any", "multi_any")
LOADS = {"C1_single": 700.0, "C1_multi": 320.0,
         "C2": 160.0, "C3": 400.0, "C4": 120.0, "C5": 500.0}


def files(case: str) -> tuple[Path, Path, str]:
    if case == "C1_single":
        physical, template = original_scenario("single")
        return physical, template, "single"
    if case == "C1_multi":
        physical, template = original_scenario("multi")
        return physical, template, "multi"
    source = ROOT / "experiments/v2_resource_generalization/pools" / case
    return source / "physical.ini", source / "template.ini", "single"


def legacy_state(case: str, model: TopologyModel) -> dict:
    if case.startswith("C1_"):
        name = case.removeprefix("C1_")
        path = ROOT / "experiments/m1_graph_candidate/layouts" / name / "placement.json"
    else:
        path = (ROOT / "experiments/v2_resource_generalization/layouts" /
                case / "adaptive/placement.json")
    record = json.loads(path.read_text(encoding="utf-8"))
    state = {"stem": record["stem"], "prefix_layers": record["prefix_layers"],
             "branches": record["branches"],
             "lengths": {int(node): end - start for node, (start, end)
                         in record["intervals"].items()}}
    return from_legacy(state, model)


def reference_state(case: str, model: TopologyModel, seed_state: dict) -> dict:
    if case.startswith("C1_"):
        return from_legacy(adaptive.reference_state(
            model, case.removeprefix("C1_")), model)
    return seed_state


def _audit_export(destination: Path, expected: dict) -> dict:
    solution = ConfigParser()
    simulator = ConfigParser()
    if not solution.read(destination / "solution.ini") or not simulator.read(
            destination / "simulator_cluster.ini"):
        raise ValueError("Exported deployment file is missing")
    exported_spans = {}
    for node, encoded in solution["Solution"].items():
        layers = ast.literal_eval(encoded)
        if layers != list(range(layers[0], layers[-1] + 1)):
            raise ValueError("Noncontiguous exported GPU layers")
        exported_spans[int(node.removeprefix("compute_node_")) - 2] = (
            layers[0], layers[-1] + 1)
    if exported_spans != expected["spans"]:
        raise ValueError("Exported layer intervals differ from M1 DAG")
    edges = set()
    for name in ast.literal_eval(simulator["Links"]["names"]):
        link = simulator[name]
        left, right = link["in"], link["out"]
        edges.add(("source" if left == "source" else
                   int(left.removeprefix("compute_node_")) - 2,
                   "sink" if right == "sink" else
                   int(right.removeprefix("compute_node_")) - 2))
    if edges != expected["dag"].edge_set:
        raise ValueError("Exported deployment edges differ from M1 DAG")
    return {"exported_edges": len(edges), "exported_layers": len(exported_spans),
            "checked": True}


def plan(case: str) -> dict:
    physical, template, topology = files(case)
    if not physical.is_file() or not template.is_file():
        raise FileNotFoundError(f"Missing resource pool files for {case}")
    model = TopologyModel(physical)
    seed = legacy_state(case, model)
    reference = reference_state(case, model, seed)
    legacy_static = static_resource.measure(model, {
        "stem": seed["segments"][0]["replicas"][0],
        "prefix_layers": seed["segments"][0]["end"],
        "branches": seed["segments"][1]["replicas"],
        "lengths": seed["lengths"]})
    translated = measure(model, seed)
    score_parity = {key: math.isclose(legacy_static[key], translated[key],
                                     rel_tol=1e-12, abs_tol=1e-10)
                    for key in ("ttft_s", "tpot_s", "bottleneck_s")}
    if not all(score_parity.values()):
        raise ValueError(f"Legacy static score changed for {case}: {score_parity}")
    result = {"case": case, "topology": topology, "offered_tokens_per_s": LOADS[case],
              "physical_source": str(physical.relative_to(ROOT)).replace("\\", "/"),
              "physical_sha256": digest(physical),
              "template_sha256": digest(template),
              "score_parity": score_parity,
              "reference": measure(model, reference),
              "variants": {}}
    for restriction in ("a100", "any"):
        outcome = search(model, reference, a100_prefix=restriction == "a100",
                         seed_state=seed)
        for mode in ("single", "multi"):
            label = f"{mode}_{restriction}"
            item = outcome[mode]
            if item["status"] != "feasible":
                result["variants"][label] = item
                continue
            destination = HERE / "layouts" / case / label
            metadata = {key: value for key, value in item.items()
                        if key not in ("state", "status")}
            metadata["status"] = "feasible"
            metadata["search_wall_s"] = outcome["search_wall_s"]
            record = save(model, template, item["state"], destination, metadata)
            checked = validate(model, item["state"])
            result["variants"][label] = {
                "status": "feasible", "score": item["score"],
                "widths": record["widths"],
                "boundaries": [part["end"] for part in item["state"]["segments"][:-1]],
                "layer_copies": record["layer_copies"],
                "active_gpus": record["active_gpus"],
                "idle_gpus": record["idle_gpus"],
                "compatible_paths": record["compatible_paths"],
                "candidate_evaluations": item["candidate_evaluations"],
                "search_wall_s": outcome["search_wall_s"],
                "solution_sha256": record["solution_sha256"],
                "sim_cluster_sha256": record["sim_cluster_sha256"],
                "deployment_audit": _audit_export(destination, checked),
                "failure_counts": item["initialization"]["failure_counts"]}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    cases = (args.case,) if args.case else CASES
    result = {case: plan(case) for case in cases}
    output = HERE / "offline_audit.json"
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    existing.update(result)
    output.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    for case in cases:
        print(case, {name: (item["status"], item.get("widths"), item.get("score"))
                     for name, item in result[case]["variants"].items()}, flush=True)
    print(output)


if __name__ == "__main__":
    main()

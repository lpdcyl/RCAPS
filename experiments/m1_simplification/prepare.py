"""Generate isolated static-M1 layouts and audit their execution graphs."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

from experiments.v2_core_ablations.audit_layouts import audit as audit_layout
from rcaps.placement import adaptive, static_resource
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCENARIOS = ("single", "multi")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantics(record: dict) -> dict:
    return {key: record[key] for key in
            ("stem", "prefix_layers", "branches", "intervals")}


def compatible_path_count(cluster_path: Path, record: dict, layers: int) -> int:
    """Count exported source-to-sink paths with contiguous layer coverage."""
    config = ConfigParser()
    if not config.read(cluster_path):
        raise FileNotFoundError(cluster_path)
    spans = {f"compute_node_{int(node) + 2}": pair
             for node, pair in record["intervals"].items()}
    links: dict[str, list[str]] = {}
    for name in ast.literal_eval(config["Links"]["names"]):
        link = config[name]
        links.setdefault(link["in"], []).append(link["out"])

    @lru_cache(None)
    def paths(node: str, boundary: int) -> int:
        if node == "sink":
            return int(boundary == layers)
        total = 0
        for next_node in links.get(node, []):
            if next_node == "sink":
                total += paths(next_node, boundary)
            else:
                start, end = spans[next_node]
                if start <= boundary < end:
                    total += paths(next_node, end)
        return total

    return paths("source", 0)


def generate(scenario: str) -> dict:
    physical, template = scenario_files(scenario)
    model = TopologyModel(physical)
    original_state, original_metadata = adaptive.optimize(
        model, scenario, fixed_structure=False)
    frozen = json.loads((ROOT / "rcaps/v2_layouts" /
                         f"{scenario}_adaptive/placement.json").read_text(encoding="utf-8"))
    if semantics({"stem": original_state["stem"],
                  "prefix_layers": original_state["prefix_layers"],
                  "branches": original_state["branches"],
                  "intervals": {str(node): list(pair) for node, pair in
                                adaptive.intervals(model, original_state).items()}}) != semantics(frozen):
        raise ValueError(f"Default V2 search changed: {scenario}")
    state, metadata = adaptive.optimize(
        model, scenario, fixed_structure=False, evaluator=static_resource.measure)
    metadata["evaluation_model"] = "static_heterogeneous_normalized_suffixes"
    metadata["metric_interpretation"] = {
        "ttft_s": "isolated prefill route cost proxy, not online TTFT prediction",
        "tpot_s": "isolated decode route cost proxy, not online TPOT prediction",
        "bottleneck_s": "equal-suffix-weighted resource burden proxy"}
    destination = HERE / "layouts" / scenario
    record = adaptive.save(model, template, state, destination, metadata)
    solution = destination / "solution.ini"
    cluster = destination / "simulator_cluster.ini"
    layout_audit = audit_layout(solution, cluster, scenario)
    path_count = compatible_path_count(cluster, record, model.layers)
    if path_count < len(state["branches"]):
        raise ValueError(f"Too few online compatible paths: {scenario}")
    previous = ROOT / "experiments/v2_method_comparisons/layouts/static_resource" / scenario
    previous_record = json.loads((previous / "placement.json").read_text(encoding="utf-8"))
    return {"scenario": scenario, "evaluation_model": metadata["evaluation_model"],
            "default_v2_search_unchanged": True,
            "structure": {"shared_gpus": len(state["stem"]),
                          "shared_layers": state["prefix_layers"],
                          "suffixes": len(state["branches"]),
                          "model_layer_copies": sum(
                              end - start for start, end in
                              adaptive.intervals(model, state).values()),
                          "online_compatible_path_count": path_count},
            "search": {key: metadata[key] for key in
                       ("score", "candidate_evaluations", "planning_s")},
            "frozen_v2_search": {key: original_metadata[key] for key in
                                 ("score", "candidate_evaluations", "planning_s")},
            "layout_audit": layout_audit,
            "legacy_static_comparison": {
                "same_structure": semantics(record) == semantics(previous_record),
                "same_solution_sha256": digest(solution) == digest(previous / "solution.ini"),
                "same_sim_cluster_sha256": digest(cluster) == digest(previous / "simulator_cluster.ini"),
                "legacy_solution_sha256": digest(previous / "solution.ini"),
                "legacy_sim_cluster_sha256": digest(previous / "simulator_cluster.ini")}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS,
                        default=list(SCENARIOS))
    args = parser.parse_args()
    output = {scenario: generate(scenario) for scenario in args.scenarios}
    (HERE / "layout_audit.json").write_text(json.dumps(output, indent=2) + "\n",
                                            encoding="utf-8")
    print(HERE / "layout_audit.json")


if __name__ == "__main__":
    main()

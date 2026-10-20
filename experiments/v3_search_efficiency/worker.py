"""Run one fresh-process planning trial without changing either planner."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import time
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import patch

from rcaps.v3.placement import normalize, save, validate
from rcaps.v3.resource_graph import LayerCompatibilityDag, from_topology
from rcaps.v3.search import search
from rcaps.v3.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "rcaps/v3/planning_inputs.json"
RELEASE = ROOT / "experiments/v3_release/manifest.json"
HELIX = {
    "C1_single": {
        "directory": ROOT / "artifact_evaluation/single_cluster",
        "script": ROOT / "artifact_evaluation/single_cluster/step2_gen_layout.py",
        "physical": ROOT / "artifact_evaluation/single_cluster/config/cluster24.ini",
        "profile": ROOT / "artifact_evaluation/single_cluster/config/machine_profiles.ini",
        "warm_start": ROOT / "artifact_evaluation/single_cluster/layout_llama70b/petals/petals_sol.ini",
    },
    "C1_multi": {
        "directory": ROOT / "artifact_evaluation/distributed_clusters",
        "script": ROOT / "artifact_evaluation/distributed_clusters/step2_gen_layout.py",
        "physical": ROOT / "artifact_evaluation/distributed_clusters/config/3cluster24.ini",
        "profile": ROOT / "artifact_evaluation/distributed_clusters/config/machine_profiles.ini",
        "warm_start": ROOT / "artifact_evaluation/distributed_clusters/layout_llama70b/swarm/swarm_sol.ini",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _node(name: str) -> int | str:
    if name in ("source", "sink"):
        return name
    return int(name.removeprefix("compute_node_")) - 2


def audit_export(case: str, solution: Path, simulator: Path) -> dict:
    """Validate the exported layer spans and every deployed logical edge."""
    item = json.loads(INPUTS.read_text(encoding="utf-8"))[case]
    model = TopologyModel(ROOT / item["physical"])
    physical = from_topology(model)
    placement = ConfigParser()
    links_ini = ConfigParser()
    if not placement.read(solution) or not links_ini.read(simulator):
        raise ValueError("Missing exported deployment INI")
    spans = {}
    for name, encoded in placement["Solution"].items():
        layers = ast.literal_eval(encoded)
        if not layers or layers != list(range(layers[0], layers[-1] + 1)):
            raise ValueError(f"Non-contiguous model layers on {name}")
        node = _node(name)
        spans[node] = (layers[0], layers[-1] + 1)
        if node not in model.capacity or len(layers) > model.capacity[node]:
            raise ValueError(f"Layer capacity exceeded on {name}")
    edges = []
    for name in ast.literal_eval(links_ini["Links"]["names"]):
        link = links_ini[name]
        left, right = _node(link["in"]), _node(link["out"])
        if (left, right) not in physical.links:
            raise ValueError(f"Missing physical link {left}->{right}")
        if left == "source":
            valid = right in spans and spans[right][0] == 0
        elif right == "sink":
            valid = left in spans and spans[left][1] == model.layers
        else:
            valid = (left in spans and right in spans and
                     spans[right][0] <= spans[left][1] < spans[right][1])
        if not valid:
            raise ValueError(f"Incompatible layer edge {left}->{right}")
        edges.append((left, right))
    dag = LayerCompatibilityDag(spans, tuple(edges), model.layers)
    valid = len(dag.edge_set) == len(dag.edges) and dag.path_count() > 0
    return {"valid": valid,
            "invalid_reason": None if valid else "No unique complete deployment path",
            "active_gpus": len(spans), "deployed_edges": len(edges),
            "complete_paths": dag.path_count(),
            "solution_sha256": sha256(solution),
            "sim_cluster_sha256": sha256(simulator)}


def run_v3(case: str, output: Path) -> dict:
    item = json.loads(INPUTS.read_text(encoding="utf-8"))[case]
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    physical, template = ROOT / item["physical"], ROOT / item["template"]
    if sha256(physical) != item["physical_sha256"] or \
            sha256(template) != item["template_sha256"]:
        raise ValueError("Frozen V3 input hash mismatch")
    if sha256(physical) != sha256(HELIX[case]["physical"]):
        raise ValueError("V3 and Helix physical cluster files differ")
    started = time.perf_counter()
    model = TopologyModel(physical)
    seed = normalize(item["seed_state"])
    reference = normalize(item["reference_state"])
    validate(model, seed)
    validate(model, reference)
    prepared = time.perf_counter()
    outcome = search(model, reference, a100_prefix=False, seed_state=seed)
    searched = time.perf_counter()
    candidate = outcome["multi"]
    if candidate["status"] != "feasible":
        raise ValueError("V3 multi_any search returned no feasible layout")
    metadata = {key: value for key, value in candidate.items()
                if key not in ("state", "status")}
    metadata.update({"version": "RCAPS V3", "candidate_variant": "multi_any",
                     "case": case})
    saved = save(model, template, candidate["state"], output, metadata)
    audited = audit_export(case, output / "solution.ini",
                           output / "simulator_cluster.ini")
    if not audited["valid"]:
        raise ValueError(audited["invalid_reason"])
    total = time.perf_counter() - started
    expected = release["layouts"]["single" if case == "C1_single" else "multi"]
    for key in ("solution_sha256", "sim_cluster_sha256"):
        if audited[key] != expected[key]:
            raise ValueError(f"V3 output differs from frozen release: {key}")
    return {"status": "passed", "method": "v3", "case": case,
            "prep_wall_s": prepared - started,
            "search_wall_s": searched - prepared,
            "search_internal_wall_s": outcome["search_wall_s"],
            "export_and_audit_wall_s": total - (searched - started),
            "total_wall_s": total,
            "candidate_evaluations": candidate["candidate_evaluations"],
            "common_evaluations": candidate["common_evaluations"],
            "additional_evaluations": candidate["additional_evaluations"],
            "score": candidate["score"], "widths": saved["widths"],
            "input_sha256": sha256(physical), "release_parity": True,
            "deployment": audited}


def run_helix(case: str, output: Path, solver_budget_s: int | None = None) -> dict:
    """Call the artifact's original 70B entry point with its own fixed policy."""
    from simulator.initial_layout.ilp_layout.ilp_layout import ILPLayout
    import importlib.util

    cfg = HELIX[case]
    item = json.loads(INPUTS.read_text(encoding="utf-8"))[case]
    if sha256(cfg["physical"]) != item["physical_sha256"]:
        raise ValueError("V3 and Helix physical cluster files differ")
    spec = importlib.util.spec_from_file_location("helix_original_step2", cfg["script"])
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    stage_times = {}
    model_stats = {}
    originals = {}
    patchers = []
    for name in ("from_ini", "build_model", "search_layout",
                 "load_and_verify_solution", "generate_simulator_cluster",
                 "save_layout_solution"):
        original = getattr(ILPLayout, name)
        originals[name] = original

        def timed(self, *args, _name=name, _original=original, **kwargs):
            stage_start = time.perf_counter()
            try:
                if _name == "search_layout" and solver_budget_s is not None:
                    # Experimental anytime checkpoint. All other original
                    # Helix model, warm start, callback and stopping rules stay.
                    self.ilp_model.Params.TimeLimit = solver_budget_s
                result = _original(self, *args, **kwargs)
                if _name == "build_model":
                    model_stats["build_counts"] = result
                if _name == "search_layout":
                    mip = self.ilp_model
                    model_stats.update({
                        "solver_status": int(mip.Status),
                        "solver_runtime_s": float(mip.Runtime),
                        "solution_count": int(mip.SolCount),
                        "variables": int(mip.NumVars),
                        "constraints": int(mip.NumConstrs),
                    })
                    if mip.SolCount:
                        model_stats.update({"objective": float(mip.ObjVal),
                                            "objective_bound": float(mip.ObjBound),
                                            "mip_gap": float(mip.MIPGap)})
                return result
            finally:
                stage_times[_name] = stage_times.get(_name, 0.0) + (
                    time.perf_counter() - stage_start)

        patchers.append(patch.object(ILPLayout, name, timed))
    previous = Path.cwd()
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        os.chdir(cfg["directory"])
        for patcher in patchers:
            patcher.start()
        try:
            module.ilp_layout70b(str(output))
        finally:
            for patcher in reversed(patchers):
                patcher.stop()
    finally:
        os.chdir(previous)
    total = time.perf_counter() - started
    audited = audit_export(case, output / "ilp_sol.ini",
                           output / "simulator_cluster.ini")
    return {"status": "passed" if audited["valid"] else "invalid_deployment",
            "method": "helix_ilp_budgeted" if solver_budget_s else "helix_ilp",
            "solver_budget_s": solver_budget_s, "case": case,
            "total_wall_s": total, "stage_wall_s": stage_times,
            "model": model_stats, "input_sha256": sha256(cfg["physical"]),
            "profile_sha256": sha256(cfg["profile"]),
            "heuristic_sha256": sha256(cfg["warm_start"]),
            "original_script_sha256": sha256(cfg["script"]),
            "deployment": audited}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=tuple(HELIX), required=True)
    parser.add_argument("--method", choices=("v3", "helix_ilp",
                                             "helix_ilp_budgeted"), required=True)
    parser.add_argument("--solver-budget-s", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to((ROOT / "rcaps/v3_layouts").resolve()) or \
            output.is_relative_to((ROOT / "artifact_evaluation").resolve()):
        parser.error("Output must not overwrite released or original layouts")
    if args.method == "helix_ilp_budgeted" and not args.solver_budget_s:
        parser.error("budgeted Helix requires --solver-budget-s")
    result = (run_v3(args.case, output) if args.method == "v3" else
              run_helix(args.case, output,
                        args.solver_budget_s if args.method == "helix_ilp_budgeted"
                        else None))
    write_json(output / "result.json", result)
    print(json.dumps({"status": result["status"], "method": args.method,
                      "case": args.case, "total_wall_s": result["total_wall_s"]}))


if __name__ == "__main__":
    main()

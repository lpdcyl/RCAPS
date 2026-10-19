"""Sweep V3 grouping beam width and per-stage scoring budget in child processes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from experiments.m2_multistage_candidate.prepare import (
    _audit_export, files, initial_state, reference_state,
)
from experiments.v3_release.verify import digest, snapshot
from rcaps.v3 import placement, search
from rcaps.v3.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = ("C1_single", "C1_multi")
SETTINGS = ((64, 500), (32, 500), (128, 500), (64, 250), (64, 1000),
            (128, 1000))


def label(beam: int, budget: int) -> str:
    return f"beam{beam}_budget{budget}"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def released() -> dict:
    saved = json.loads((ROOT / "experiments/v3_release/manifest.json").read_text(
        encoding="utf-8"))
    if snapshot() != saved:
        raise ValueError("Frozen V3 release manifest changed")
    return saved


def run_one(case: str, beam: int, budget: int) -> dict:
    manifest = released()
    physical, template, scenario = files(case)
    model = TopologyModel(physical)
    seed = initial_state(case, model)
    reference = reference_state(case, model, seed)
    reference_metrics = placement.measure(model, reference)
    with patch.object(search, "BEAM_WIDTH", beam), patch.object(
            search, "STAGE_BUDGET", budget):
        result = search.search(model, reference, a100_prefix=False,
                               seed_state=seed)
    candidate = result.get("multi")
    if not candidate or candidate["status"] != "feasible":
        raise ValueError(f"Search did not produce a feasible multi_any layout: {case}")
    state = candidate["state"]
    checked = placement.validate(model, state)
    destination = HERE / "layouts" / case / label(beam, budget)
    metadata = {"case": case, "beam_width": beam, "stage_budget": budget,
                "score": candidate["score"], "metrics": candidate["metrics"],
                "reference": candidate["reference"],
                "common_evaluations": candidate["common_evaluations"],
                "additional_evaluations": candidate["additional_evaluations"],
                "candidate_evaluations": candidate["candidate_evaluations"],
                "search_wall_s": result["search_wall_s"],
                "extension_s": candidate["extension_s"],
                "initialization": candidate["initialization"]}
    saved = placement.save(model, template, state, destination, metadata)
    exported = _audit_export(destination, checked)
    record = {"case": case, "scenario": scenario, "beam_width": beam,
              "stage_budget": budget, "status": "feasible",
              "physical_sha256": digest(physical),
              "template_sha256": digest(template),
              "reference": reference_metrics,
              "score": candidate["score"], "metrics": candidate["metrics"],
              "state_signature": placement.signature(state),
              "widths": saved["widths"],
              "boundaries": [part["end"] for part in state["segments"][:-1]],
              "layer_copies": saved["layer_copies"],
              "active_gpus": saved["active_gpus"],
              "idle_gpus": saved["idle_gpus"],
              "compatible_paths": saved["compatible_paths"],
              "compatibility_edges": saved["compatibility_edges"],
              "common_evaluations": candidate["common_evaluations"],
              "additional_evaluations": candidate["additional_evaluations"],
              "candidate_evaluations": candidate["candidate_evaluations"],
              "search_wall_s": result["search_wall_s"],
              "extension_s": candidate["extension_s"],
              "failure_counts": candidate["initialization"]["failure_counts"],
              "deployment_audit": exported,
              "solution_sha256": saved["solution_sha256"],
              "sim_cluster_sha256": saved["sim_cluster_sha256"],
              "placement_source": (destination / "placement.json").relative_to(ROOT).as_posix(),
              "placement_sha256": digest(destination / "placement.json")}
    if (beam, budget) == (64, 500):
        original = manifest["layouts"]["single" if case == "C1_single" else "multi"]
        historical_case = json.loads((ROOT / "experiments/m2_multistage_candidate/offline_audit.json").read_text(
            encoding="utf-8"))[case]
        historical = historical_case["variants"]["multi_any"]
        for key in ("solution_sha256", "sim_cluster_sha256"):
            if record[key] != original[key] or record[key] != historical[key]:
                raise ValueError(f"Default search deployment differs from V3: {case}/{key}")
        if abs(record["score"] - historical["score"]) > 1e-10:
            raise ValueError(f"Default search score differs from V3: {case}")
        for key in ("ttft_s", "tpot_s", "bottleneck_s"):
            if abs(record["reference"][key] - historical_case["reference"][key]) > 1e-10:
                raise ValueError(f"Default reference differs from V3: {case}/{key}")
        record["release_parity"] = True
    write_json(HERE / "planning" / case / f"{label(beam, budget)}.json", record)
    return record


def sweep() -> None:
    released()
    for case in CASES:
        for beam, budget in SETTINGS:
            cmd = [sys.executable, "-m", "experiments.v3_search_sensitivity.plan",
                   "one", "--case", case, "--beam", str(beam),
                   "--budget", str(budget)]
            subprocess.run(cmd, cwd=ROOT, check=True)
    records = {case: {label(beam, budget): json.loads((
        HERE / "planning" / case / f"{label(beam, budget)}.json").read_text(
            encoding="utf-8")) for beam, budget in SETTINGS} for case in CASES}
    write_json(HERE / "planning_index.json", {
        "release_manifest_sha256": digest(ROOT / "experiments/v3_release/manifest.json"),
        "search_sha256": digest(ROOT / "rcaps/v3/search.py"),
        "placement_sha256": digest(ROOT / "rcaps/v3/placement.py"),
        "cases": records})
    print(HERE / "planning_index.json", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("one", "sweep"))
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--beam", type=int)
    parser.add_argument("--budget", type=int)
    args = parser.parse_args()
    if args.command == "sweep":
        sweep()
    else:
        if args.case is None or (args.beam, args.budget) not in SETTINGS:
            parser.error("one requires --case and a predefined --beam/--budget pair")
        row = run_one(args.case, args.beam, args.budget)
        print(args.case, label(args.beam, args.budget), row["score"],
              row["widths"], row["candidate_evaluations"], flush=True)


if __name__ == "__main__":
    main()

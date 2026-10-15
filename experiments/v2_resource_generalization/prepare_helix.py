"""Regenerate the Helix Petals warm start and ILP layout per GPU pool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulator.event_simulator.utils import mbps
from simulator.initial_layout.layout_synthesizer import LayoutMethod, LayoutSynthesizer
from simulator.model_manager.model_manager import ModelName

from .prepare import BASE, COUNTS, HERE


def build(case: str, *, max_run_time: int, numeric: bool = False,
          petals_only: bool = False) -> None:
    physical = HERE / "pools" / case / "physical.ini"
    profile = BASE / "config/machine_profile.ini"
    if not physical.exists():
        raise FileNotFoundError(physical)
    warm = HERE / "layouts" / case / "petals"
    dest = HERE / "layouts" / case / ("helix_numeric" if numeric else "helix")
    if dest.joinpath("ilp_sol.ini").exists():
        print(f"skip {case}: {dest}", flush=True)
        return
    warm.mkdir(parents=True, exist_ok=True)
    petals = LayoutSynthesizer(str(physical), str(profile), ModelName.LLaMa70B,
                               str(warm), LayoutMethod.Petals, COUNTS[case])
    if not (warm / "petals_sol.ini").exists():
        petals.synthesize({"seed": 0, "max_out_links_per_node": sum(COUNTS[case].values())})
    if petals_only:
        print(f"done Petals warm start {case}", flush=True)
        return
    dest.mkdir(parents=True, exist_ok=True)
    ilp = LayoutSynthesizer(str(physical), str(profile), ModelName.LLaMa70B,
                           str(dest), LayoutMethod.ILP, COUNTS[case])
    if numeric:
        original_search = ilp.layout_synthesizer.search_layout

        def tuned_search(**kwargs):
            solver = ilp.layout_synthesizer.ilp_model
            solver.Params.NumericFocus = 3
            solver.Params.IntFeasTol = 1e-9
            return original_search(**kwargs)

        ilp.layout_synthesizer.search_layout = tuned_search
    ilp.synthesize({
        "seed": 0, "enable_pruning": False, "min_keep": 12, "max_keep": 12,
        "keep_bandwidth_threshold": 1 * mbps,
        "use_existing_sol": False, "allow_partial_inference": False,
        "remove_redundant": True, "max_run_time": max_run_time,
        "early_stop_time": 30, "early_stop_threshold": 0.95,
        "existing_sol_path": "unused", "start_from_heuristic": True,
        "heuristic_sol_path": str(warm / "petals_sol.ini"),
    })
    (dest / "provenance.json").write_text(json.dumps({
        "physical": str(physical), "counts": COUNTS[case],
        "warm_start": str(warm / "petals_sol.ini"),
        "max_run_time_s": max_run_time,
        "allow_partial_inference": False, "remove_redundant": True,
        "enable_pruning": False,
        "numeric_focus": 3 if numeric else None,
        "int_feas_tol": 1e-9 if numeric else None,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"done {case}: {dest}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=COUNTS)
    parser.add_argument("--max-run-time", type=int, default=120)
    parser.add_argument("--numeric", action="store_true")
    parser.add_argument("--petals-only", action="store_true")
    args = parser.parse_args()
    build(args.case, max_run_time=args.max_run_time,
          numeric=args.numeric, petals_only=args.petals_only)

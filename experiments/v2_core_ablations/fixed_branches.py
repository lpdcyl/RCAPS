"""V2 search with exactly two suffixes and otherwise adaptive structure."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from rcaps.placement import adaptive
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel


HERE = Path(__file__).resolve().parent


def optimize(model: TopologyModel, scenario: str, max_steps: int = 16) -> tuple[dict, dict]:
    started = time.perf_counter()
    reference = adaptive.measure(model, adaptive.reference_state(model, scenario))
    candidates = [state for state in adaptive.initial_states(model, fixed_structure=False)
                  if len(state["branches"]) == 2]
    if not candidates:
        raise ValueError("No feasible two-suffix V2 candidate")
    evaluations = 0
    ranked = []
    for state in candidates:
        metrics = adaptive.measure(model, state)
        evaluations += 1
        ranked.append((adaptive.objective(metrics, reference), state, metrics))
    current_score, state, current = min(ranked, key=lambda item: item[0])
    trace = [{"step": 0, "score": current_score,
              "move": "best feasible two-suffix initializer"}]
    for step in range(1, max_steps + 1):
        best = None
        for move, candidate in adaptive.neighbors(model, state, allow_prefix=True):
            if len(candidate["branches"]) != 2:
                continue
            try:
                adaptive.intervals(model, candidate)
                metrics = adaptive.measure(model, candidate)
            except ValueError:
                continue
            evaluations += 1
            score = adaptive.objective(metrics, reference)
            if score < current_score - 1e-9 and (best is None or score < best[0]):
                best = (score, move, candidate, metrics)
        if best is None:
            break
        current_score, move, state, current = best
        trace.append({"step": step, "score": current_score, "move": move})
    if len(state["branches"]) != 2:
        raise AssertionError("Two-suffix constraint not preserved")
    return state, {"reference": reference, "metrics": current,
                   "score": current_score, "trace": trace,
                   "shortlisted_candidates": len(candidates),
                   "candidate_evaluations": evaluations,
                   "planning_s": time.perf_counter() - started,
                   "constraint": "exactly_two_suffixes"}


def run(scenario: str) -> dict:
    physical, template = scenario_files(scenario)
    model = TopologyModel(physical)
    state, metrics = optimize(model, scenario)
    destination = HERE / "layouts" / "fixed_branches" / scenario
    record = adaptive.save(model, template, state, destination, metrics)
    print(json.dumps({key: record[key] for key in
                      ("stem", "prefix_layers", "branches", "score",
                       "candidate_evaluations", "planning_s")}, indent=2))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    run(parser.parse_args().scenario)

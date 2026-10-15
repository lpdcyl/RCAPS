"""Independent offline model and search alternatives for RCAPS V2.

The original V2 implementation and its saved layouts are never modified.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from rcaps.placement import adaptive
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
VARIANTS = ("static_resource", "beam_search")


def signature(state: dict) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def static_measure(model: TopologyModel, state: dict) -> dict:
    """Static heterogeneity model without inter-request event dependencies."""
    paths = [adaptive.stages(model, state, branch) for branch in state["branches"]]
    prompt_paths = []
    decode_paths = []
    demand = defaultdict(float)
    for path in paths:
        prompt_paths.append(sum(
            stage["prefill_s"] + stage["incoming_latency_s"] +
            stage["payload_bytes"] * model.prompt_tokens / stage["incoming_bytes_per_s"]
            for stage in path))
        decode_paths.append(sum(
            stage["decode_s"] + stage["incoming_latency_s"] +
            stage["payload_bytes"] / stage["incoming_bytes_per_s"]
            for stage in path))
    # Six representative requests use canonical suffixes in round-robin order.
    # Resource demand is additive, while ordering and queue dependencies are absent.
    for index in range(len(adaptive.ARRIVALS)):
        for stage in paths[index % len(paths)]:
            demand[f"link:{stage['incoming_link']}"] += (
                stage["payload_bytes"] * model.prompt_tokens /
                stage["incoming_bytes_per_s"] +
                8 * stage["payload_bytes"] / stage["incoming_bytes_per_s"])
            if stage["device"] != "sink":
                demand[f"gpu:{stage['device']}"] += (
                    stage["prefill_s"] + 8 * stage["decode_s"])
    bottleneck = max(demand, key=demand.get)
    return {"ttft_s": max(prompt_paths),
            "tpot_s": max(decode_paths),
            "bottleneck_s": demand[bottleneck],
            "bottleneck_resource": bottleneck}


def static_resource_search(model: TopologyModel, scenario: str) -> tuple[dict, dict]:
    """Run the complete V2 structural search using the static resource model."""
    started = time.perf_counter()
    reference = static_measure(model, adaptive.reference_state(model, scenario))
    candidates = adaptive.initial_states(model, fixed_structure=False)
    evaluations = 0
    scoring_s = 0.0

    def evaluate(state: dict) -> tuple[float, dict]:
        nonlocal evaluations, scoring_s
        begin = time.perf_counter()
        metrics = static_measure(model, state)
        scoring_s += time.perf_counter() - begin
        evaluations += 1
        return adaptive.objective(metrics, reference), metrics

    ranked = [(evaluate(state), signature(state), state) for state in candidates]
    (score, metrics), _, selected = min(ranked, key=lambda item: (item[0][0], item[1]))
    trace = [{"step": 0, "score": score, "move": "best static-model initializer"}]
    for step in range(1, 17):
        best = None
        for move, candidate in adaptive.neighbors(model, selected, allow_prefix=True):
            try:
                adaptive.intervals(model, candidate)
                candidate_score, candidate_metrics = evaluate(candidate)
            except ValueError:
                continue
            row = (candidate_score, signature(candidate), move, candidate, candidate_metrics)
            if candidate_score < score - 1e-9 and (best is None or row[:2] < best[:2]):
                best = row
        if best is None:
            break
        score, _, move, selected, metrics = best
        trace.append({"step": step, "score": score, "move": move})
    return selected, {"reference": reference, "metrics": metrics,
                      "score": score, "trace": trace,
                      "shortlisted_candidates": len(candidates),
                      "candidate_evaluations": evaluations,
                      "scoring_s": scoring_s,
                      "planning_s": time.perf_counter() - started,
                      "alternative": "static heterogeneous resource model"}


def beam_search(model: TopologyModel, scenario: str) -> tuple[dict, dict]:
    """Width-four, 16-round beam search with the original V2 event-DAG score."""
    started = time.perf_counter()
    official = json.loads((ROOT / "rcaps" / "v2_layouts" /
                           f"{scenario}_adaptive" / "placement.json").read_text(
                               encoding="utf-8"))
    budget = int(official["candidate_evaluations"])
    reference = adaptive.measure(model, adaptive.reference_state(model, scenario))
    initial = adaptive.initial_states(model, fixed_structure=False)
    if len(initial) > budget:
        raise ValueError("Official evaluation budget cannot score every initializer")
    scored = {}
    scoring_s = 0.0

    def evaluate(state: dict) -> tuple[float, dict] | None:
        nonlocal scoring_s
        key = signature(state)
        if key in scored:
            return scored[key][0], scored[key][1]
        if len(scored) >= budget:
            return None
        start = time.perf_counter()
        metrics = adaptive.measure(model, state)
        scoring_s += time.perf_counter() - start
        score = adaptive.objective(metrics, reference)
        scored[key] = (score, metrics, state)
        return score, metrics

    for state in initial:
        evaluate(state)
    rank = lambda row: (row[0], row[1])
    frontier = sorted(((value[0], key, value[2]) for key, value in scored.items()),
                      key=rank)[:4]
    trace = [{"round": 0, "best_score": frontier[0][0],
              "evaluated": len(scored)}]
    for round_id in range(1, 17):
        next_states = {key: (score, key, state) for score, key, state in frontier}
        for _, _, state in frontier:
            candidates = sorted(adaptive.neighbors(model, state, allow_prefix=True),
                                key=lambda item: (item[0], signature(item[1])))
            for _, candidate in candidates:
                try:
                    adaptive.intervals(model, candidate)
                    result = evaluate(candidate)
                except ValueError:
                    continue
                if result is None:
                    break
                key = signature(candidate)
                next_states[key] = (result[0], key, candidate)
            if len(scored) >= budget:
                break
        replacement = sorted(next_states.values(), key=rank)[:4]
        trace.append({"round": round_id, "best_score": replacement[0][0],
                      "evaluated": len(scored)})
        if [row[1] for row in replacement] == [row[1] for row in frontier]:
            break
        frontier = replacement
        if len(scored) >= budget:
            break
    best_key, best = min(scored.items(), key=lambda item: (item[1][0], item[0]))
    return best[2], {"reference": reference, "metrics": best[1],
                     "score": best[0], "trace": trace,
                     "shortlisted_candidates": len(initial),
                     "candidate_evaluations": len(scored),
                     "evaluation_budget": budget,
                     "beam_width": 4, "max_rounds": 16,
                     "scoring_s": scoring_s,
                     "planning_s": time.perf_counter() - started,
                     "alternative": "bounded event-DAG beam search",
                     "selected_signature": best_key}


def generate(scenario: str, variant: str) -> Path:
    if scenario not in ("single", "multi") or variant not in VARIANTS:
        raise ValueError((scenario, variant))
    cluster, template = scenario_files(scenario)
    model = TopologyModel(cluster)
    state, metadata = (static_resource_search(model, scenario) if variant ==
                       "static_resource" else beam_search(model, scenario))
    destination = HERE / "layouts" / variant / scenario
    adaptive.save(model, template, state, destination, metadata)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    args = parser.parse_args()
    print(generate(args.scenario, args.variant))


if __name__ == "__main__":
    main()

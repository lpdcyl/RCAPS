"""Select placements with three evaluators from an identical V2 candidate pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from rcaps.placement import adaptive
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EVALUATORS = ("compute_only", "compute_comm", "event_dag")


def signature(state: dict) -> str:
    return json.dumps({"stem": state["stem"],
                       "prefix_layers": state["prefix_layers"],
                       "branches": state["branches"],
                       "lengths": sorted((int(k), v) for k, v in state["lengths"].items())},
                      sort_keys=True, separators=(",", ":"))


def official_state(scenario: str) -> dict:
    path = ROOT / "rcaps" / "v2_layouts" / f"{scenario}_adaptive" / "placement.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    spans = {int(node): pair for node, pair in record["intervals"].items()}
    return {"stem": record["stem"], "prefix_layers": record["prefix_layers"],
            "branches": record["branches"],
            "lengths": {node: end - start for node, (start, end) in spans.items()}}


def candidate_pool(model: TopologyModel, scenario: str) -> tuple[list[dict], dict]:
    initial = adaptive.initial_states(model, fixed_structure=False)
    official = official_state(scenario)
    pool = {}
    origins = {}
    for index, state in enumerate([*initial, official]):
        origin = "official" if index == len(initial) else f"initializer_{index}"
        for label, candidate in [("self", state),
                                 *adaptive.neighbors(model, state, allow_prefix=True)]:
            try:
                adaptive.intervals(model, candidate)
            except ValueError:
                continue
            key = signature(candidate)
            pool.setdefault(key, candidate)
            origins.setdefault(key, []).append(f"{origin}:{label}")
    return [pool[key] for key in sorted(pool)], origins


def static_metrics(model: TopologyModel, state: dict, *, communication: bool) -> dict:
    prompt, decode = [], []
    for branch in state["branches"]:
        path = adaptive.stages(model, state, branch)
        prompt.append(sum(stage["prefill_s"] +
                          (stage["incoming_latency_s"] +
                           stage["payload_bytes"] * model.prompt_tokens /
                           stage["incoming_bytes_per_s"] if communication else 0)
                          for stage in path))
        decode.append(sum(stage["decode_s"] +
                          (stage["incoming_latency_s"] +
                           stage["payload_bytes"] /
                           stage["incoming_bytes_per_s"] if communication else 0)
                          for stage in path))
    return {"prompt_s": max(prompt), "decode_s": max(decode)}


def score_static(metrics: dict, reference: dict) -> float:
    return (0.40 * metrics["prompt_s"] / reference["prompt_s"] +
            0.35 * metrics["decode_s"] / reference["decode_s"])


def run(scenario: str) -> dict:
    started = time.perf_counter()
    physical, template = scenario_files(scenario)
    model = TopologyModel(physical)
    states, origins = candidate_pool(model, scenario)
    ref_state = adaptive.reference_state(model, scenario)
    refs = {"compute_only": static_metrics(model, ref_state, communication=False),
            "compute_comm": static_metrics(model, ref_state, communication=True),
            "event_dag": adaptive.measure(model, ref_state)}
    official_id = hashlib.sha256(signature(official_state(scenario)).encode()).hexdigest()[:16]
    entries = []
    score_time = {name: 0.0 for name in EVALUATORS}
    for state in states:
        key = signature(state)
        row = {"id": hashlib.sha256(key.encode()).hexdigest()[:16],
               "state": state, "family": [len(state["stem"]), len(state["branches"])],
               "origins": origins[key], "scores": {}, "metrics": {}}
        for evaluator in EVALUATORS:
            t0 = time.perf_counter()
            if evaluator == "event_dag":
                metrics = adaptive.measure(model, state)
                score = adaptive.objective(metrics, refs[evaluator])
            else:
                metrics = static_metrics(model, state,
                                         communication=evaluator == "compute_comm")
                score = score_static(metrics, refs[evaluator])
            score_time[evaluator] += time.perf_counter() - t0
            row["scores"][evaluator] = score
            row["metrics"][evaluator] = metrics
        entries.append(row)
    selected = {}
    output = HERE / "layouts" / "modeling" / scenario
    for evaluator in EVALUATORS:
        winner = min(entries, key=lambda row: (
            round(row["scores"][evaluator], 9),
            row["id"] != official_id, row["id"]))
        selected[evaluator] = winner["id"]
        destination = output / evaluator
        adaptive.save(model, template, winner["state"], destination,
                      {"experiment": "fixed_candidate_pool_modeling_ablation",
                       "candidate_id": winner["id"],
                       "evaluator": evaluator,
                       "score": winner["scores"][evaluator],
                       "candidate_count": len(entries)})
    family_examples = {}
    for row in entries:
        family = tuple(row["family"])
        family_examples.setdefault(family, []).append(row)
    diagnostics = []
    for family, options in sorted(family_examples.items()):
        diagnostics.append(min(options, key=lambda row: row["id"])["id"])
    if official_id not in diagnostics:
        diagnostics.append(official_id)
    manifest = {"scenario": scenario, "candidate_pool_rule":
                "V2 initial states plus one-step legal neighbors plus official layout and its neighbors",
                "candidate_count": len(entries), "selected_ids": selected,
                "official_id": official_id, "diagnostic_ids": diagnostics,
                "reference_metrics": refs, "scoring_wall_s": score_time,
                "total_planning_wall_s": time.perf_counter() - started,
                "entries": entries}
    manifest_path = HERE / "modeling_candidates" / f"{scenario}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scenario": scenario, "candidate_count": len(entries),
                      "selected_ids": selected, "official_id": official_id,
                      "diagnostic_ids": diagnostics,
                      "scoring_wall_s": score_time}, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    run(parser.parse_args().scenario)

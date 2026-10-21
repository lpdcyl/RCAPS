"""Retrospective Pareto and weight-sensitivity audit of the frozen V3 M2 score.

This reuses the fixed candidate pool from selection_manifest.json. It does not
search for layouts, inspect online outcomes, or change the released V3 method.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from experiments.v3_joint_routing_candidate.joint import case_inputs
from rcaps.v3.placement import WEIGHTS, digest, measure

from .diagnose import HERE, ROOT


KEYS = ("ttft_s", "tpot_s", "bottleneck_s")
GRID_STEP = 0.05
LOCAL_RADIUS = 0.10
EPSILON = 1e-9


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dominates(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
    return (all(x <= y + EPSILON for x, y in zip(left, right))
            and any(x < y - EPSILON for x, y in zip(left, right)))


def winner(rows: list[dict], weights: tuple[float, ...], baseline: str) -> str:
    scored = [(sum(w * x for w, x in zip(weights, row["normalized"])), row)
              for row in rows]
    floor = min(score for score, _ in scored)
    ties = [row for score, row in scored if score <= floor + EPSILON]
    return min(ties, key=lambda row: (row["label"] != baseline,
                                      row["label"]))["label"]


def grid() -> list[tuple[float, float, float]]:
    # Integer coordinates avoid a drifted or incomplete simplex grid.
    return [(i / 20, j / 20, (20 - i - j) / 20)
            for i in range(21) for j in range(21 - i)]


def run() -> dict:
    manifest = read(HERE / "selection_manifest.json")
    references = read(ROOT / "rcaps/v3/planning_inputs.json")
    result = {
        "scope": "retrospective fixed-candidate audit, no new search or online simulation",
        "candidate_manifest": "selection_manifest.json",
        "weights": list(WEIGHTS),
        "component_order": list(KEYS),
        "grid_step": GRID_STEP,
        "local_component_radius": LOCAL_RADIUS,
        "tie_epsilon": EPSILON,
        "cases": {},
    }
    for case, entry in manifest["cases"].items():
        model, physical, template = case_inputs(case)
        if (digest(physical) != entry["physical_sha256"] or
                digest(template) != entry["template_sha256"]):
            raise ValueError(f"Topology/template changed: {case}")
        reference = measure(model, references[case]["reference_state"])
        baseline = f"rcaps/v3_layouts/{'single' if case == 'C1_single' else 'multi'}"
        rows = []
        for candidate in entry["candidates"]:
            path = ROOT / candidate["label"]
            if (digest(path / "solution.ini") != candidate["solution_sha256"] or
                    digest(path / "simulator_cluster.ini") !=
                    candidate["sim_cluster_sha256"]):
                raise ValueError(f"Deployment changed: {path}")
            state = read(path / "placement.json")["state"]
            metrics = measure(model, state)
            normalized = tuple(metrics[key] / reference[key] for key in KEYS)
            score = sum(w * x for w, x in zip(WEIGHTS, normalized))
            if abs(score - candidate["weighted_score"]) > EPSILON:
                raise ValueError(f"Stored score changed: {path}")
            rows.append({"label": candidate["label"],
                         "normalized": normalized,
                         "raw_metrics": {key: metrics[key] for key in KEYS},
                         "bottleneck_resource": metrics["bottleneck_resource"],
                         "score": score})

        front = {row["label"] for row in rows if not any(
            dominates(other["normalized"], row["normalized"])
            for other in rows if other is not row)}
        weights = grid()
        local = [weight for weight in weights if all(
            abs(w - center) <= LOCAL_RADIUS + 1e-12
            for w, center in zip(weight, WEIGHTS))]
        all_winners = Counter(winner(rows, weight, baseline) for weight in weights)
        local_winners = Counter(winner(rows, weight, baseline) for weight in local)
        chosen = winner(rows, WEIGHTS, baseline)
        if chosen != entry["weighted_selected"]:
            raise ValueError(f"Default winner changed: {case}")
        chosen_row = next(row for row in rows if row["label"] == chosen)
        distinct_scores = sorted({round(row["score"], 12) for row in rows})
        result["cases"][case] = {
            "reference_metrics": {key: reference[key] for key in KEYS},
            "baseline": baseline,
            "default_winner": chosen,
            "default_winner_on_pareto_front": chosen in front,
            "baseline_on_pareto_front": baseline in front,
            "default_winner_normalized": list(chosen_row["normalized"]),
            "default_winner_contributions": [
                w * x for w, x in zip(WEIGHTS, chosen_row["normalized"])],
            "default_score_gap_to_next_distinct": (
                distinct_scores[1] - distinct_scores[0]
                if len(distinct_scores) > 1 else None),
            "pareto_front": sorted(front),
            "grid_size": len(weights),
            "local_grid_size": len(local),
            "all_grid_winners": dict(all_winners),
            "local_grid_winners": dict(local_winners),
            "candidates": rows,
        }
    path = HERE / "objective_audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return result


if __name__ == "__main__":
    audit = run()
    for case, item in audit["cases"].items():
        print(case)
        print("  front:", *item["pareto_front"], sep="\n    ")
        print("  local:", item["local_grid_winners"])
        print("  full:", item["all_grid_winners"])

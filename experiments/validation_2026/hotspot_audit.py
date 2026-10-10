"""Audit offline resource-demand ranks against measured online profile fields.

This is a retrospective diagnostic, not a trained predictor or a placement
result. In particular, route visits are read from the same online run only to
explain ranking errors and must not be used to choose that run's placement.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from rcaps.placement.partition import scenario
from rcaps.placement.path_ensemble import measure as ensemble_measure
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def average_ranks(values: dict[int, float]) -> dict[int, float]:
    ordered = sorted(values, key=lambda node: (-values[node], node))
    ranks: dict[int, float] = {}
    index = 0
    while index < len(ordered):
        stop = index + 1
        while stop < len(ordered) and abs(values[ordered[stop]] -
                                           values[ordered[index]]) <= 1e-12:
            stop += 1
        rank = (index + 1 + stop) / 2
        for node in ordered[index:stop]:
            ranks[node] = rank
        index = stop
    return ranks


def spearman(first: dict[int, float], second: dict[int, float]) -> float:
    left, right = average_ranks(first), average_ranks(second)
    nodes = sorted(first)
    a, b = mean(left.values()), mean(right.values())
    numerator = sum((left[node] - a) * (right[node] - b) for node in nodes)
    left_sum = sum((left[node] - a) ** 2 for node in nodes)
    right_sum = sum((right[node] - b) ** 2 for node in nodes)
    return numerator / (left_sum * right_sum) ** 0.5


def placement_state(layout: Path) -> dict:
    data = json.loads((layout / "placement.json").read_text(encoding="utf-8"))
    shared = data["shared"]
    return {"shared": shared,
            "shared_length": data["intervals"][str(shared)][1],
            "paths": data["branches"],
            "lengths": {int(node): end - start
                        for node, (start, end) in data["intervals"].items()
                        if int(node) != shared}}


def canonical_gpu_demand(model: TopologyModel, state: dict) -> dict[int, float]:
    demand = {node: 0.0 for node in model.types}
    for path in state["paths"]:
        for stage in model._stages(state, path):
            if stage["device"] == "sink":
                continue
            node = int(stage["device"])
            demand[node] += max(stage["prefill_s"] / model.prompt_tokens,
                                stage["decode_s"] / model.decode_batch)
    return demand


def profile_values(row: dict, field: str, nodes: dict[int, str]) -> dict[int, float]:
    return {node: row[field].get(f"Compute-{node + 2}", 0.0) for node in nodes}


def visit_fraction(row: dict, nodes: dict[int, str]) -> dict[int, float]:
    total = sum(row["route_counts"].values())
    if not total:
        raise ValueError("No assigned routes")
    visits = {node: 0 for node in nodes}
    for route, count in row["route_counts"].items():
        for uid in (int(part) for part in route.split("-")):
            node = uid - 2
            if node in visits:
                visits[node] += count
    return {node: count / total for node, count in visits.items()}


def audit() -> dict:
    output = {}
    for name in ("single", "multi"):
        model = TopologyModel(scenario(name)[0])
        output[name] = {}
        for arm in ("rcaps_coarse", "rcaps"):
            layout = (ROOT / "rcaps/variant_layouts" / f"{name}_coarse"
                      if arm == "rcaps_coarse" else ROOT / "rcaps/layouts" / name)
            state = placement_state(layout)
            canonical = canonical_gpu_demand(model, state)
            ensemble = ensemble_measure(model, state).gpu_demand_s
            max_demand = max(canonical.values())
            tied_top = [node for node in canonical
                        if abs(canonical[node] - max_demand) <= 1e-12]
            rows = []
            for seed in (0, 1, 2):
                path = HERE / "runs70b" / name / f"seed{seed}" / f"{arm}.json"
                run = json.loads(path.read_text(encoding="utf-8"))
                busy = profile_values(run, "gpu_busy_fraction", model.types)
                queue = profile_values(run, "gpu_queue_request_s", model.types)
                visits = visit_fraction(run, model.types)
                row = {"seed": seed,
                       "trace_sha256": run["trace_sha256"],
                       "canonical_busy_spearman": spearman(canonical, busy),
                       "canonical_queue_spearman": spearman(canonical, queue),
                       "ensemble_busy_spearman": spearman(ensemble, busy),
                       "ensemble_queue_spearman": spearman(ensemble, queue)}
                if name == "multi":
                    row["gpu17"] = {
                        "canonical_demand_rank_with_ties": average_ranks(canonical)[17],
                        "busy_rank": average_ranks(busy)[17],
                        "queue_rank": average_ranks(queue)[17],
                        "assigned_route_visit_fraction": visits[17]}
                rows.append(row)
            output[name][arm] = {
                "canonical_max_demand_s": max_demand,
                "canonical_tied_top_gpus": tied_top,
                "seeds": rows,
                "mean_correlations": {
                    key: mean(row[key] for row in rows)
                    for key in ("canonical_busy_spearman",
                                "canonical_queue_spearman",
                                "ensemble_busy_spearman",
                                "ensemble_queue_spearman")}}
    return output


if __name__ == "__main__":
    result = audit()
    target = HERE / "hotspot_audit.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(target)

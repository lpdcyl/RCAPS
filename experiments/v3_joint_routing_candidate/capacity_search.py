"""Bounded M2 search over multi-level shapes using a shared-resource LP.

The shape grid and beam are fixed before any online validation.  Each valid
candidate is checked by the M1 legality graph, then evaluated with the same
class mix and physical GPU/link/NIC constraints.  This returns a shortlist,
not a global optimum certificate.
"""

from __future__ import annotations

import json
import itertools
import time
from collections import Counter
from types import SimpleNamespace

from rcaps.v3.placement import measure, save, signature, validate
from rcaps.v3.search import assignments, build

from .capacity import solve, workload_classes
from .joint import HERE, ROOT, case_inputs, read, relative, write
from .joint_capacity import BASE, train_trace


BOUNDARIES_SINGLE = (32, 40, 48, 56)
WIDTHS_SINGLE = (2, 3, 4)
BOUNDARIES_MULTI = ((16, 40), (24, 48), (32, 48),
                    (40, 56), (48, 64))
WIDTHS_MULTI = ((2, 1), (3, 1), (2, 2), (3, 2), (4, 2), (4, 3))
GROUPS_PER_SHAPE = 2
KEEP = 3


def shapes(layers: int):
    for boundary in BOUNDARIES_SINGLE:
        if boundary < layers:
            for width in WIDTHS_SINGLE:
                yield (boundary,), (1, width)
    for boundaries in BOUNDARIES_MULTI:
        if boundaries[-1] < layers:
            for second in WIDTHS_MULTI:
                yield boundaries, (1, *second)


def requirements(layers: int, boundaries: tuple[int, ...],
                 widths: tuple[int, ...]):
    positions = (0, *boundaries, layers)
    return [end - start for start, end, width in
            zip(positions, positions[1:], widths) for _ in range(width)]


def a100_seed_groups(model, required: list[int]):
    """Ensure the finite beam also tests physically plausible fast stems."""
    fast = [gpu for gpu, kind in sorted(model.types.items()) if kind == "A100"]
    options = []
    for count in range(1, len(fast) + 1):
        for prefix in itertools.combinations(fast, count):
            if sum(model.capacity[gpu] for gpu in prefix) < required[0]:
                continue
            remaining = {gpu: kind for gpu, kind in model.types.items()
                         if gpu not in prefix}
            subset = SimpleNamespace(types=remaining,
                                     capacity={gpu: model.capacity[gpu]
                                               for gpu in remaining})
            for tails in assignments(subset, required[1:],
                                     a100_prefix=False,
                                     keep=GROUPS_PER_SHAPE):
                options.append((prefix, *tails))
        if options:
            break
    return options[:4]


def run(case: str):
    model, _, template = case_inputs(case)
    classes = workload_classes(train_trace(case, "uniform"))
    started = time.perf_counter()
    seen = set()
    records = []
    failures = Counter()
    for boundaries, widths in shapes(model.layers):
        required = requirements(model.layers, boundaries, widths)
        if sum(required) > sum(model.capacity.values()):
            failures["capacity_lower_bound"] += 1
            continue
        groups = assignments(model, required, a100_prefix=False,
                             keep=GROUPS_PER_SHAPE)
        groups.extend(a100_seed_groups(model, required))
        groups = list(dict.fromkeys(groups))
        if not groups:
            failures["beam_infeasible"] += 1
        for group in groups:
            state = build(model, boundaries, widths, group)
            if state is None:
                failures["physical_or_layer_infeasible"] += 1
                continue
            key = signature(state)
            if key in seen:
                continue
            seen.add(key)
            checked = validate(model, state)
            lp = solve(model, template, state, classes)
            if not lp["success"]:
                failures[f"lp_status_{lp['status']}"] += 1
                continue
            static = measure(model, state)
            records.append({"boundaries": boundaries, "widths": widths,
                            "capacity_requests_per_s": lp["requests_per_s"],
                            "static_ttft_s": static["ttft_s"],
                            "static_tpot_s": static["tpot_s"],
                            "bottleneck": lp["bottlenecks"][0]["resource"],
                            "active_gpus": checked["active_gpus"],
                            "layer_copies": checked["layer_copies"],
                            "signature": key, "state": state})
    records.sort(key=lambda row: (-row["capacity_requests_per_s"],
                                  row["static_tpot_s"], row["static_ttft_s"],
                                  row["signature"]))
    selected = []
    for row in records:
        # Keep structural diversity when the shared stem creates LP ties.
        family = tuple(row["widths"])
        if family in {tuple(item["widths"]) for item in selected}:
            continue
        selected.append(row)
        if len(selected) >= KEEP:
            break
    output = []
    for rank, row in enumerate(selected, 1):
        directory = BASE / "layouts" / case / f"capacity_{rank}"
        saved = save(model, template, row["state"], directory,
                     {"candidate_variant": "capacity_joint_m2",
                      "case": case, "capacity_requests_per_s":
                      row["capacity_requests_per_s"]})
        output.append({"label": f"capacity_{rank}",
                       "layout": relative(directory),
                       "solution_sha256": saved["solution_sha256"],
                       "sim_cluster_sha256": saved["sim_cluster_sha256"],
                       "widths": row["widths"], "boundaries": row["boundaries"],
                       "capacity_requests_per_s": row["capacity_requests_per_s"]})
    summary = {"case": case, "shapes_considered": sum(1 for _ in shapes(model.layers)),
               "legal_layouts_evaluated": len(records),
               "failures": dict(failures),
               "planning_wall_s": time.perf_counter() - started,
               "selected": output,
               "ranked": [{key: value for key, value in row.items()
                           if key != "state"} for row in records]}
    write(BASE / "plans" / f"{case}_capacity_search.json", summary)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("C1_single", "C1_multi"), required=True)
    args = parser.parse_args()
    result = run(args.case)
    print(json.dumps({"case": args.case,
                      "legal_layouts_evaluated": result["legal_layouts_evaluated"],
                      "planning_wall_s": result["planning_wall_s"],
                      "selected": result["selected"]}, ensure_ascii=False))

"""Capacity-only adaptive placement control for the V2 method ablation.

The placement decision reads GPU memory capacity and *existence* of physical
links. Compute profiles, link bandwidth/latency and event-graph scores are not
available to this search. They are read only after selection to export the
ordinary simulator configuration.
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from configparser import ConfigParser
from pathlib import Path

from rcaps.placement.adaptive import (SHORTLIST_PER_FAMILY, assign_branches,
                                      intervals, neighbors, save)
from rcaps.placement.partition import scenario


# These are the 70B model's hard VRAM layer limits in the current simulator.
# Keeping them explicit prevents the decision model from instantiating the
# performance-profile manager used by V2.
LAYER_CAPACITY = {"A100": 12, "L4": 7, "T4": 4}
MODEL_LAYERS = 80


class CapacityTopology:
    """Minimal input surface for a capacity-and-connectivity-only decision."""

    def __init__(self, cluster_file: Path):
        config = ConfigParser()
        if not config.read(cluster_file):
            raise FileNotFoundError(cluster_file)
        self.config = config
        count = len([key for key in config if key.startswith("ComputeNode-")])
        self.types = {node: config[f"ComputeNode-{node}"]["type"]
                      for node in range(count)}
        self.capacity = {node: LAYER_CAPACITY[kind]
                         for node, kind in self.types.items()}
        self.layers = MODEL_LAYERS
        self.edges = set()
        for name in config:
            if name.startswith("Link-"):
                _, left, right = name.split("-", 2)
                self.edges.add(frozenset((left, right)))

    def connected(self, left: str | int, right: str | int) -> bool:
        return frozenset((str(left), str(right))) in self.edges


def order(model: CapacityTopology, nodes: list[int] | tuple[int, ...],
          previous: str | int, *, terminal: bool = True) -> list[int] | None:
    """Find one connected path, preferring larger memory capacity then ID."""
    pending = frozenset(nodes)
    failed = set()

    def visit(current: str | int, remaining: frozenset[int]) -> list[int] | None:
        if not remaining:
            if not terminal or model.connected(current, "sink"):
                return []
            return None
        key = (current, remaining)
        if key in failed:
            return None
        for node in sorted(remaining, key=lambda item: (-model.capacity[item], item)):
            if model.connected(current, node):
                tail = visit(node, remaining - {node})
                if tail is not None:
                    return [node, *tail]
        failed.add(key)
        return None

    return visit(previous, pending)


def allocate(model: CapacityTopology, nodes: list[int], total: int) -> dict[int, int] | None:
    """Balance occupied fractions of each GPU's layer capacity."""
    if not nodes or len(nodes) > total or sum(model.capacity[n] for n in nodes) < total:
        return None
    lengths = {node: 1 for node in nodes}
    for _ in range(total - len(nodes)):
        node = min((n for n in nodes if lengths[n] < model.capacity[n]),
                   key=lambda n: ((lengths[n] + 1) / model.capacity[n], n),
                   default=None)
        if node is None:
            return None
        lengths[node] += 1
    return lengths


def construct(model: CapacityTopology, stem_nodes: tuple[int, ...], p: int,
              groups: list[list[int]]) -> dict | None:
    stem = order(model, stem_nodes, "source", terminal=False)
    if stem is None:
        return None
    branches = [order(model, group, stem[-1]) for group in groups]
    if any(branch is None for branch in branches):
        return None
    lengths = allocate(model, stem, p)
    if lengths is None:
        return None
    for branch in branches:
        assigned = allocate(model, branch, model.layers - p)
        if assigned is None:
            return None
        lengths.update(assigned)
    state = {"stem": stem, "prefix_layers": p,
             "branches": branches, "lengths": lengths}
    try:
        intervals(model, state)
    except ValueError:
        return None
    return state


def score(model: CapacityTopology, state: dict) -> tuple[float, float]:
    fractions = [state["lengths"][node] / model.capacity[node]
                 for node in sorted(model.types)]
    return max(fractions), sum(value * value for value in fractions)


def key(state: dict) -> tuple:
    return (tuple(state["stem"]), state["prefix_layers"],
            tuple(tuple(branch) for branch in state["branches"]),
            tuple(sorted(state["lengths"].items())))


def initial_states(model: CapacityTopology, *, fixed_structure: bool = False) -> tuple[list[dict], int]:
    a100s = tuple(sorted(node for node, kind in model.types.items()
                         if kind == "A100"))
    families = {}
    feasible = 0
    for size in ((1,) if fixed_structure else (1, 2, 3, 4)):
        for shared in itertools.combinations(a100s, size):
            remaining = [n for n in sorted(model.types) if n not in shared]
            for suffix_count in ((2,) if fixed_structure else (2, 3)):
                prefixes = ((model.capacity[shared[0]],) if fixed_structure else
                            range(size, sum(model.capacity[n] for n in shared) + 1))
                for p in prefixes:
                    required = model.layers - p
                    if (required <= 0 or
                            sum(model.capacity[n] for n in remaining) < suffix_count * required):
                        continue
                    for groups in assign_branches(model, remaining, suffix_count, required):
                        state = construct(model, shared, p, groups)
                        if state is not None:
                            feasible += 1
                            families.setdefault((suffix_count, size), []).append(state)
    shortlisted = []
    for family in sorted(families):
        ranked = sorted(families[family], key=lambda state: (score(model, state), key(state)))
        shortlisted.extend(ranked[:SHORTLIST_PER_FAMILY])
    if not shortlisted:
        raise ValueError("No feasible capacity-only adaptive placement")
    return shortlisted, feasible


def optimize(model: CapacityTopology, *, fixed_structure: bool = False,
             max_steps: int = 16) -> tuple[dict, dict]:
    started = time.perf_counter()
    candidates, feasible = initial_states(model, fixed_structure=fixed_structure)
    state = min(candidates, key=lambda item: (score(model, item), key(item)))
    current = score(model, state)
    evaluations = len(candidates)
    trace = [{"step": 0, "score": current, "move": "best capacity-only initializer"}]
    for step in range(1, max_steps + 1):
        best = None
        for move, candidate in neighbors(model, state, allow_prefix=not fixed_structure):
            try:
                intervals(model, candidate)
            except ValueError:
                continue
            evaluations += 1
            candidate_score = score(model, candidate)
            if candidate_score < current and (best is None or
                    (candidate_score, key(candidate)) < (best[0], key(best[2]))):
                best = (candidate_score, move, candidate)
        if best is None:
            break
        current, move, state = best
        trace.append({"step": step, "score": current, "move": move})
    return state, {"capacity_score": current, "trace": trace,
                   "feasible_constructed": feasible,
                   "shortlisted_candidates": len(candidates),
                   "candidate_evaluations": evaluations,
                   "planning_s": time.perf_counter() - started}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, choices=("single", "multi"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--variant", choices=("adaptive", "fixed"), default="adaptive")
    args = parser.parse_args()
    cluster, template = scenario(args.scenario)
    decision_model = CapacityTopology(cluster)
    fixed_structure = args.variant == "fixed"
    state, metadata = optimize(decision_model, fixed_structure=fixed_structure)
    # The ordinary V2 exporter needs profile and link values only to create
    # the simulator input. They play no role in the completed search above.
    from rcaps.placement.topology import TopologyModel
    export_model = TopologyModel(cluster)
    if export_model.layers != decision_model.layers or export_model.capacity != decision_model.capacity:
        raise ValueError("Capacity-only decision limits disagree with simulator")
    record = save(export_model, template, state, args.output_dir,
                  {"algorithm": f"capacity-only {args.variant} structure control", **metadata})
    print(json.dumps({field: record[field] for field in
                      ("stem", "prefix_layers", "branches", "capacity_score",
                       "candidate_evaluations", "planning_s")}, indent=2))


if __name__ == "__main__":
    main()

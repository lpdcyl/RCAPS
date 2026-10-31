"""Bounded deterministic search over one- and two-boundary M2 layouts."""

from __future__ import annotations

import copy
import itertools
import time
from collections import Counter

from rcaps.v3 import placement_utils as adaptive
from rcaps.v3.topology import TopologyModel, profile_at

from .placement_multi import (BEAM_WIDTH, MAX_ACCEPTED_MOVES, STAGE_BUDGET,
                        measure, normalize, objective, signature, validate)


def _shape_requirements(layers: int, boundaries: tuple[int, ...],
                        widths: tuple[int, ...]) -> list[int]:
    positions = (0, *boundaries, layers)
    return [length for start, end, width in zip(positions, positions[1:], widths)
            for length in [end - start] for _ in range(width)]


def assignments(model: TopologyModel, required: list[int], *,
                a100_prefix: bool, keep: int = 2) -> list[tuple[tuple[int, ...], ...]]:
    """Finite-width bin-covering beam; unused GPUs are a legitimate choice."""
    if sum(required) > sum(model.capacity.values()) or len(required) > len(model.types):
        return []
    nodes = sorted(model.types, key=lambda node: (-model.capacity[node], node))
    future_total = [0] * (len(nodes) + 1)
    future_a100 = [0] * (len(nodes) + 1)
    for index in range(len(nodes) - 1, -1, -1):
        node = nodes[index]
        future_total[index] = future_total[index + 1] + model.capacity[node]
        future_a100[index] = future_a100[index + 1] + (
            model.capacity[node] if model.types[node] == "A100" else 0)
    empty = tuple(() for _ in required)
    beam = [(empty, (0,) * len(required))]
    for index, node in enumerate(nodes):
        capacity = model.capacity[node]
        possibilities = []
        for bins, caps in beam:
            for target in range(-1, len(required)):
                new_caps = list(caps)
                new_bins = list(bins)
                if target >= 0:
                    if caps[target] >= required[target]:
                        continue
                    new_caps[target] += capacity
                    new_bins[target] = (*bins[target], node)
                deficits = [max(0, need - cap)
                            for need, cap in zip(required, new_caps)]
                if sum(deficits) > future_total[index + 1]:
                    continue
                if any(deficit > future_total[index + 1] for deficit in deficits):
                    continue
                # Oversupply matters only after covering every replica. The
                # deficit dominates early decisions, while deterministic GPU
                # IDs stabilize ties across repeated planning runs.
                overfill = sum(max(0, cap - need) for cap, need
                               in zip(new_caps, required))
                rank = (sum(value * value for value in deficits),
                        overfill, sum(len(group) for group in new_bins),
                        tuple(new_bins))
                possibilities.append((rank, tuple(new_bins), tuple(new_caps)))
        possibilities.sort(key=lambda item: item[0])
        seen = set()
        beam = []
        for _, bins, caps in possibilities:
            if bins in seen:
                continue
            seen.add(bins)
            beam.append((bins, caps))
            if len(beam) >= BEAM_WIDTH:
                break
        if not beam:
            return []
    complete = [bins for bins, caps in beam
                if all(cap >= need for cap, need in zip(caps, required))]
    return complete[:keep]


def _order(model: TopologyModel, nodes: tuple[int, ...],
           previous: tuple[int | str, ...], *, terminal: bool) -> list[int] | None:
    options = []
    for start in nodes:
        if not any(adaptive.has_link(model, left, start) for left in previous):
            continue
        rest = adaptive.route_order(model, [node for node in nodes if node != start],
                                    start, terminal=False)
        if rest is None:
            continue
        route = [start, *rest]
        if terminal and not adaptive.has_link(model, route[-1], "sink"):
            continue
        cost = min(adaptive.link_cost(model, left, start) for left in previous)
        cost += sum(adaptive.link_cost(model, left, right)
                    for left, right in zip(route, route[1:]))
        options.append((cost, route))
    return min(options, key=lambda item: (item[0], item[1]))[1] if options else None


def build(model: TopologyModel, boundaries: tuple[int, ...],
          widths: tuple[int, ...], bins: tuple[tuple[int, ...], ...]) -> dict | None:
    positions = (0, *boundaries, model.layers)
    segments = []
    lengths = {}
    at = 0
    previous = ("source",)
    for level, (start, end, width) in enumerate(zip(positions, positions[1:], widths)):
        replicas = []
        for _ in range(width):
            group = bins[at]
            at += 1
            route = _order(model, group, previous,
                           terminal=end == model.layers)
            if route is None:
                return None
            allocation = adaptive.allocate(model, route, end - start)
            if allocation is None:
                return None
            lengths.update(allocation)
            replicas.append(route)
        segments.append({"start": start, "end": end, "replicas": replicas})
        previous = tuple(replica[-1] for replica in replicas)
    state = {"segments": segments, "lengths": lengths}
    try:
        validate(model, state)
    except ValueError:
        return None
    return state


def build_ordered(model: TopologyModel, boundaries: tuple[int, ...],
                  widths: tuple[int, ...], bins: tuple[tuple[int, ...], ...],
                  *, first_fastest: bool = False) -> dict | None:
    """Greedy chain variant; order the first GPU by profiled service cost."""
    if not first_fastest:
        return build(model, boundaries, widths, bins)
    positions = (0, *boundaries, model.layers)
    segments, lengths = [], {}
    previous = ("source",)
    at = 0
    for start, end, width in zip(positions, positions[1:], widths):
        replicas = []
        for _ in range(width):
            group = bins[at]
            at += 1
            choices = []
            for entry in group:
                if not adaptive.has_link(model, previous[0], entry):
                    continue
                rest = adaptive.route_order(model, [n for n in group if n != entry], entry, terminal=False)
                if rest is None:
                    continue
                route = [entry, *rest]
                if end == model.layers and not adaptive.has_link(model, route[-1], "sink"):
                    continue
                allocation = adaptive.allocate(model, route, end-start)
                if allocation is None:
                    continue
                estimate = sum(length * (0.4 * profile_at(model.profiles[model.types[node]].prompt_bs2time,
                    model.prompt_tokens) + 0.35 * profile_at(model.profiles[model.types[node]].decode_bs2time,
                    model.decode_batch)) for node, length in allocation.items())
                choices.append((estimate, route, allocation))
            if not choices:
                return None
            _, route, allocation = min(choices, key=lambda x: (x[0], x[1]))
            lengths.update(allocation)
            replicas.append(route)
        segments.append(dict(start=start, end=end, replicas=replicas))
        previous = tuple(replica[-1] for replica in replicas)
    state = dict(segments=segments, lengths=lengths)
    try:
        validate(model, state)
    except ValueError:
        return None
    return state


def cheap_cost(model: TopologyModel, state: dict) -> float:
    """Initialization rank only; final selection always uses full M2 score."""
    segment_costs = []
    for segment in state["segments"]:
        replicas = []
        for replica in segment["replicas"]:
            cost = 0.0
            for node in replica:
                profile = model.profiles[model.types[node]]
                length = state["lengths"][node]
                cost += length * (0.40 * profile_at(profile.prompt_bs2time,
                                                   model.prompt_tokens) +
                                  0.35 * profile_at(profile.decode_bs2time,
                                                   model.decode_batch))
            replicas.append(cost)
        segment_costs.append(max(replicas))
    return sum(segment_costs) + 0.002 * sum(state["lengths"].values())


def _shapes(layers: int, *, multistage: bool):
    grid = range(4, layers, 4)
    if not multistage:
        for boundary in grid:
            for first in (1, 2, 3, 4):
                for count in (1, 2, 3, 4):
                    if max(first, count) > 1:
                        yield (boundary,), (first, count)
    else:
        for first, second in itertools.combinations(grid, 2):
            for first_width in (1, 2, 3, 4):
                for middle in (1, 2, 3, 4):
                    for last in (1, 2, 3, 4):
                        if len({first_width, middle, last}) > 1:
                            yield (first, second), (first_width, middle, last)


def _noshare_shapes(layers: int, *, multistage: bool):
    """Same shape grid, but require an initial width above one."""
    for boundaries, widths in _shapes(layers, multistage=multistage):
        if widths[0] > 1:
            yield boundaries, widths


def initial_states(model: TopologyModel, *, a100_prefix: bool,
                   multistage: bool, no_share_only: bool = False) -> tuple[list[dict], dict]:
    failures = Counter()
    by_family = {}
    shapes = _noshare_shapes if no_share_only else _shapes
    for boundaries, widths in shapes(model.layers, multistage=multistage):
        required = _shape_requirements(model.layers, boundaries, widths)
        if sum(required) > sum(model.capacity.values()):
            failures["capacity_lower_bound"] += 1
            continue
        grouped = assignments(model, required,
                              a100_prefix=a100_prefix)
        if not a100_prefix:
            grouped.extend(assignments(model, required, a100_prefix=True))
            grouped = list(dict.fromkeys(grouped))
        if not grouped:
            failures["assignment_infeasible"] += 1
            continue
        feasible = []
        for bins in grouped:
            state = build(model, boundaries, widths, bins)
            if state is None:
                failures["chain_or_link_infeasible"] += 1
            else:
                feasible.append((cheap_cost(model, state), signature(state), state))
        if not feasible:
            continue
        for candidate in feasible:
            first_gpus = [replica[0] for replica in candidate[2]["segments"][0]["replicas"]]
            prefix_class = ("A100" if all(model.types[node] == "A100" for node in first_gpus)
                            else "other")
            family = (widths, prefix_class if not a100_prefix else "A100")
            by_family.setdefault(family, []).append(candidate)
    # Shape diversity is preserved before the expensive static evaluation.
    selected = []
    for family in sorted(by_family):
        ranked = sorted(by_family[family])[:(16 if a100_prefix else 8)]
        selected.extend(item[2] for item in ranked)
    return selected, {"failure_counts": dict(failures),
                      "feasible_families": len(by_family),
                      "initial_candidates": len(selected)}


def _reallocate(model: TopologyModel, candidate: dict) -> dict | None:
    lengths = {}
    for segment in candidate["segments"]:
        required = segment["end"] - segment["start"]
        for replica in segment["replicas"]:
            allocation = adaptive.allocate(model, replica, required)
            if allocation is None:
                return None
            lengths.update(allocation)
    candidate["lengths"] = lengths
    try:
        validate(model, candidate)
    except ValueError:
        return None
    return candidate


def neighbors(model: TopologyModel, state: dict):
    """Fixed-shape local refinements; width changes enter via initial states."""
    segments = state["segments"]
    for boundary in range(len(segments) - 1):
        for direction in (-1, 1):
            candidate = copy.deepcopy(state)
            left, right = candidate["segments"][boundary:boundary + 2]
            if left["end"] + direction <= left["start"] or right["end"] <= right["start"] + direction:
                continue
            left["end"] += direction
            right["start"] += direction
            result = _reallocate(model, candidate)
            if result is not None:
                yield f"boundary{boundary}{direction:+d}", result
    for level, segment in enumerate(segments):
        for replica_index, replica in enumerate(segment["replicas"]):
            for position in range(len(replica) - 1):
                left, right = replica[position:position + 2]
                for donor, receiver in ((left, right), (right, left)):
                    if (state["lengths"][donor] <= 1 or
                            state["lengths"][receiver] >= model.capacity[receiver]):
                        continue
                    candidate = copy.deepcopy(state)
                    candidate["lengths"][donor] -= 1
                    candidate["lengths"][receiver] += 1
                    try:
                        validate(model, candidate)
                    except ValueError:
                        continue
                    yield f"layer{donor}->{receiver}", candidate
                candidate = copy.deepcopy(state)
                route = candidate["segments"][level]["replicas"][replica_index]
                route[position:position + 2] = [right, left]
                result = _reallocate(model, candidate)
                if result is not None:
                    yield f"swap{left}<->{right}", result
            if len(replica) > 1:
                for node in replica:
                    candidate = copy.deepcopy(state)
                    candidate["segments"][level]["replicas"][replica_index].remove(node)
                    result = _reallocate(model, candidate)
                    if result is not None:
                        yield f"idle{node}", result
            used = set(state["lengths"])
            for idle in sorted(set(model.types) - used):
                candidate = copy.deepcopy(state)
                candidate["segments"][level]["replicas"][replica_index].append(idle)
                result = _reallocate(model, candidate)
                if result is not None:
                    yield f"add{idle}", result
    # Move or swap whole GPUs between replica buckets.
    positions = [(level, index) for level, segment in enumerate(segments)
                 for index in range(len(segment["replicas"]))]
    for (left_level, left_index), (right_level, right_index) in itertools.combinations(positions, 2):
        left = segments[left_level]["replicas"][left_index]
        right = segments[right_level]["replicas"][right_index]
        for old in left:
            for new in right:
                candidate = copy.deepcopy(state)
                a = candidate["segments"][left_level]["replicas"][left_index]
                b = candidate["segments"][right_level]["replicas"][right_index]
                a[a.index(old)] = new
                b[b.index(new)] = old
                result = _reallocate(model, candidate)
                if result is not None:
                    yield f"exchange{old}<->{new}", result
        if len(left) > 1:
            for node in left:
                candidate = copy.deepcopy(state)
                a = candidate["segments"][left_level]["replicas"][left_index]
                b = candidate["segments"][right_level]["replicas"][right_index]
                a.remove(node)
                b.append(node)
                result = _reallocate(model, candidate)
                if result is not None:
                    yield f"move{node}", result


def _improve(model: TopologyModel, candidates: list[dict], reference: dict,
             incumbent: tuple[float, dict, dict] | None,
             cache: dict[str, tuple[float, dict]], budget: int,
             a100_prefix: bool) -> tuple[tuple[float, dict, dict] | None, int, list[dict]]:
    evaluations = 0
    family_best = {}
    ranked = sorted(((cheap_cost(model, state), signature(state), state)
                     for state in candidates), key=lambda item: (item[0], item[1]))
    for _, key, state in ranked[:160]:
        if a100_prefix and any(model.types[node] != "A100"
                               for replica in state["segments"][0]["replicas"] for node in replica):
            continue
        if evaluations >= budget:
            break
        if key not in cache:
            metrics = measure(model, state)
            cache[key] = (objective(metrics, reference), metrics)
            evaluations += 1
        score, metrics = cache[key]
        family = tuple(len(segment["replicas"]) for segment in state["segments"])
        if family not in family_best or score < family_best[family][0]:
            family_best[family] = (score, state, metrics)
        if incumbent is None or score < incumbent[0] - 1e-9:
            incumbent = (score, state, metrics)
    trace = []
    if incumbent is None:
        return None, evaluations, trace
    starts = [incumbent]
    for candidate in sorted(family_best.values(), key=lambda item: item[0]):
        if signature(candidate[1]) != signature(incumbent[1]):
            starts.append(candidate)
        if len(starts) >= 3:
            break
    allowance = max(1, (budget - evaluations) // len(starts))
    for start_index, start in enumerate(starts):
        local = start
        local_limit = min(budget, evaluations + allowance)
        for step in range(MAX_ACCEPTED_MOVES):
            if evaluations >= local_limit:
                break
            best = None
            for move, state in neighbors(model, local[1]):
                if a100_prefix and any(model.types[node] != "A100"
                                       for replica in state["segments"][0]["replicas"] for node in replica):
                    continue
                key = signature(state)
                if key not in cache:
                    if evaluations >= local_limit:
                        break
                    metrics = measure(model, state)
                    cache[key] = (objective(metrics, reference), metrics)
                    evaluations += 1
                score, metrics = cache[key]
                if score < local[0] - 1e-9 and (best is None or score < best[0]):
                    best = (score, state, metrics, move)
            if best is None:
                break
            local = best[:3]
            trace.append({"start": start_index, "step": step + 1,
                          "move": best[3], "score": best[0]})
            if local[0] < incumbent[0] - 1e-9:
                incumbent = local
    return incumbent, evaluations, trace


def search(model: TopologyModel, reference: dict, *,
           a100_prefix: bool, seed_state: dict | None = None,
           no_share_only: bool = False) -> dict:
    """A common 500-score phase, then equal-budget single/multi extensions."""
    started = time.perf_counter()
    reference_metrics = measure(model, reference)
    single_states, single_info = initial_states(
        model, a100_prefix=a100_prefix, multistage=False, no_share_only=no_share_only)
    if not single_states and seed_state is None:
        return {"status": "infeasible", "reason": "no legal single-boundary initializer",
                "initialization": single_info}
    cache: dict[str, tuple[float, dict]] = {}
    incumbent = None
    seed_evaluations = 0
    if seed_state is not None:
        seed_state = normalize(seed_state)
        validate(model, seed_state)
        if no_share_only and len(seed_state["segments"][0]["replicas"]) == 1:
            raise ValueError("No-share seed must use multiple first-stage replicas")
        if a100_prefix and any(model.types[node] != "A100"
                               for replica in seed_state["segments"][0]["replicas"] for node in replica):
            raise ValueError("Seed violates the A100 shared-prefix restriction")
        metrics = measure(model, seed_state)
        score = objective(metrics, reference_metrics)
        cache[signature(seed_state)] = (score, metrics)
        incumbent = (score, seed_state, metrics)
        seed_evaluations = 1
    shared, count_shared, trace_shared = _improve(
        model, single_states, reference_metrics, incumbent, cache,
        STAGE_BUDGET - seed_evaluations, a100_prefix)
    count_shared += seed_evaluations
    results = {}
    for mode in ("single", "multi"):
        mode_started = time.perf_counter()
        local_cache = dict(cache)
        if mode == "single":
            candidates = single_states
            info = single_info
        else:
            candidates, info = initial_states(
                model, a100_prefix=a100_prefix, multistage=True, no_share_only=no_share_only)
        best, additional, trace = _improve(
            model, candidates, reference_metrics, shared, local_cache,
            STAGE_BUDGET, a100_prefix)
        if best is None:
            results[mode] = {"status": "infeasible", "initialization": info}
            continue
        results[mode] = {"status": "feasible", "state": best[1],
                         "metrics": best[2], "score": best[0],
                         "reference": reference_metrics,
                         "initialization": info,
                         "common_evaluations": count_shared,
                         "additional_evaluations": additional,
                         "candidate_evaluations": count_shared + additional,
                         "trace": trace_shared + trace,
                         "extension_s": time.perf_counter() - mode_started}
    results["search_wall_s"] = time.perf_counter() - started
    return results


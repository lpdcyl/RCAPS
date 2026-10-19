"""Experimental per-layer-cost adapter; V3 source remains frozen."""

from __future__ import annotations

from collections import defaultdict

from rcaps.v3 import placement as original
from rcaps.v3.topology import profile_at


def weighted_layers(start: int, end: int, hot_start: int, hot_end: int,
                    multiplier: float) -> float:
    overlap = max(0, min(end, hot_end) - max(start, hot_start))
    return float(end - start) + overlap * (multiplier - 1.0)


def measure(model, state: dict, *, interval: tuple[int, int],
            multiplier: float) -> dict:
    """Identical static objective, with GPU work summed over its actual layers."""
    state = original.normalize(state)
    checked = original.validate(model, state)
    spans, resources = checked["spans"], checked["resources"]
    segments, transitions = state["segments"], checked["transitions"]
    demand = defaultdict(float)
    probabilities = [[0.0] * len(s["replicas"]) for s in segments]
    probabilities[0][0] = 1.0
    worst_prompt = [[float("-inf")] * len(s["replicas"]) for s in segments]
    worst_decode = [[float("-inf")] * len(s["replicas"]) for s in segments]
    worst_prompt[0][0] = worst_decode[0][0] = 0.0
    for level, segment in enumerate(segments):
        for index, replica in enumerate(segment["replicas"]):
            probability = probabilities[level][index]
            if probability <= 0:
                continue
            internal_prompt = internal_decode = 0.0
            for node in replica:
                effective = weighted_layers(*spans[node], *interval, multiplier)
                profile = resources.gpus[node].profile
                gpu_prompt = effective * profile_at(profile.prompt_bs2time,
                                                    resources.prompt_tokens)
                gpu_decode = effective * profile_at(profile.decode_bs2time,
                                                    resources.decode_batch)
                internal_prompt += gpu_prompt
                internal_decode += gpu_decode
                demand[f"gpu:{node}"] += probability * (
                    gpu_prompt + original.DECODE_COST_WEIGHT * gpu_decode)
            for left, right in original._replica_edges(replica):
                prompt, decode, work = original._transfer(resources, left, right)
                internal_prompt += prompt
                internal_decode += decode
                demand[f"link:{left}->{right}"] += probability * work
            worst_prompt[level][index] += internal_prompt
            worst_decode[level][index] += internal_decode
            if level == len(segments) - 1:
                prompt, decode, work = original._transfer(resources, replica[-1], "sink")
                worst_prompt[level][index] += prompt
                worst_decode[level][index] += decode
                demand[f"link:{replica[-1]}->sink"] += probability * work
                continue
            successors = [j for i, j in transitions[level] if i == index]
            flow = probability / len(successors)
            for successor in successors:
                next_replica = segments[level + 1]["replicas"][successor]
                prompt, decode, work = original._transfer(resources, replica[-1],
                                                          next_replica[0])
                probabilities[level + 1][successor] += flow
                demand[f"link:{replica[-1]}->{next_replica[0]}"] += flow * work
                worst_prompt[level + 1][successor] = max(
                    worst_prompt[level + 1][successor],
                    worst_prompt[level][index] + prompt)
                worst_decode[level + 1][successor] = max(
                    worst_decode[level + 1][successor],
                    worst_decode[level][index] + decode)
    first = segments[0]["replicas"][0][0]
    source_prompt, source_decode, source_work = original._transfer(resources, "source", first)
    demand[f"link:source->{first}"] += source_work
    bottleneck = max(demand, key=demand.get)
    return {"ttft_s": source_prompt + max(worst_prompt[-1]),
            "tpot_s": source_decode + max(worst_decode[-1]),
            "bottleneck_s": demand[bottleneck],
            "bottleneck_resource": bottleneck}


def cheap_cost(model, state: dict, *, interval: tuple[int, int],
               multiplier: float) -> float:
    checked = original.validate(model, state)
    spans = checked["spans"]
    segment_costs = []
    for segment in state["segments"]:
        replicas = []
        for replica in segment["replicas"]:
            cost = 0.0
            for node in replica:
                profile = model.profiles[model.types[node]]
                effective = weighted_layers(*spans[node], *interval, multiplier)
                cost += effective * (
                    0.40 * profile_at(profile.prompt_bs2time, model.prompt_tokens) +
                    0.35 * profile_at(profile.decode_bs2time, model.decode_batch))
            replicas.append(cost)
        segment_costs.append(max(replicas))
    return sum(segment_costs) + 0.002 * sum(state["lengths"].values())


def assert_unit_parity(model, states: list[dict]) -> None:
    for state in states:
        baseline, adapted = original.measure(model, state), measure(
            model, state, interval=(32, 48), multiplier=1)
        for key in baseline:
            if isinstance(baseline[key], float):
                if abs(baseline[key] - adapted[key]) > 1e-10:
                    raise AssertionError(f"Unit multiplier score drift: {key}")
            elif baseline[key] != adapted[key]:
                raise AssertionError(f"Unit multiplier bottleneck drift: {key}")

"""M2's profile-based placement cost, without inter-request simulation.

Canonical suffixes receive equal design weight, without forecasting traffic.
The returned latency values are isolated-route costs and must not be
interpreted as online P95 estimates.
"""

from __future__ import annotations

from collections import defaultdict

from . import adaptive
from .resource_graph import from_topology, layer_dag
from .topology import TopologyModel


# Fixed profiling scale inherited from the audited static comparator. It is
# not an estimate of any future request's output length or arrival pattern.
DECODE_COST_WEIGHT = 8


def measure(model: TopologyModel, state: dict) -> dict:
    """M2's static cost over M1's physical and legal-execution graphs."""
    resources = from_topology(model)
    spans = adaptive.intervals(model, state)
    dag = layer_dag(resources, spans, (state["stem"][0],))
    paths = []
    for branch in state["branches"]:
        route = [*state["stem"], *branch]
        transitions = list(zip(["source", *route], [*route, "sink"]))
        if any(edge not in dag.edge_set for edge in transitions):
            raise ValueError("Canonical suffix is absent from the execution DAG")
        stages = []
        for left, right in transitions:
            link = resources.link(left, right)
            if right == "sink":
                prefill = decode = 0.0
            else:
                length = spans[right][1] - spans[right][0]
                profile = resources.gpus[right].profile
                prefill = length * adaptive.profile_at(
                    profile.prompt_bs2time, resources.prompt_tokens)
                decode = length * adaptive.profile_at(
                    profile.decode_bs2time, resources.decode_batch)
            stages.append({"device": str(right), "prefill_s": prefill,
                           "decode_s": decode,
                           "incoming_link": f"{left}->{right}",
                           "incoming_latency_s": link.latency_s,
                           "incoming_bytes_per_s": link.bandwidth_bytes_per_s,
                           "payload_bytes": (resources.token_bytes if left == "source"
                                             else resources.token_bytes +
                                             resources.activation_bytes)})
        paths.append(stages)
    if not paths:
        raise ValueError("A placement must have at least one suffix")
    route_weight = 1.0 / len(paths)
    prompt_costs = []
    decode_costs = []
    demand: dict[str, float] = defaultdict(float)
    for path in paths:
        prompt_costs.append(sum(
            stage["prefill_s"] + stage["incoming_latency_s"] +
            stage["payload_bytes"] * model.prompt_tokens /
            stage["incoming_bytes_per_s"] for stage in path))
        decode_costs.append(sum(
            stage["decode_s"] + stage["incoming_latency_s"] +
            stage["payload_bytes"] / stage["incoming_bytes_per_s"]
            for stage in path))
        for stage in path:
            demand[f"link:{stage['incoming_link']}"] += route_weight * (
                stage["payload_bytes"] * model.prompt_tokens /
                stage["incoming_bytes_per_s"] +
                DECODE_COST_WEIGHT * stage["payload_bytes"] /
                stage["incoming_bytes_per_s"])
            if stage["device"] != "sink":
                demand[f"gpu:{stage['device']}"] += route_weight * (
                    stage["prefill_s"] + DECODE_COST_WEIGHT * stage["decode_s"])
    bottleneck = max(demand, key=demand.get)
    return {"ttft_s": max(prompt_costs),
            "tpot_s": max(decode_costs),
            "bottleneck_s": demand[bottleneck],
            "bottleneck_resource": bottleneck}

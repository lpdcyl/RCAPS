"""Build controlled single-path and shared-prefix sensitivity placements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rcaps.placement.partition import ROOT, save, scenario, topology_groups
from rcaps.placement.topology import TopologyModel, profile_at


HERE = Path(__file__).resolve().parent


def service_rank(model: TopologyModel, node: int) -> tuple[float, int]:
    profile = model.profiles[model.types[node]]
    prompt = profile_at(profile.prompt_bs2time, model.prompt_tokens)
    decode = profile_at(profile.decode_bs2time, model.decode_batch)
    return (prompt + decode, node)


def assign_single_path(model: TopologyModel, route: list[int]) -> dict:
    if sum(model.capacity[node] for node in route) < model.layers:
        raise ValueError("Single path lacks total layer capacity")
    lengths = {node: 1 for node in route}
    remaining = model.layers - len(route)
    if remaining < 0:
        raise ValueError("More active GPUs than layers")
    for node in sorted(route, key=lambda item: service_rank(model, item)):
        extra = min(remaining, model.capacity[node] - 1)
        lengths[node] += extra
        remaining -= extra
    if remaining:
        raise ValueError("Single path assignment incomplete")
    state = {"shared": route[0], "shared_length": lengths[route[0]],
             "paths": [route[1:]], "lengths": lengths}
    model.intervals(state)
    return state


def ordered_route(model: TopologyModel, devices: set[int]) -> list[int]:
    groups = topology_groups(model)
    # Keep each physical region contiguous, then order its devices by measured
    # per-layer service time. This minimizes region crossings among these groups.
    return [node for group in groups
            for node in sorted(devices.intersection(group),
                               key=lambda item: service_rank(model, item))]


def single_path(model: TopologyModel, *, all_gpus: bool) -> dict:
    if all_gpus:
        selected = set(model.types)
    else:
        # Select the fastest-capacity devices first, preferring one remote
        # region for tied L4s on the three-cluster physical topology. The
        # selection uses hardware profiles only, never benchmark outcomes.
        groups = topology_groups(model)
        node_group = {node: index for index, group in enumerate(groups)
                      for node in group}
        preferred_remote = max(range(len(groups)),
                               key=lambda index: (sum(model.types[node] == "L4"
                                                     for node in groups[index]),
                                                  -index))
        candidates = sorted(model.types,
                            key=lambda node: (service_rank(model, node)[0],
                                              node_group[node] != preferred_remote,
                                              node))
        selected = set()
        capacity = 0
        for node in candidates:
            selected.add(node)
            capacity += model.capacity[node]
            if capacity >= model.layers:
                break
    return assign_single_path(model, ordered_route(model, selected))


def prefix_variant(model: TopologyModel, reference: dict,
                   prefix_length: int) -> dict:
    shared = reference["shared"]
    branches = reference["branches"]
    base_length = reference["intervals"][str(shared)][1]
    if not 1 <= prefix_length <= min(base_length, model.capacity[shared]):
        raise ValueError("Prefix length outside feasible A100 range")
    required = model.layers - prefix_length
    capacities = [sum(model.capacity[node] for node in path)
                  for path in branches]
    if min(capacities) < required:
        raise ValueError(f"Prefix {prefix_length} needs {required} layers per "
                         f"suffix but fixed branch capacities are {capacities}")
    lengths = {int(node): end - start for node, (start, end)
               in reference["intervals"].items() if int(node) != shared}
    delta = base_length - prefix_length
    for path in branches:
        missing = delta
        for node in path:
            addition = min(missing, model.capacity[node] - lengths[node])
            lengths[node] += addition
            missing -= addition
            if not missing:
                break
        if missing:
            raise ValueError("Fixed suffix cannot absorb shorter prefix")
    state = {"shared": shared, "shared_length": prefix_length,
             "paths": branches, "lengths": lengths}
    model.intervals(state)
    return state


def active_summary(model: TopologyModel, state: dict) -> dict:
    spans = model.intervals(state)
    assigned = sum(end - start for start, end in spans.values())
    active_capacity = sum(model.capacity[node] for node in spans)
    pool_capacity = sum(model.capacity.values())
    return {"active_gpu_count": len(spans),
            "physical_gpu_count": len(model.types),
            "assigned_layer_replicas": assigned,
            "active_layer_capacity": active_capacity,
            "pool_layer_capacity": pool_capacity,
            "active_capacity_utilization": assigned / active_capacity,
            "pool_capacity_utilization": assigned / pool_capacity,
            "branch_capacities": [sum(model.capacity[node] for node in path)
                                  for path in state["paths"]],
            "canonical_path_count": len(state["paths"])}


def generate(scenario_name: str, arm: str) -> dict:
    physical, template = scenario(scenario_name)
    model = TopologyModel(physical)
    reference = json.loads((ROOT / "rcaps/layouts" / scenario_name /
                            "placement.json").read_text(encoding="utf-8"))
    if arm == "s1_all24":
        state = single_path(model, all_gpus=True)
    elif arm == "s1_lean":
        state = single_path(model, all_gpus=False)
    elif arm.startswith("s3_prefix"):
        state = prefix_variant(model, reference, int(arm.removeprefix("s3_prefix")))
    else:
        raise ValueError(arm)
    destination = HERE / "layouts" / scenario_name / arm
    trace = [{"step": 0, "move": "deterministic structural ablation",
              "demand_mode": "none", "score": None}]
    result = save(model, template, state, destination, trace,
                  algorithm=f"structure ablation {arm}")
    metadata = {"scenario": scenario_name, "arm": arm,
                "physical_topology": physical.relative_to(ROOT).as_posix(),
                "online_scheduler": "QueueAwareDagScheduler",
                "state": state, "capacity": active_summary(model, state),
                "solution": result["solution"],
                "simulator_cluster": result["simulator_cluster"]}
    (destination / "structure.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    parser.add_argument("--arm", required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.scenario, args.arm)["capacity"], indent=2))


if __name__ == "__main__":
    main()

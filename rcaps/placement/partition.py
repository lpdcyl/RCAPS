"""Critical-path-guided, topology-aware partition of an ordered layer graph.

The physical graph supplies GPU capacities and per-link transfer costs. The
model graph is an ordered chain of layers. A feasible mapping has one shared
prefix and two complete, disjoint suffix paths. Region contraction builds a
coarse placement; gain-ordered boundary refinement improves its mapping.
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
import time
from configparser import ConfigParser
from heapq import heappop, heappush
from pathlib import Path

from .topology import GraphMetrics, TopologyModel


ROOT = Path(__file__).resolve().parents[2]


def scenario(name: str) -> tuple[Path, Path]:
    if name == "single":
        base = ROOT / "examples/simulation"
        return base / "config/single24.ini", base / "layouts/ilp/simulator_cluster.ini"
    if name == "multi":
        base = ROOT / "artifact_evaluation/distributed_clusters"
        return base / "config/3cluster24.ini", base / "layout_llama70b/ilp/simulator_cluster.ini"
    raise ValueError(name)


def topology_groups(model: TopologyModel) -> list[list[int]]:
    """Contract fast-connected GPUs; the widest RTT gap defines the cut."""
    edges: list[tuple[int, int, float]] = []
    for section in model.config.sections():
        parts = section.split("-")
        if len(parts) != 3 or parts[0] != "Link":
            continue
        if not parts[1].isdigit() or not parts[2].isdigit():
            continue
        left, right = int(parts[1]), int(parts[2])
        if left in model.types and right in model.types:
            edges.append((left, right, model.link(left, right)[0]))
    latencies = sorted({latency for _, _, latency in edges})
    if len(latencies) < 2:
        return [sorted(model.types)]
    widest = max(range(len(latencies) - 1),
                 key=lambda index: latencies[index + 1] / max(latencies[index], 1e-12))
    threshold = (latencies[widest] * latencies[widest + 1]) ** 0.5
    parent = {node: node for node in model.types}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for left, right, latency in edges:
        if latency <= threshold:
            parent[find(left)] = find(right)
    groups: dict[int, list[int]] = {}
    for node in model.types:
        groups.setdefault(find(node), []).append(node)
    return sorted((sorted(group) for group in groups.values()), key=lambda group: group[0])


def capacity_partition(model: TopologyModel) -> dict:
    """VRAM-only two-branch construction; do not inspect RTT or bandwidth.

    The same physical GPU pool and shared-prefix/two-suffix family are used as
    in ``initial_partition``. All non-shared GPUs are assigned to one branch,
    so gains cannot be attributed to activating more devices.
    """
    shared = min(model.types, key=lambda node: (-model.capacity[node], node))
    remaining = model.layers - model.capacity[shared]
    devices = sorted((node for node in model.types if node != shared),
                     key=lambda node: (-model.capacity[node], node))
    paths: list[list[int]] = [[], []]
    capacities = [0, 0]
    for node in devices:
        target = min(range(2), key=lambda index: (capacities[index], index))
        paths[target].append(node)
        capacities[target] += model.capacity[node]
    if min(capacities) < remaining:
        raise ValueError("VRAM-only split cannot cover both complete suffixes")
    lengths: dict[int, int] = {}
    for path in paths:
        unplaced = remaining
        for index, node in enumerate(path):
            reserve = len(path) - index - 1
            length = min(model.capacity[node], unplaced - reserve)
            if length < 1:
                raise ValueError("VRAM-only split cannot give every GPU a layer")
            lengths[node] = length
            unplaced -= length
        if unplaced:
            raise ValueError("VRAM-only branch does not cover all layers")
    state = {"shared": shared, "shared_length": model.capacity[shared],
             "paths": paths, "lengths": lengths}
    model.intervals(state)
    return state


def initial_partition(model: TopologyModel) -> dict:
    """Form two complete replicas using contracted topology and VRAM capacity."""
    groups = topology_groups(model)
    a100 = [node for node, kind in model.types.items() if kind == "A100"]
    shared = min(a100, key=lambda node: (model.link("source", node)[0], node))
    required = model.layers - model.capacity[shared]
    if len(groups) >= 3:
        central = next(group for group in groups if shared in group)
        remotes = [list(group) for group in groups if group is not central]
        remotes.sort(key=lambda group: (-sum(model.capacity[node] for node in group), group[0]))
        paths = remotes[:2]
        pool = [node for node in central if node != shared]
        pool.extend(node for group in remotes[2:] for node in group)
        pool.sort(key=lambda node: (-model.capacity[node], node))
        for path in sorted(paths, key=lambda group: sum(model.capacity[node] for node in group)):
            while sum(model.capacity[node] for node in path) < required:
                if not pool:
                    raise ValueError("Insufficient capacity for both paths")
                path.append(pool.pop(0))
    else:
        # Balanced two-way partition of the physical graph. The capacity target
        # is explicit; device order is chosen separately from the layer cut.
        devices = sorted((node for node in model.types if node != shared),
                         key=lambda node: (-model.capacity[node], node))
        paths = [[], []]
        capacity = [0, 0]
        for node in devices:
            target = min(range(2), key=lambda index: (capacity[index], index))
            paths[target].append(node)
            capacity[target] += model.capacity[node]
        if min(capacity) < required:
            for source in sorted(range(2), key=lambda index: -capacity[index]):
                target = 1 - source
                for node in sorted(paths[source], key=lambda item: (model.capacity[item], item)):
                    amount = model.capacity[node]
                    if capacity[source] - amount >= required and capacity[target] < required:
                        paths[source].remove(node)
                        paths[target].append(node)
                        capacity[source] -= amount
                        capacity[target] += amount
        if min(capacity) < required:
            raise ValueError("Could not form two complete layer paths")
    ordered: list[list[int]] = []
    for group in paths:
        remaining = set(group)
        route: list[int] = []
        previous: str | int = shared
        while remaining and sum(model.capacity[node] for node in route) < required:
            node = min(remaining, key=lambda candidate: (
                model.link(previous, candidate)[0] +
                model.manager.get_model_activation_size() /
                model.link(previous, candidate)[1],
                -model.capacity[candidate], candidate))
            route.append(node)
            remaining.remove(node)
            previous = node
        if sum(model.capacity[node] for node in route) < required:
            raise ValueError("A path does not cover every model layer")
        ordered.append(route)
    lengths: dict[int, int] = {}
    for route in ordered:
        remaining = required
        for index, node in enumerate(route):
            reserve = len(route) - index - 1
            length = min(model.capacity[node], remaining - reserve)
            if length < 1:
                raise ValueError("Every selected GPU must host at least one layer")
            lengths[node] = length
            remaining -= length
        if remaining:
            raise ValueError("Incomplete model coverage")
    state = {"shared": shared, "shared_length": model.capacity[shared],
             "paths": ordered, "lengths": lengths}
    model.intervals(state)
    return state


def score(metrics: GraphMetrics, reference: GraphMetrics) -> float:
    return (0.40 * metrics.ttft_s / reference.ttft_s +
            0.35 * metrics.tpot_s / reference.tpot_s +
            0.25 * metrics.bottleneck_s / reference.bottleneck_s)


def boundary_moves(state: dict, model: TopologyModel, metrics: GraphMetrics | None,
                   *, guided: bool = True):
    """Emit the same legal neighborhood, optionally filtered by critical resources."""
    if guided and metrics is None:
        raise ValueError("Guided search requires resource metrics")
    active = (set(metrics.critical_resources) | {metrics.bottleneck_resource}
              if metrics is not None else set())
    for branch, path in enumerate(state["paths"]):
        for position in range(len(path) - 1):
            left, right = path[position:position + 2]
            neighborhood = {f"gpu:{left}", f"gpu:{right}", f"link:{left}->{right}"}
            if guided and not neighborhood & active:
                continue
            for donor, receiver in ((left, right), (right, left)):
                if state["lengths"][donor] <= 1 or state["lengths"][receiver] >= model.capacity[receiver]:
                    continue
                candidate = copy.deepcopy(state)
                candidate["lengths"][donor] -= 1
                candidate["lengths"][receiver] += 1
                yield f"branch{branch}: boundary {donor}->{receiver}", candidate
            candidate = copy.deepcopy(state)
            candidate["paths"][branch][position:position + 2] = [right, left]
            yield f"branch{branch}: topology swap {left}<->{right}", candidate
    if state["shared_length"] > 1:
        first_nodes = [path[0] for path in state["paths"]]
        if (all(state["lengths"][node] < model.capacity[node] for node in first_nodes) and
                (not guided or f"gpu:{state['shared']}" in active or
                 any(f"gpu:{node}" in active for node in first_nodes))):
            candidate = copy.deepcopy(state)
            candidate["shared_length"] -= 1
            for node in first_nodes:
                candidate["lengths"][node] += 1
            yield "shared boundary -1", candidate
    if state["shared_length"] < model.capacity[state["shared"]] and all(
            state["lengths"][path[0]] > 1 for path in state["paths"]):
        candidate = copy.deepcopy(state)
        candidate["shared_length"] += 1
        for path in state["paths"]:
            candidate["lengths"][path[0]] -= 1
        yield "shared boundary +1", candidate


def refine(model: TopologyModel, initial: dict, *, max_steps: int = 16,
           demand_mode: str | None = None, guided: bool = True
           ) -> tuple[dict, list[dict]]:
    state = copy.deepcopy(initial)
    # Uniform low-latency topology admits many stitched routes and their join
    # hotspots matter. Across contracted regions, the critical-path proxy
    # retains emphasis on inter-region stage order and transfer latency.
    if demand_mode is None:
        demand_mode = "ensemble" if len(topology_groups(model)) == 1 else "canonical"
    if demand_mode not in ("ensemble", "canonical"):
        raise ValueError(f"Unknown demand mode: {demand_mode}")
    reference = model.measure(state, demand_mode=demand_mode)
    started = time.perf_counter()
    evaluations = 1
    current = reference
    current_score = score(current, reference)
    trace = [{"step": 0, "move": "coarse partition", "score": current_score,
              "demand_mode": demand_mode,
              "search_mode": "guided" if guided else "full",
              "ttft_s": current.ttft_s, "tpot_s": current.tpot_s,
              "bottleneck_s": current.bottleneck_s,
              "bottleneck_resource": current.bottleneck_resource}]
    for step in range(1, max_steps + 1):
        gains = []
        for sequence, (move, candidate) in enumerate(
                boundary_moves(state, model, current, guided=guided)):
            try:
                evaluations += 1
                estimate = model.measure(candidate, demand_mode=demand_mode)
            except ValueError:
                continue
            candidate_score = score(estimate, reference)
            gain = current_score - candidate_score
            if gain > 1e-9:
                heappush(gains, (-gain, sequence, move, candidate, estimate))
        if not gains:
            break
        neg_gain, _, move, state, current = heappop(gains)
        current_score += neg_gain
        trace.append({"step": step, "move": move, "gain": -neg_gain,
                      "score": current_score, "ttft_s": current.ttft_s,
                      "tpot_s": current.tpot_s,
                      "bottleneck_s": current.bottleneck_s,
                      "bottleneck_resource": current.bottleneck_resource})
    trace[0]["candidate_evaluations"] = evaluations - 1
    trace[0]["planning_s"] = time.perf_counter() - started
    return state, trace


def static_route_costs(model: TopologyModel, state: dict) -> tuple[float, float]:
    """Mean isolated-route prefill/decode times without event or queue modeling."""
    model.intervals(state)
    prompt, decode = [], []
    for path in state["paths"]:
        stages = model._stages(state, path)
        prompt.append(sum(stage["prefill_s"] + stage["incoming_latency_s"] +
                          stage["payload_bytes"] * model.prompt_tokens /
                          stage["incoming_bytes_per_s"] for stage in stages))
        decode.append(sum(stage["decode_s"] + stage["incoming_latency_s"] +
                          stage["payload_bytes"] /
                          stage["incoming_bytes_per_s"] for stage in stages))
    return sum(prompt) / len(prompt), sum(decode) / len(decode)


def refine_static(model: TopologyModel, initial: dict, *, max_steps: int = 16
                  ) -> tuple[dict, list[dict]]:
    """Use the full legal neighborhood and isolated-route latency alone."""
    state = copy.deepcopy(initial)
    started = time.perf_counter()
    reference = static_route_costs(model, state)
    evaluations = 0

    def objective(costs: tuple[float, float]) -> float:
        # Renormalize the two latency terms of the original 0.40/0.35/0.25
        # score after removing its bottleneck-demand component.
        return (0.40 * costs[0] / reference[0] +
                0.35 * costs[1] / reference[1]) / 0.75

    current = reference
    current_score = objective(current)
    trace = [{"step": 0, "move": "coarse partition", "score": current_score,
              "search_mode": "static", "demand_mode": "none",
              "static_prefill_s": current[0], "static_decode_s": current[1]}]
    for step in range(1, max_steps + 1):
        gains = []
        for sequence, (move, candidate) in enumerate(
                boundary_moves(state, model, None, guided=False)):
            evaluations += 1
            try:
                estimate = static_route_costs(model, candidate)
            except ValueError:
                continue
            gain = current_score - objective(estimate)
            if gain > 1e-9:
                heappush(gains, (-gain, sequence, move, candidate, estimate))
        if not gains:
            break
        neg_gain, _, move, state, current = heappop(gains)
        current_score += neg_gain
        trace.append({"step": step, "move": move, "gain": -neg_gain,
                      "score": current_score, "static_prefill_s": current[0],
                      "static_decode_s": current[1]})
    trace[0]["candidate_evaluations"] = evaluations
    trace[0]["planning_s"] = time.perf_counter() - started
    return state, trace


def save(model: TopologyModel, template: Path, state: dict, destination: Path,
         trace: list[dict], *, algorithm: str =
         "topology-conditioned critical-path/path-ensemble graph partition") -> dict:
    spans = model.intervals(state)
    destination.mkdir(parents=True, exist_ok=True)
    solution = ConfigParser()
    solution["Settings"] = {"offset": "2"}
    solution["Solution"] = {f"compute_node_{node + 2}": repr(list(range(*interval)))
                            for node, interval in sorted(spans.items())}
    solution_file = destination / "solution.ini"
    with solution_file.open("w", encoding="utf-8") as handle:
        solution.write(handle)
    sim = ConfigParser()
    if not sim.read(template):
        raise FileNotFoundError(template)
    for node, (start, end) in spans.items():
        sim[f"compute_node_{node + 2}"]["kv_cache_capacity"] = str(
            model.manager.get_kv_cache_capacity(model.types[node], end - start))
    for section in list(sim.sections()):
        if section.startswith("link_"):
            sim.remove_section(section)
    edges: list[tuple[str | int, str | int]] = [("source", state["shared"])]
    for left, (_, end) in spans.items():
        for right, (start, limit) in spans.items():
            if left != right and start <= end < limit:
                edges.append((left, right))
        if end == model.layers:
            edges.append((left, "sink"))
    names: list[str] = []
    for left, right in edges:
        lookup = f"Link-{left}-{right}"
        if lookup not in model.config:
            lookup = f"Link-{right}-{left}"
        if lookup not in model.config:
            raise ValueError(f"Missing link {left}->{right}")
        left_name = left if left == "source" else f"compute_node_{left + 2}"
        right_name = right if right == "sink" else f"compute_node_{right + 2}"
        name = f"link_{left_name}_{right_name}"
        names.append(name)
        sim[name] = {"in": left_name, "out": right_name,
                     "latency": model.config[lookup]["latency"],
                     "bandwidth": model.config[lookup]["bandwidth"]}
    sim["Links"]["names"] = repr(names)
    sim_file = destination / "simulator_cluster.ini"
    with sim_file.open("w", encoding="utf-8") as handle:
        sim.write(handle)
    result = {"algorithm": algorithm,
              "demand_mode": trace[0]["demand_mode"],
              "cluster_file": model.cluster_file.relative_to(ROOT).as_posix(),
              "shared": state["shared"],
              "branches": state["paths"],
              "intervals": {str(node): list(interval) for node, interval in sorted(spans.items())},
              "solution": solution_file.as_posix(),
              "simulator_cluster": sim_file.as_posix(),
              "trace": trace}
    (destination / "placement.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("single", "multi"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--demand-mode", choices=("auto", "canonical", "ensemble"),
                        default="auto")
    parser.add_argument("--initial-mode", choices=("topology", "capacity"),
                        default="topology")
    parser.add_argument("--search-mode", choices=("guided", "full", "static"),
                        default="guided")
    args = parser.parse_args()
    cluster, template = scenario(args.scenario)
    model = TopologyModel(cluster)
    if args.initial_mode == "capacity":
        if args.max_steps != 0:
            parser.error("capacity-only placement requires --max-steps 0")
        refined = capacity_partition(model)
        trace = [{"step": 0, "move": "VRAM-only construction",
                  "demand_mode": "none", "score": None}]
        algorithm = "VRAM-only balanced shared-prefix/two-suffix partition"
    else:
        state = initial_partition(model)
        if args.search_mode == "static":
            refined, trace = refine_static(model, state, max_steps=args.max_steps)
            algorithm = "topology-conditioned full-neighborhood isolated-route search"
        else:
            refined, trace = refine(model, state, max_steps=args.max_steps,
                                    demand_mode=None if args.demand_mode == "auto"
                                    else args.demand_mode,
                                    guided=args.search_mode == "guided")
            algorithm = ("topology-conditioned critical-path/path-ensemble graph partition"
                         if args.search_mode == "guided" else
                         "topology-conditioned full-neighborhood greedy graph partition")
    result = save(model, template, refined, args.output_dir, trace,
                  algorithm=algorithm)
    print(json.dumps({"scenario": args.scenario, "steps": len(trace) - 1,
                      "initial_score": trace[0]["score"],
                      "final_score": trace[-1]["score"],
                      "solution": result["solution"]}, indent=2))


if __name__ == "__main__":
    main()

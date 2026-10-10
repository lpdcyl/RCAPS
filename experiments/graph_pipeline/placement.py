"""Construct two complete layer paths using capacity and locality graph constraints."""

from __future__ import annotations

import argparse
import ast
import json
from configparser import ConfigParser
from pathlib import Path

from simulator.model_manager.model_manager import ModelManager, ModelName

ROOT = Path(__file__).resolve().parents[2]
MACHINES = {"A100": 4, "L4": 8, "T4": 12}


def _node_types(cluster: Path):
    parser = ConfigParser()
    parser.read(cluster)
    n = ast.literal_eval(parser["NodeNames"]["total_compute_nodes"])
    return {i: parser[f"ComputeNode-{i}"]["type"] for i in range(n)}


def _choose_shared(types, manager):
    a100 = [i for i, kind in types.items() if kind == "A100"]
    return a100[0]


def _partition_single(types, shared, capacity, needed):
    by_type = {kind: [i for i, current in types.items() if current == kind and i != shared]
               for kind in ("A100", "L4", "T4")}
    # Small subset-sum DP over type counts gives each branch a full layer cover
    # while balancing fast GPUs. The symmetric solution is deterministic.
    options = []
    for a in range(len(by_type["A100"]) + 1):
        for l in range(len(by_type["L4"]) + 1):
            for t in range(len(by_type["T4"]) + 1):
                cover = 12 * a + 7 * l + 4 * t
                leftover = sum(capacity[i] for i in types if i != shared) - cover
                if cover == needed and leftover >= needed:
                    # Balance L4 stages first, then place the odd A100 on the
                    # branch with fewer T4 stages to equalize service demand.
                    score = (abs(2 * l - len(by_type["L4"])),
                             abs(a - 2), abs(2 * t - len(by_type["T4"])), -a)
                    options.append((score, a, l, t))
    _, a, l, t = min(options)
    first = [*by_type["A100"][:a], *by_type["L4"][:l], *by_type["T4"][:t]]
    second = [*by_type["A100"][a:], *by_type["L4"][l:], *by_type["T4"][t:]]
    return first, second


def _regions(cluster, types):
    parser = ConfigParser()
    parser.read(cluster)
    edges = []
    for name in parser.sections():
        parts = name.split("-")
        if len(parts) != 3 or parts[0] != "Link" or not parts[1].isdigit() or not parts[2].isdigit():
            continue
        latency = float(parser[name]["latency"].split("*")[0].strip())
        edges.append((int(parts[1]), int(parts[2]), latency))
    values = sorted({latency for _, _, latency in edges})
    if len(values) < 2:
        threshold = values[0] if values else float("inf")
    else:
        gap = max(range(len(values) - 1), key=lambda k: values[k + 1] / values[k])
        threshold = (values[gap] * values[gap + 1]) ** 0.5
    parent = {i: i for i in types}
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j, latency in edges:
        if latency <= threshold:
            parent[find(i)] = find(j)
    groups = {}
    for i in types:
        groups.setdefault(find(i), []).append(i)
    return sorted((sorted(group) for group in groups.values()), key=lambda group: group[0])


def _partition_multi(cluster, types, shared, capacity, needed):
    groups = _regions(cluster, types)
    central = next(group for group in groups if shared in group)
    branches = [list(group) for group in groups if group is not central]
    if len(branches) != 2:
        raise ValueError("Expected two remote regions in the three-cluster topology")
    remaining = sorted((i for i in central if i != shared),
                       key=lambda i: (-capacity[i], i))
    for branch in sorted(branches, key=lambda group: sum(capacity[i] for i in group)):
        while sum(capacity[i] for i in branch) < needed:
            branch.insert(0, remaining.pop(0))
    return branches[0], branches[1]


def save_layout(cluster: Path, sim_template: Path, destination: Path, variant: str,
                types: dict[int, str], manager: ModelManager, shared: int,
                branches: list[list[int]], intervals: dict[int, tuple[int, int]]) -> dict:
    """Serialize an independently computed layer assignment and its usable links."""
    total_layers = manager.get_num_layers()
    destination.mkdir(parents=True, exist_ok=True)
    solution = ConfigParser()
    solution["Settings"] = {"offset": "2"}
    solution["Solution"] = {f"compute_node_{i + 2}": repr(list(range(*intervals[i])))
                            for i in sorted(intervals)}
    solution_file = destination / "solution.ini"
    with solution_file.open("w", encoding="utf-8") as handle:
        solution.write(handle)
    sim = ConfigParser()
    sim.read(sim_template)
    for i, (start, end) in intervals.items():
        sim[f"compute_node_{i + 2}"]["kv_cache_capacity"] = str(
            manager.get_kv_cache_capacity(types[i], end - start))
    for section in list(sim.sections()):
        if section.startswith("link_"):
            sim.remove_section(section)
    complete = ConfigParser()
    complete.read(cluster)
    links = []
    edges = [("source", shared)]
    for i, (_, end) in intervals.items():
        for j, (next_start, next_end) in intervals.items():
            if i != j and next_start <= end < next_end:
                edges.append((i, j))
        if end == total_layers:
            edges.append((i, "sink"))
    for src, dst in edges:
        lookup = f"Link-{src}-{dst}"
        if lookup not in complete:
            lookup = f"Link-{dst}-{src}"
        if lookup not in complete:
            raise ValueError(f"Missing topology link for {src} -> {dst}")
        src_name = "source" if src == "source" else f"compute_node_{src + 2}"
        dst_name = "sink" if dst == "sink" else f"compute_node_{dst + 2}"
        name = f"link_{src_name}_{dst_name}"
        links.append(name)
        sim[name] = {"in": src_name, "out": dst_name,
                     "latency": complete[lookup]["latency"],
                     "bandwidth": complete[lookup]["bandwidth"]}
    sim["Links"]["names"] = repr(links)
    sim_file = destination / "simulator_cluster.ini"
    with sim_file.open("w", encoding="utf-8") as handle:
        sim.write(handle)
    result = {"variant": variant, "shared": shared, "branches": branches,
              "intervals": {str(i): list(span) for i, span in sorted(intervals.items())},
              "solution": str(solution_file), "simulator_cluster": str(sim_file),
              "unused_nodes": sorted(set(types) - set(intervals))}
    (destination / "placement.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def construct(cluster: Path, profile: Path, sim_template: Path, destination: Path,
              variant: str) -> dict:
    """Allocate exact intervals; no Helix placement, max flow, or MILP is read."""
    types = _node_types(cluster)
    manager = ModelManager(ModelName.LLaMa70B, MACHINES)
    total_layers = manager.get_num_layers()
    capacity = {i: manager.get_max_num_layers(kind) for i, kind in types.items()}
    shared = _choose_shared(types, manager)
    shared_length = capacity[shared]
    remaining = total_layers - shared_length
    branch_a, branch_b = (_partition_multi(cluster, types, shared, capacity, remaining)
                          if variant == "multi" else
                          _partition_single(types, shared, capacity, remaining))
    if sum(capacity[i] for i in branch_a) < remaining or sum(capacity[i] for i in branch_b) < remaining:
        raise ValueError("The selected branch has insufficient layer capacity")
    intervals = {shared: (0, shared_length)}
    for branch in (branch_a, branch_b):
        # Put fast nodes before each region crossing; their 12-layer blocks amortize prompt transfer.
        order = sorted(branch, key=lambda i: (0 if types[i] == "A100" else
                                              1 if types[i] == "L4" else 2, i))
        current = shared_length
        for i in order:
            if current >= total_layers:
                break
            end = min(total_layers, current + capacity[i])
            intervals[i] = (current, end)
            current = end
        assert current == total_layers
    return save_layout(cluster, sim_template, destination, variant, types, manager,
                       shared, [branch_a, branch_b], intervals)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["single", "multi"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.variant == "single":
        base = ROOT / "examples/simulation"
        cluster = base / "config/single24.ini"
        profile = base / "config/machine_profile.ini"
        template = base / "layouts/ilp/simulator_cluster.ini"
    else:
        base = ROOT / "artifact_evaluation/distributed_clusters"
        cluster = base / "config/3cluster24.ini"
        profile = base / "config/machine_profiles.ini"
        template = base / "layout_llama70b/ilp/simulator_cluster.ini"
    print(json.dumps(construct(cluster, profile, template, args.output_dir, args.variant), indent=2))


if __name__ == "__main__":
    main()

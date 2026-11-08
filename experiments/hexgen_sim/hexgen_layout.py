"""Development implementation of HexGen's partition/placement search.

This is deliberately separate from official-result directories. It implements
full-model pipeline grouping, a bounded genetic search, and DP layer placement.
The static fitness is an approximation to the paper's simulated SLO objective;
outputs from this module must therefore be called development candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from configparser import ConfigParser
from pathlib import Path

from benchmarks.layout import scenario
from rcaps.v3.topology import TopologyModel, profile_at

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULTS = {
    "single24": (scenario("single")[0], scenario("single")[3]),
    "multi24": (scenario("multi")[0], scenario("multi")[3]),
    "high_heterogeneity42": (
        ROOT / "artifact_evaluation/high_heterogeneity/config/cluster42.ini",
        ROOT / "artifact_evaluation/high_heterogeneity/layout_llama70b/ilp/simulator_cluster.ini",
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def node_cost(model: TopologyModel, node: int) -> float:
    profile = model.profiles[model.types[node]]
    return profile_at(profile.prompt_bs2time, model.prompt_tokens) + 32 * profile_at(
        profile.decode_bs2time, model.decode_batch
    )


def order_nodes(model: TopologyModel, nodes: tuple[int, ...]) -> tuple[int, ...]:
    """Keep the faster stages early and make interstage links a tie breaker."""
    remaining = set(nodes)
    first = min(remaining, key=lambda n: (node_cost(model, n), n))
    ordered = [first]
    remaining.remove(first)
    while remaining:
        last = ordered[-1]
        def key(n: int) -> tuple[float, float, int]:
            try:
                latency, bandwidth = model.link(last, n)
            except ValueError:
                return (float("inf"), float("inf"), n)
            return (node_cost(model, n) + 16384 / bandwidth + latency,
                    node_cost(model, n), n)
        nxt = min(remaining, key=key)
        if key(nxt)[0] == float("inf"):
            raise ValueError("No connected pipeline ordering")
        ordered.append(nxt)
        remaining.remove(nxt)
    model.link("source", ordered[0])
    model.link(ordered[-1], "sink")
    return tuple(ordered)


def place_layers(model: TopologyModel, nodes: tuple[int, ...]) -> dict:
    """DP minimizes the maximum per-stage service estimate, then total work."""
    ordered = order_nodes(model, nodes)
    if sum(model.capacity[n] for n in ordered) < model.layers:
        raise ValueError("Insufficient full-model layer capacity")
    # State value: (estimated bottleneck, sum of stage costs, lengths tuple).
    table = {0: (0.0, 0.0, ())}
    for node in ordered:
        next_table = {}
        per_layer = node_cost(model, node)
        for assigned, (worst, total, lengths) in table.items():
            for count in range(1, min(model.capacity[node], model.layers - assigned) + 1):
                if model.manager.get_kv_cache_capacity(model.types[node], count) <= 0:
                    continue
                stage = count * per_layer
                item = (max(worst, stage), total + stage, lengths + (count,))
                index = assigned + count
                if index not in next_table or item[:2] < next_table[index][:2]:
                    next_table[index] = item
        table = next_table
    if model.layers not in table:
        raise ValueError("No KV-feasible full-model layer allocation")
    worst, total, lengths = table[model.layers]
    spans = {}
    cursor = 0
    for node, count in zip(ordered, lengths):
        spans[node] = (cursor, cursor + count)
        cursor += count
    assert cursor == model.layers
    communication = 0.0
    for left, right in zip(ordered, ordered[1:]):
        latency, bandwidth = model.link(left, right)
        communication += latency + 16384 / bandwidth
    return {"nodes": list(ordered), "spans": spans, "bottleneck_estimate_s": worst,
            "total_stage_estimate_s": total, "communication_estimate_s": communication}


def normalized(groups: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(tuple(sorted(group)) for group in groups))


def initial_partition(model: TopologyModel, count: int, rng: random.Random):
    groups = [[] for _ in range(count)]
    capacities = [0] * count
    nodes = list(model.types)
    rng.shuffle(nodes)
    nodes.sort(key=lambda n: model.capacity[n], reverse=True)
    for node in nodes:
        index = min(range(count), key=lambda g: (capacities[g], len(groups[g]), g))
        groups[index].append(node)
        capacities[index] += model.capacity[node]
    if min(capacities) < model.layers:
        return None
    return normalized(groups)


def mutate(model: TopologyModel, partition, rng: random.Random):
    groups = [list(group) for group in partition]
    if len(groups) < 2:
        return partition
    left, right = rng.sample(range(len(groups)), 2)
    if rng.random() < 0.5 and len(groups[left]) > 1:
        node = rng.choice(groups[left])
        groups[left].remove(node)
        groups[right].append(node)
    else:
        a, b = rng.choice(groups[left]), rng.choice(groups[right])
        groups[left].remove(a)
        groups[right].remove(b)
        groups[left].append(b)
        groups[right].append(a)
    if min(sum(model.capacity[n] for n in group) for group in groups) < model.layers:
        return partition
    return normalized(groups)


def optimize(model: TopologyModel, seed: int = 2403,
             generations: int = 8, population_size: int = 12) -> dict:
    """Bounded GA over GPU partitions; the inner search is layer DP."""
    rng = random.Random(seed)
    upper = min(4, sum(model.capacity.values()) // model.layers)
    cache = {}
    def evaluate(partition):
        if partition not in cache:
            try:
                layouts = [place_layers(model, group) for group in partition]
                # Static proxy: combined service capacity, with a latency penalty.
                capacity = sum(1.0 / (layout["bottleneck_estimate_s"] +
                                      layout["communication_estimate_s"])
                               for layout in layouts)
                latency = sum(layout["total_stage_estimate_s"] +
                              layout["communication_estimate_s"] for layout in layouts)
                cache[partition] = (capacity - 0.001 * latency, layouts)
            except ValueError:
                cache[partition] = (float("-inf"), None)
        return cache[partition]
    population = set()
    for count in range(1, upper + 1):
        for _ in range(population_size):
            item = initial_partition(model, count, rng)
            if item is not None:
                population.add(item)
    if not population:
        raise ValueError("No memory-feasible pipeline partition")
    for _ in range(generations):
        ranked = sorted(population, key=lambda p: (-evaluate(p)[0], p))
        elite = ranked[:population_size]
        children = set(elite)
        for parent in elite:
            for _ in range(3):
                children.add(mutate(model, parent, rng))
        population = children
    best = min(population, key=lambda p: (-evaluate(p)[0], p))
    score, layouts = evaluate(best)
    return {"partition": [list(group) for group in best], "layouts": layouts,
            "static_fitness": score, "candidate_count": len(cache),
            "ga_seed": seed, "generations": generations,
            "population_size": population_size,
            "fitness_limitation": "static bottleneck/latency proxy, not paper SLO simulator"}


def export(model: TopologyModel, template: Path, result: dict, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite candidate: {output}")
    output.mkdir(parents=True)
    records = []
    for index, layout in enumerate(result["layouts"]):
        nodes = layout["nodes"]
        spans = layout["spans"]
        folder = output / f"pipeline_{index}"
        folder.mkdir()
        solution = ConfigParser()
        solution["Settings"] = {"offset": "2"}
        solution["Solution"] = {
            f"compute_node_{node + 2}": repr(list(range(*spans[node])))
            for node in nodes
        }
        solution_path = folder / "solution.ini"
        with solution_path.open("w", encoding="utf-8") as stream:
            solution.write(stream)
        simulator = ConfigParser()
        if not simulator.read(template):
            raise FileNotFoundError(template)
        simulator["ComputeNodes"]["names"] = repr([f"compute_node_{n + 2}" for n in nodes])
        selected_sections = {f"compute_node_{n + 2}" for n in nodes}
        for section in list(simulator.sections()):
            if (section.startswith("compute_node_") and section not in selected_sections) or section.startswith("link_"):
                simulator.remove_section(section)
        for node in nodes:
            size = spans[node][1] - spans[node][0]
            simulator[f"compute_node_{node + 2}"]["kv_cache_capacity"] = str(
                model.manager.get_kv_cache_capacity(model.types[node], size))
        edges = [("source", nodes[0]), *zip(nodes, nodes[1:]), (nodes[-1], "sink")]
        link_names = []
        for left, right in edges:
            section = f"Link-{left}-{right}"
            if section not in model.config:
                section = f"Link-{right}-{left}"
            if section not in model.config:
                raise ValueError(f"No physical edge {left} -> {right}")
            left_name = left if left == "source" else f"compute_node_{left + 2}"
            right_name = right if right == "sink" else f"compute_node_{right + 2}"
            link_name = f"link_{left_name}_{right_name}"
            link_names.append(link_name)
            simulator[link_name] = {"in": left_name, "out": right_name,
                                    "latency": model.config[section]["latency"],
                                    "bandwidth": model.config[section]["bandwidth"]}
        simulator["Links"]["names"] = repr(link_names)
        cluster_path = folder / "simulator_cluster.ini"
        with cluster_path.open("w", encoding="utf-8") as stream:
            simulator.write(stream)
        records.append({"index": index, "nodes": nodes,
                        "spans": {str(n): list(spans[n]) for n in nodes},
                        "solution": solution_path.relative_to(output).as_posix(),
                        "sim_cluster": cluster_path.relative_to(output).as_posix(),
                        "solution_sha256": sha(solution_path),
                        "sim_cluster_sha256": sha(cluster_path),
                        "bottleneck_estimate_s": layout["bottleneck_estimate_s"],
                        "communication_estimate_s": layout["communication_estimate_s"]})
    manifest = {"status": "development_candidate", "algorithm": "HexGen-inspired GA+DP",
                "physical_cluster": model.cluster_file.relative_to(ROOT).as_posix(),
                "physical_sha256": sha(model.cluster_file),
                "template": template.relative_to(ROOT).as_posix(),
                "template_sha256": sha(template),
                "planner_sha256": sha(Path(__file__)),
                "paper_source_commit": "949414d1be18e504752508c0559cb966ddf999f4",
                "method_limitations": ["static fitness replaces paper's simulated SLO fitness",
                                       "ordered nodes are chosen by greedy link-aware ordering",
                                       "online request assignment not yet integrated"],
                "search": {key: value for key, value in result.items() if key not in ("layouts", "partition")},
                "pipelines": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=DEFAULTS)
    parser.add_argument("--seed", type=int, default=2403)
    parser.add_argument("--generations", type=int, default=8)
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    physical, template = DEFAULTS[args.case]
    model = TopologyModel(physical)
    result = optimize(model, args.seed, args.generations, args.population)
    output = args.output or HERE / "development" / args.case / f"seed{args.seed}"
    manifest = export(model, template, result, output)
    print(json.dumps({"output": str(output), "pipelines": len(manifest["pipelines"]),
                      "fitness": result["static_fitness"],
                      "candidates": result["candidate_count"]}, indent=2))


if __name__ == "__main__":
    main()

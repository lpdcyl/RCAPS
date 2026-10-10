"""Deterministic bottleneck-guided refinement of two layer-covering paths.

The initial graph placement is a feasible solution. Each iteration enumerates
integer layer transfers, adjacent stage swaps, and feasible shared-boundary
changes. A normalized surrogate combines the longest prefill path, decode
path, and per-resource demand. The best strict improvement is accepted.
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
from configparser import ConfigParser
from pathlib import Path

from simulator.event_simulator.utils import kbps, mbps, gbps, MilliSec, Sec
from simulator.model_manager.model_manager import ModelManager, ModelName
from experiments.graph_pipeline.model import interpolate_profile
from experiments.graph_pipeline.placement import MACHINES, ROOT, _node_types, save_layout


def scenario(variant):
    if variant == "single":
        base = ROOT / "examples/simulation"
        return base / "config/single24.ini", base / "layouts/ilp/simulator_cluster.ini"
    base = ROOT / "artifact_evaluation/distributed_clusters"
    return base / "config/3cluster24.ini", base / "layout_llama70b/ilp/simulator_cluster.ini"


class PlacementRefiner:
    def __init__(self, variant: str, initial: Path, prompt_tokens=1000, decode_batch=8):
        self.variant = variant
        self.cluster, self.sim_template = scenario(variant)
        self.model = ModelManager(ModelName.LLaMa70B, MACHINES)
        self.types = _node_types(self.cluster)
        self.capacity = {i: self.model.get_max_num_layers(kind) for i, kind in self.types.items()}
        self.total_layers = self.model.get_num_layers()
        self.prompt_tokens = prompt_tokens
        self.decode_batch = decode_batch
        layout = json.loads(initial.read_text(encoding="utf-8"))
        spans = {int(i): tuple(span) for i, span in layout["intervals"].items()}
        shared = layout["shared"]
        self.initial = {"shared": shared, "shared_length": spans[shared][1],
                        "paths": [sorted((i for i in branch if i in spans),
                                         key=lambda i: spans[i][0]) for branch in layout["branches"]],
                        "lengths": {i: end - start for i, (start, end) in spans.items() if i != shared}}
        self.links = ConfigParser()
        self.links.read(self.cluster)
        self.profile = {kind: self.model.get_profiling_results(kind) for kind in set(self.types.values())}
        self.regions = self._regions()

    def _regions(self):
        from experiments.graph_pipeline.placement import _regions
        return {i: index for index, group in enumerate(_regions(self.cluster, self.types)) for i in group}

    def _link(self, source, target):
        name = f"Link-{source}-{target}"
        if name not in self.links:
            name = f"Link-{target}-{source}"
        variables = {"kbps": kbps, "mbps": mbps, "gbps": gbps,
                     "MilliSec": MilliSec, "Sec": Sec}
        section = self.links[name]
        latency = eval(section["latency"], {"__builtins__": {}}, variables)
        bandwidth = eval(section["bandwidth"], {"__builtins__": {}}, variables)
        return latency, bandwidth

    def _intervals(self, state):
        shared = state["shared"]
        result = {shared: (0, state["shared_length"])}
        for path in state["paths"]:
            position = state["shared_length"]
            for node in path:
                length = state["lengths"][node]
                if not 1 <= length <= self.capacity[node]:
                    return None
                interval = (position, position + length)
                if node in result and result[node] != interval:
                    return None
                result[node] = interval
                position += length
            if position != self.total_layers:
                return None
        return result

    def metrics(self, state):
        if self._intervals(state) is None:
            return None
        shared = state["shared"]
        prompt_paths = []
        decode_paths = []
        resource_demand = []
        bottleneck = None
        for branch_index, path in enumerate(state["paths"]):
            prompt_total = decode_total = 0.0
            previous = "source"
            for node in [shared, *path, "sink"]:
                latency, bandwidth = self._link(previous, node)
                size = (self.model.get_model_token_size()
                        if previous == "source" or node == "sink" else
                        self.model.get_model_activation_size())
                prompt_transfer = latency + self.prompt_tokens * size / bandwidth
                decode_transfer = latency + size / bandwidth
                prompt_total += prompt_transfer
                decode_total += decode_transfer
                # Link occupancy excludes propagation delay; shared links serve both branches.
                edge_demand = size / bandwidth * (2 if previous == "source" else 1)
                resource_demand.append(edge_demand)
                if bottleneck is None or edge_demand > bottleneck[0]:
                    bottleneck = (edge_demand, f"link {previous}->{node}")
                if node != "sink":
                    length = state["shared_length"] if node == shared else state["lengths"][node]
                    profile = self.profile[self.types[node]]
                    prompt_compute = length * interpolate_profile(profile.prompt_bs2time,
                                                                  self.prompt_tokens)
                    decode_compute = length * interpolate_profile(profile.decode_bs2time,
                                                                  self.decode_batch)
                    prompt_total += prompt_compute
                    decode_total += decode_compute
                    compute_demand = max(prompt_compute / self.prompt_tokens,
                                         decode_compute / self.decode_batch)
                    if node == shared:
                        compute_demand *= 2
                    resource_demand.append(compute_demand)
                    if compute_demand > bottleneck[0]:
                        bottleneck = (compute_demand, f"compute {node}")
                previous = node
            prompt_paths.append(prompt_total)
            decode_paths.append(decode_total)
        return {"max_prefill_s": max(prompt_paths), "max_decode_batch_s": max(decode_paths),
                "max_resource_s_per_token": max(resource_demand),
                "bottleneck": bottleneck[1], "prefill_paths_s": prompt_paths,
                "decode_paths_s": decode_paths}

    def score(self, metrics, reference):
        return (0.40 * metrics["max_prefill_s"] / reference["max_prefill_s"] +
                0.35 * metrics["max_decode_batch_s"] / reference["max_decode_batch_s"] +
                0.25 * metrics["max_resource_s_per_token"] / reference["max_resource_s_per_token"])

    def neighbors(self, state):
        lengths = state["lengths"]
        for branch_index, path in enumerate(state["paths"]):
            # Transfer one layer from a loaded stage to any stage with spare VRAM.
            # Intermediate boundaries move together, preserving layer continuity.
            for source in path:
                if lengths[source] <= 1:
                    continue
                for target in path:
                    if source == target or lengths[target] >= self.capacity[target]:
                        continue
                    candidate = copy.deepcopy(state)
                    candidate["lengths"][source] -= 1
                    candidate["lengths"][target] += 1
                    yield f"branch{branch_index}: transfer 1 layer {source}->{target}", candidate
            # A swap changes the network edges without changing the layer budget.
            for position in range(len(path) - 1):
                candidate = copy.deepcopy(state)
                candidate["paths"][branch_index][position:position + 2] = [path[position + 1], path[position]]
                yield f"branch{branch_index}: swap {path[position]}<->{path[position + 1]}", candidate
        if state["shared_length"] > 1:
            a, b = state["paths"]
            for left in a:
                if lengths[left] >= self.capacity[left]:
                    continue
                for right in b:
                    if lengths[right] >= self.capacity[right]:
                        continue
                    candidate = copy.deepcopy(state)
                    candidate["shared_length"] -= 1
                    candidate["lengths"][left] += 1
                    candidate["lengths"][right] += 1
                    yield f"shared boundary -1; branches +1 on {left},{right}", candidate
        # An unused device can absorb a layer, allowing a shorter shared stage.
        unused = sorted(set(self.types) - {state["shared"]} -
                        set(state["paths"][0]) - set(state["paths"][1]))
        for device in unused:
            for branch_index, path in enumerate(state["paths"]):
                for donor in path:
                    if lengths[donor] <= 1:
                        continue
                    for position in (0, len(path)):
                        candidate = copy.deepcopy(state)
                        candidate["paths"][branch_index].insert(position, device)
                        candidate["lengths"][device] = 1
                        candidate["lengths"][donor] -= 1
                        yield f"branch{branch_index}: activate {device}, donor {donor}", candidate

    def search(self, max_steps=12):
        state = copy.deepcopy(self.initial)
        reference = self.metrics(state)
        if reference is None:
            raise ValueError("Initial placement is not a complete two-branch layer cover")
        current_score = self.score(reference, reference)
        trace = [{"step": 0, "move": "initial", "score": current_score, "metrics": reference}]
        for step in range(1, max_steps + 1):
            best = None
            for move, candidate in self.neighbors(state):
                metrics = self.metrics(candidate)
                if metrics is None:
                    continue
                score = self.score(metrics, reference)
                if score < current_score - 1e-8 and (best is None or score < best[0] - 1e-12):
                    best = (score, move, candidate, metrics)
            if best is None:
                break
            current_score, move, state, metrics = best
            trace.append({"step": step, "move": move, "score": current_score, "metrics": metrics})
        return state, trace

    def save(self, state, trace, destination):
        intervals = self._intervals(state)
        if intervals is None:
            raise ValueError("Search produced an invalid placement")
        layout = save_layout(self.cluster, self.sim_template, destination, self.variant,
                             self.types, self.model, state["shared"], state["paths"], intervals)
        report = {"algorithm": "deterministic best-improvement layer-boundary search",
                  "prompt_tokens": self.prompt_tokens, "decode_batch": self.decode_batch,
                  "weights": {"prefill": 0.40, "decode": 0.35, "resource": 0.25},
                  "steps": trace, "initial_score": trace[0]["score"],
                  "final_score": trace[-1]["score"], "layout": layout}
        (destination / "search_trace.json").write_text(json.dumps(report, indent=2) + "\n",
                                                       encoding="utf-8")
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["single", "multi"], required=True)
    parser.add_argument("--initial", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=12)
    args = parser.parse_args()
    refiner = PlacementRefiner(args.scenario, args.initial)
    state, trace = refiner.search(args.max_steps)
    report = refiner.save(state, trace, args.output_dir)
    print(json.dumps({"scenario": args.scenario, "steps": len(trace) - 1,
                      "initial_score": report["initial_score"],
                      "final_score": report["final_score"],
                      "moves": [item["move"] for item in trace[1:]]}, indent=2))


if __name__ == "__main__":
    main()

"""Produce a concrete, inspectable critical-path breakdown for each placed branch."""

from __future__ import annotations

import argparse
import json
from configparser import ConfigParser
from pathlib import Path

import numpy as np

from simulator.event_simulator.utils import mbps, gbps, kbps, MilliSec, Sec
from simulator.model_manager.model_manager import ModelManager, ModelName
from experiments.graph_pipeline.placement import MACHINES, ROOT, _node_types
from experiments.graph_pipeline.model import EventDagModel


def _profile_time(points, tokens):
    keys = sorted(points)
    return float(np.interp(tokens, keys, [points[key] for key in keys]))


def explain(variant, placement_file: Path, prompt_tokens=1000, decode_batch=8):
    placement = json.loads(placement_file.read_text(encoding="utf-8"))
    base = ROOT / ("examples/simulation" if variant == "single" else
                   "artifact_evaluation/distributed_clusters")
    config_path = base / ("config/single24.ini" if variant == "single" else
                          "config/3cluster24.ini")
    types = _node_types(config_path)
    config = ConfigParser()
    config.read(config_path)
    model = ModelManager(ModelName.LLaMa70B, MACHINES)
    spans = {int(i): span for i, span in placement["intervals"].items()}
    shared = placement["shared"]
    def link_cost(src, dst, bytes_per_token):
        name = f"Link-{src}-{dst}"
        if name not in config:
            name = f"Link-{dst}-{src}"
        variables = {"mbps": mbps, "gbps": gbps, "kbps": kbps,
                     "MilliSec": MilliSec, "Sec": Sec}
        latency = eval(config[name]["latency"], {"__builtins__": {}}, variables)
        bandwidth = eval(config[name]["bandwidth"], {"__builtins__": {}}, variables)
        return latency + prompt_tokens * bytes_per_token / bandwidth
    results = []
    for branch in placement["branches"]:
        ordered = sorted((i for i in branch if i in spans), key=lambda i: spans[i][0])
        path = [shared, *ordered]
        stages = []
        previous = "source"
        for i in path:
            start, end = spans[i]
            profile = model.get_profiling_results(types[i])
            compute = (end - start) * _profile_time(profile.prompt_bs2time, prompt_tokens)
            decode = (end - start) * _profile_time(profile.decode_bs2time, decode_batch)
            transfer = link_cost(previous, i, model.get_model_token_size() if previous == "source"
                                 else model.get_model_activation_size())
            stages.append({"node": i, "type": types[i], "layers": [start, end],
                           "compute_s": compute, "decode_batch_s": decode,
                           "transfer_s": transfer, "queue_s": 0.0})
            previous = i
        stages.append({"node": "sink", "compute_s": 0.0, "decode_batch_s": 0.0,
                       "transfer_s": link_cost(previous, "sink", model.get_model_token_size()),
                       "queue_s": 0.0})
        summary = EventDagModel.describe_path(stages)
        summary["path_nodes"] = path
        summary["bottleneck_node"] = max(stages[:-1],
                                          key=lambda stage: stage["compute_s"] + stage["transfer_s"])["node"]
        results.append(summary)
    return {"scenario": variant, "prompt_tokens": prompt_tokens,
            "decode_batch": decode_batch, "branches": results,
            "note": "Queue-free reference estimate; online routing adds measured occupancy."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["single", "multi"], required=True)
    parser.add_argument("--placement", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = explain(args.scenario, args.placement)
    content = json.dumps(result, indent=2)
    print(content)
    if args.output:
        args.output.write_text(content + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Read-only resource feasibility audit for external simulator baselines.

This checks only the full-model pipeline memory constraint. A positive result
does not imply that a connected layout or an end-to-end implementation exists.
"""

from __future__ import annotations

import hashlib
import json
from configparser import ConfigParser
from pathlib import Path

from benchmarks.layout import scenario
from rcaps.v3.topology import TopologyModel
from simulator.event_simulator.utils import MB


ROOT = Path(__file__).resolve().parents[2]
CASES = {
    "single24": (scenario("single")[0], scenario("single")[3]),
    "multi24": (scenario("multi")[0], scenario("multi")[3]),
    "high_heterogeneity42": (
        ROOT / "artifact_evaluation/high_heterogeneity/config/cluster42.ini",
        ROOT / "artifact_evaluation/high_heterogeneity/layout_llama70b/ilp/simulator_cluster.ini",
    ),
}


def audit() -> dict:
    results = {}
    for name, (path, template) in CASES.items():
        topology = TopologyModel(path)
        available = sum(topology.capacity.values())
        layers = topology.layers
        config = ConfigParser()
        if not config.read(template):
            raise FileNotFoundError(template)
        node_memory = []
        for section in config.sections():
            if section.startswith("compute_node_"):
                amount, unit = (part.strip() for part in config[section]["vram_size"].split("*"))
                if unit != "MB":
                    raise ValueError(f"Unexpected VRAM unit {unit}")
                node_memory.append(float(amount) * MB)
        weights_bytes = sum(topology.manager.get_model_params())
        max_node_vram = max(node_memory)
        results[name] = {
            "physical_cluster": path.relative_to(ROOT).as_posix(),
            "physical_cluster_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "model_layers": layers,
            "machine_counts": topology.machine_counts,
            "nodes": len(topology.types),
            "full_layer_slots": available,
            "max_full_model_replicas_memory_only": available // layers,
            "two_replicas_memory_necessary": available >= 2 * layers,
            "model_weight_bytes": weights_bytes,
            "max_single_machine_vram_bytes": max_node_vram,
            "hexgen3_full_worker_fits_one_machine": weights_bytes <= max_node_vram,
            "hexgen3_note": "Paper local strategies use DP/TP/EP with TP and EP confined to one machine; no PP within a worker. Every prefill worker needs the full model weights. This necessary test assumes the current model precision and topology.",
            "interpretation": "necessary memory test only; link reachability, KV and execution not established",
        }
    return results


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))

"""Build paired Helix/GREEN layouts under scaled inter-cluster RTT."""

from __future__ import annotations

import argparse
import json
from configparser import ConfigParser
from pathlib import Path

from experiments.critical_graph.partition import initial_partition, refine, save
from experiments.critical_graph.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "network_layouts"
PHYSICAL = ROOT / "artifact_evaluation/distributed_clusters/config/3cluster24.ini"
HELIX = ROOT / "artifact_evaluation/distributed_clusters/layout_llama70b/ilp"
GREEN = ROOT / "experiments/critical_graph/runs/multi_final"


def region(node: int) -> int:
    return 0 if node < 4 else 1 if node < 14 else 2


def scaled(text: str, factor: float) -> str:
    value, unit = (part.strip() for part in text.split("*", 1))
    return f"{float(value) * factor:.12g} * {unit}"


def write_config(config: ConfigParser, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        config.write(stream)


def prepare(factor: float) -> dict:
    if factor <= 0:
        raise ValueError("RTT factor must be positive")
    label = f"rtt_{factor:g}x".replace(".", "p")
    target = OUT / label
    physical = ConfigParser()
    physical.read(PHYSICAL)
    physical_count = 0
    for section in physical.sections():
        parts = section.split("-")
        if (len(parts) == 3 and parts[0] == "Link" and
                parts[1].isdigit() and parts[2].isdigit() and
                region(int(parts[1])) != region(int(parts[2]))):
            physical[section]["latency"] = scaled(physical[section]["latency"], factor)
            physical_count += 1
    physical_file = target / "physical_cluster.ini"
    write_config(physical, physical_file)

    helix = ConfigParser()
    helix.read(HELIX / "simulator_cluster.ini")
    simulator_count = 0
    for section in helix.sections():
        if not section.startswith("link_"):
            continue
        source, sink = helix[section]["in"], helix[section]["out"]
        if source.startswith("compute_node_") and sink.startswith("compute_node_"):
            left = int(source.removeprefix("compute_node_")) - 2
            right = int(sink.removeprefix("compute_node_")) - 2
            if region(left) != region(right):
                helix[section]["latency"] = scaled(helix[section]["latency"], factor)
                simulator_count += 1
    helix_dir = target / "helix"
    write_config(helix, helix_dir / "simulator_cluster.ini")
    # The official layer assignment stays fixed; Helix did not optimize for
    # modified RTT. GREEN is regenerated using the same physical topology.
    (helix_dir / "ilp_sol.ini").write_bytes((HELIX / "ilp_sol.ini").read_bytes())

    model = TopologyModel(physical_file)
    partition, trace = refine(model, initial_partition(model))
    placement = save(model, GREEN / "simulator_cluster.ini", partition,
                     target / "green", trace)
    metadata = {
        "factor": factor, "physical_cluster": str(physical_file),
        "physical_cross_links_scaled": physical_count,
        "helix_simulator_cross_links_scaled": simulator_count,
        "green_demand_mode": placement["demand_mode"],
        "green_refinement_moves": len(trace) - 1,
        "green_intervals": placement["intervals"],
    }
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n",
                                           encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factors", type=float, nargs="+", default=[0.5, 2.0])
    args = parser.parse_args()
    for factor in args.factors:
        print(json.dumps(prepare(factor)), flush=True)


if __name__ == "__main__":
    main()

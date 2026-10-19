"""Derive the fixed 4 A100 / 6 L4 / 12 T4 pool from C1 single."""

from __future__ import annotations

import ast
from configparser import ConfigParser
from pathlib import Path

from rcaps.v3.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PHYSICAL = HERE / "physical22.ini"
TEMPLATE = HERE / "simulator22.ini"
REMOVED = (21, 23)


def _write(config: ConfigParser, path: Path) -> None:
    with path.open("w", encoding="utf-8") as stream:
        config.write(stream)


def prepare() -> tuple[Path, Path]:
    original = ConfigParser()
    if not original.read(ROOT / "examples/simulation/config/single24.ini"):
        raise FileNotFoundError("C1 physical pool")
    if any(original[f"ComputeNode-{node}"]["type"] != "L4" for node in REMOVED):
        raise ValueError("The two predetermined removals are not L4")
    retained = tuple(node for node in range(24) if node not in REMOVED)
    mapping = {old: new for new, old in enumerate(retained)}
    pool = ConfigParser()
    pool["NodeNames"] = {"total_compute_nodes": str(len(retained))}
    for section in ("SourceNode", "SinkNode"):
        pool[section] = {"connected_nodes": repr(list(range(len(retained))))}
    for old, new in mapping.items():
        neighbors = ast.literal_eval(original[f"ComputeNode-{old}"]["connected_nodes"])
        pool[f"ComputeNode-{new}"] = {
            "type": original[f"ComputeNode-{old}"]["type"],
            "connected_nodes": repr([mapping[item] if isinstance(item, int) else item
                                      for item in neighbors if not isinstance(item, int)
                                      or item in mapping])}
    for section in original.sections():
        if not section.startswith("Link-"):
            continue
        _, left, right = section.split("-", 2)
        endpoints = (left, right)
        if any(item.isdigit() and int(item) not in mapping for item in endpoints):
            continue
        new_name = "Link-" + "-".join(str(mapping[int(item)]) if item.isdigit()
                                           else item for item in endpoints)
        pool[new_name] = dict(original[section])
    _write(pool, PHYSICAL)

    source = ConfigParser()
    if not source.read(ROOT / "examples/simulation/layouts/ilp/simulator_cluster.ini"):
        raise FileNotFoundError("C1 simulator template")
    template = ConfigParser()
    for section in ("Coordinator", "MachineTypes"):
        template[section] = dict(source[section])
    template["ComputeNodes"] = {"names": repr([f"compute_node_{node + 2}"
                                                 for node in range(len(retained))])}
    for old, new in mapping.items():
        template[f"compute_node_{new + 2}"] = dict(source[f"compute_node_{old + 2}"])
    template["Links"] = {"names": "[]"}
    _write(template, TEMPLATE)
    model = TopologyModel(PHYSICAL)
    if model.machine_counts != {"L4": 6, "T4": 12, "A100": 4}:
        raise ValueError(f"Unexpected stress pool: {model.machine_counts}")
    if sum(model.capacity.values()) != 138:
        raise ValueError("Stress pool layer capacity changed")
    return PHYSICAL, TEMPLATE


if __name__ == "__main__":
    print(prepare())

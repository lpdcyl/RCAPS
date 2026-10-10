"""Validate generated V2 layouts against the physical 24-GPU topology."""

from __future__ import annotations

import ast
import hashlib
import json
from configparser import ConfigParser
from pathlib import Path

from rcaps.placement.adaptive import has_link, intervals
from rcaps.placement.partition import scenario
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    report = {}
    for name in ("single", "multi"):
        cluster, _ = scenario(name)
        model = TopologyModel(cluster)
        for variant in ("adaptive", "fixed"):
            directory = ROOT / "rcaps" / "v2_layouts" / f"{name}_{variant}"
            placement = json.loads((directory / "placement.json").read_text(encoding="utf-8"))
            spans = {int(node): tuple(span) for node, span in placement["intervals"].items()}
            state = {"stem": placement["stem"], "prefix_layers": placement["prefix_layers"],
                     "branches": placement["branches"],
                     "lengths": {node: end - start for node, (start, end) in spans.items()}}
            if spans != intervals(model, state):
                raise ValueError(f"Interval mismatch: {name} {variant}")
            if variant == "fixed" and (len(state["stem"]) != 1 or
                                       state["prefix_layers"] != 12 or
                                       len(state["branches"]) != 2):
                raise ValueError(f"Fixed-structure control escaped its constraints: {name}")
            solution = ConfigParser()
            solution_file = directory / "solution.ini"
            if not solution.read(solution_file):
                raise FileNotFoundError(solution_file)
            for node, (start, end) in spans.items():
                actual = ast.literal_eval(solution["Solution"][f"compute_node_{node + 2}"])
                if actual != list(range(start, end)):
                    raise ValueError(f"Serialized layers differ: {name} {variant} GPU {node}")
            sim = ConfigParser()
            sim_file = directory / "simulator_cluster.ini"
            if not sim.read(sim_file):
                raise FileNotFoundError(sim_file)
            exported = set()
            for section in sim.sections():
                if not section.startswith("link_"):
                    continue
                left = sim[section]["in"]
                right = sim[section]["out"]
                left_node = left if left == "source" else int(left.removeprefix("compute_node_")) - 2
                right_node = right if right == "sink" else int(right.removeprefix("compute_node_")) - 2
                if not has_link(model, left_node, right_node):
                    raise ValueError(f"Nonphysical edge: {name} {variant} {section}")
                exported.add((left_node, right_node))
            canonical = [("source", state["stem"][0])]
            canonical += list(zip(state["stem"], state["stem"][1:]))
            for branch in state["branches"]:
                canonical.append((state["stem"][-1], branch[0]))
                canonical.extend(zip(branch, branch[1:]))
                canonical.append((branch[-1], "sink"))
            if not set(canonical) <= exported:
                raise ValueError(f"Canonical route missing in export: {name} {variant}")
            report[f"{name}_{variant}"] = {
                "active_gpus": len(spans), "prefix_layers": state["prefix_layers"],
                "branches": len(state["branches"]),
                "layer_copies": sum(end - start for start, end in spans.values()),
                "solution_sha256": digest(solution_file),
                "sim_cluster_sha256": digest(sim_file),
            }
    path = Path(__file__).resolve().parent / "layout_audit.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

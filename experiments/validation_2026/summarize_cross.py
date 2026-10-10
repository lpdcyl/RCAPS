"""Compute paired 2x2 layout/scheduler effects without assuming additivity."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from configparser import ConfigParser
from pathlib import Path
from statistics import mean, stdev

from baselines.helix import layout as helix_layout
from rcaps.placement.topology import TopologyModel, UNITS
from rcaps.method import layout as rcaps_layout
from simulator.event_simulator.utils import MB


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CELLS = {
    "HH": ("helix", "helix"),
    "HR": ("helix", "rcaps"),
    "RH": ("rcaps", "helix"),
    "RR": ("rcaps", "rcaps"),
}
METRICS = {
    "output_throughput_tokens_per_s": 1,
    "ttft_p95_s": -1,
    "tpot_p95_s": -1,
    "completion_fraction": 1,
    "backlog_at_window_end": -1,
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def path_for(scenario: str, seed: int, cell: str) -> Path:
    if cell == "HH":
        return ROOT / "benchmarks/runs" / scenario / f"seed{seed}" / "helix.json"
    if cell == "RR":
        return HERE / "runs70b" / scenario / f"seed{seed}" / "rcaps.json"
    arm = ("helix_layout_rcaps_scheduler" if cell == "HR" else
           "rcaps_layout_helix_scheduler")
    return HERE / "cross_runs70b" / scenario / f"seed{seed}" / f"{arm}.json"


def stats(values: dict[int, float]) -> dict:
    ordered = sorted(values.items())
    observed = [value for _, value in ordered]
    return {"seed_ids": [seed for seed, _ in ordered],
            "by_seed": observed, "n": len(observed),
            "mean": mean(observed) if observed else None,
            "sd": stdev(observed) if len(observed) > 1 else None}


def used_gpus(solution: Path) -> int:
    config = ConfigParser()
    if not config.read(solution):
        raise FileNotFoundError(solution)
    return sum(bool(ast.literal_eval(layers))
               for layers in config["Solution"].values())


def layout_for(scenario: str, cell: str) -> tuple[Path, Path]:
    return (helix_layout if CELLS[cell][0] == "helix" else rcaps_layout)(
        scenario, ROOT)


def validate_physical_topology(scenario: str, helix_file: Path,
                               rcaps_file: Path) -> dict:
    configs = []
    for path in (helix_file, rcaps_file):
        config = ConfigParser()
        if not config.read(path):
            raise FileNotFoundError(path)
        configs.append(config)
    helix, rcaps = configs
    hardware_fields = ("machine_type", "vram_size", "inbound_nic_speed",
                       "outbound_nic_speed", "disk_speed")
    for node in range(2, 26):
        section = f"compute_node_{node}"
        for field in hardware_fields:
            h = eval(helix[section][field], {"__builtins__": {}}, {**UNITS, "MB": MB})
            r = eval(rcaps[section][field], {"__builtins__": {}}, {**UNITS, "MB": MB})
            if h != r:
                raise ValueError(f"{scenario}: hardware mismatch {section}.{field}")
    physical = (ROOT / "examples/simulation/config/single24.ini" if scenario == "single"
                else ROOT / "artifact_evaluation/distributed_clusters/config/3cluster24.ini")
    model = TopologyModel(physical)
    edge_counts = {}
    for placement, config in (("helix", helix), ("rcaps", rcaps)):
        links = [section for section in config.sections()
                 if section.startswith("link_")]
        for section in links:
            values = config[section]
            endpoints = [values[key] for key in ("in", "out")]
            mapped = [str(int(node.removeprefix("compute_node_")) - 2)
                      if node.startswith("compute_node_") else node
                      for node in endpoints]
            physical_latency, physical_bandwidth = model.link(*mapped)
            latency = eval(values["latency"], {"__builtins__": {}}, UNITS)
            bandwidth = eval(values["bandwidth"], {"__builtins__": {}}, UNITS)
            if abs(latency - physical_latency) > 1e-12 or abs(bandwidth - physical_bandwidth) > 1e-6:
                raise ValueError(f"{scenario}: nonphysical link {section}")
        edge_counts[placement] = len(links)
    return {"hardware_identical": True,
            "all_exported_links_match_physical_topology": True,
            "enabled_layout_edges": edge_counts,
            "physical_topology_file": str(physical)}


def validate(scenario: str, seed: int, rows: dict[str, dict]) -> None:
    fields = ("trace_sha256", "arrivals", "duration_s", "warmup_s",
              "offered_tokens_per_s", "evaluation_protocol")
    for field in fields:
        if len({row[field] for row in rows.values()}) != 1:
            raise ValueError(f"{scenario} seed{seed}: unequal {field}")
    for left, right in (("HH", "HR"), ("RH", "RR")):
        if left not in rows or right not in rows:
            continue
        for field in ("solution_sha256", "sim_cluster_sha256"):
            if rows[left][field] != rows[right][field]:
                raise ValueError(f"{scenario} seed{seed}: {left}/{right} "
                                 f"layout mismatch in {field}")
    for cell, row in rows.items():
        if row["seed"] != seed or row["scenario"] != scenario:
            raise ValueError(f"Wrong scenario or seed: {cell}")
        solution, sim_cluster = layout_for(scenario, cell)
        if used_gpus(solution) != 24:
            raise ValueError(f"{scenario} seed{seed} {cell}: not all 24 GPUs used")
        for path, hash_key in ((solution, "solution_sha256"),
                               (sim_cluster, "sim_cluster_sha256")):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != row[hash_key]:
                raise ValueError(f"{scenario} seed{seed} {cell}: stale {path}")


def collect() -> dict:
    output = {}
    for scenario in ("single", "multi"):
        seeds = {}
        for seed in (0, 1, 2):
            rows = {cell: load(path_for(scenario, seed, cell)) for cell in CELLS
                    if path_for(scenario, seed, cell).exists()}
            if not {"HH", "HR", "RR"}.issubset(rows):
                raise ValueError(f"{scenario} seed{seed}: required HH/HR/RR result missing")
            validate(scenario, seed, rows)
            seeds[str(seed)] = rows
        table = {cell: {metric: stats({seed: seeds[str(seed)][cell][metric]
                                      for seed in (0, 1, 2)
                                      if cell in seeds[str(seed)]})
                        for metric in METRICS}
                 for cell in CELLS}
        physical_topology = validate_physical_topology(
            scenario, layout_for(scenario, "HH")[1],
            layout_for(scenario, "RR")[1])
        effects = {}
        for metric, direction in METRICS.items():
            values = {name: {} for name in (
                "placement_with_helix_scheduler",
                "placement_with_rcaps_scheduler",
                "scheduler_on_helix_layout",
                "scheduler_on_rcaps_layout",
                "placement_symmetric_share", "scheduler_symmetric_share",
                "interaction", "total_RR_over_HH")}
            for seed in (0, 1, 2):
                rows = seeds[str(seed)]
                hh, hr, rr = (direction * rows[cell][metric]
                              for cell in ("HH", "HR", "RR"))
                p_r, s_h = rr - hr, hr - hh
                values["placement_with_rcaps_scheduler"][seed] = p_r
                values["scheduler_on_helix_layout"][seed] = s_h
                values["total_RR_over_HH"][seed] = rr - hh
                if abs(p_r + s_h - (rr - hh)) > 1e-7:
                    raise AssertionError("Three-cell decomposition failed")
                if "RH" in rows:
                    rh = direction * rows["RH"][metric]
                    p_h, s_r = rh - hh, rr - rh
                    values["placement_with_helix_scheduler"][seed] = p_h
                    values["scheduler_on_rcaps_layout"][seed] = s_r
                    values["placement_symmetric_share"][seed] = (p_h + p_r) / 2
                    values["scheduler_symmetric_share"][seed] = (s_h + s_r) / 2
                    values["interaction"][seed] = rr - rh - hr + hh
                    if abs((p_h + p_r + s_h + s_r) / 2 - (rr - hh)) > 1e-7:
                        raise AssertionError("2x2 decomposition failed")
            effects[metric] = {name: stats(items) for name, items in values.items()}
        output[scenario] = {
            "cell_mean": table,
            "effects_positive_means_better": effects,
            "trace_sha256_by_seed": {seed: rows["HH"]["trace_sha256"]
                                     for seed, rows in seeds.items()},
            "arrivals_by_seed": {seed: rows["HH"]["arrivals"]
                                 for seed, rows in seeds.items()},
            "missing_cells_by_seed": {seed: sorted(set(CELLS) - set(rows))
                                      for seed, rows in seeds.items()},
            "physical_topology_validation": physical_topology,
        }
    return {"design": {key: {"placement": value[0], "scheduler": value[1]}
                       for key, value in CELLS.items()},
            "seeds": [0, 1, 2], "scenarios": output,
            "effect_sign": "positive means higher throughput/completion or lower latency/backlog",
            "interpretation": "Conditional effects can differ; symmetric shares average both contexts and are descriptive, not unique causal attribution",
            "statistical_significance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "cross_summary.json")
    args = parser.parse_args()
    args.output.write_text(json.dumps(collect(), indent=2) + "\n",
                           encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

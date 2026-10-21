"""Generalization of slow-link-gated path admission beyond the C1 test.

Conditions (frozen V3 layouts, no re-planning; the rule under test is M3's):
  C2, C3            flat 1000 Mbps pools (no slow link: gated == canonical)
  C1_multi_bw0.5    C1 three-cluster, every link <= 50 Mbps (cross-cluster,
  C1_multi_bw2      including source/sink) scaled by 0.5 or 2

Cells: frozen V3 rerun here (same-environment control) and the gated rule
(experiments/v3_gated_pathspace/scheduler.py, unchanged).

Phases: audit | smoke | formal | report.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import json
import os
import traceback
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from configparser import ConfigParser
from functools import partial
from pathlib import Path

from experiments.v3_cycle_pricing.run import (
    FORMAL_SEEDS, ROOT, digest, physical_input, read, rel, scheduler_factory, write)

HERE = Path(__file__).resolve().parent
GATED = ROOT / "experiments/v3_gated_pathspace/scheduler.py"
SLOW_MBPS = 50.0  # same threshold as SLOW_LINK_BPS in the gated scheduler
CONDITIONS = {
    "C2": {"case": "C2", "load": 160.0, "bandwidth": 1.0},
    "C3": {"case": "C3", "load": 400.0, "bandwidth": 1.0},
    "C1_multi_bw0.5": {"case": "C1_multi", "load": 320.0, "bandwidth": 0.5},
    "C1_multi_bw2": {"case": "C1_multi", "load": 320.0, "bandwidth": 2.0},
}
CELLS = ("v3", "gated")


def layout_dir(case: str) -> Path:
    return ROOT / "rcaps/v3_layouts" / case.removeprefix("C1_")


def sim_cluster(condition: str) -> Path:
    """Frozen simulator cluster, or a copy with slow links scaled."""
    spec = CONDITIONS[condition]
    source = layout_dir(spec["case"]) / "simulator_cluster.ini"
    if spec["bandwidth"] == 1.0:
        return source
    destination = HERE / "derived_configs" / f"{condition}.ini"
    config = ConfigParser(interpolation=None)
    config.read(source)
    scaled = 0
    for section in ast.literal_eval(config["Links"]["names"]):
        value, unit = config[section]["bandwidth"].split(" * ", maxsplit=1)
        if unit.strip() != "mbps":
            raise ValueError(f"Unexpected bandwidth unit in {section}")
        if float(value) <= SLOW_MBPS:
            config[section]["bandwidth"] = f"{float(value) * spec['bandwidth']:g} * {unit}"
            scaled += 1
    if not scaled:
        raise ValueError(f"No slow link to scale for {condition}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        config.write(handle)
    return destination


def runtime(condition: str) -> dict:
    spec = CONDITIONS[condition]
    physical, scenario = physical_input(spec["case"])
    c1 = spec["case"].startswith("C1_")
    return {"physical": physical, "topology": scenario if c1 else "single",
            "profile": None if c1 else ROOT / "examples/simulation/config/machine_profile.ini",
            "solution": layout_dir(spec["case"]) / "solution.ini",
            "sim_cluster": sim_cluster(condition)}


def builder(condition: str, cell: str):
    from experiments.v3_cycle_pricing.scheduler import RecordedV3Scheduler
    from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
    if cell == "v3":
        return RecordedV3Scheduler
    canonical = scheduler_factory(CONDITIONS[condition]["case"], "canonical").keywords["allowed_edges"]
    return partial(SlowLinkGatedScheduler, allowed_edges=canonical)


def run_one(condition: str, cell: str, seed: int, duration: int, output: Path) -> str:
    if output.exists():
        return rel(output)
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase

    info = runtime(condition)
    base = builder(condition, cell)
    holder = {}
    stats = defaultdict(lambda: [0, 0, 0])

    def factory(simulator):
        for node in simulator.compute_nodes.values():
            original = node.start_execution

            def start_execution(requests, _original=original, _uid=node.node_uid):
                decodes = sum(r.phase == RequestPhase.Increment for r in requests)
                if decodes:
                    record = stats[_uid]
                    record[0] += 1
                    record[1] += decodes
                    record[2] += decodes == 1
                return _original(requests)

            node.start_execution = start_execution
        holder["scheduler"] = base(simulator)
        return holder["scheduler"]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as stream, \
            contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            row = fixed_window.run(
                info["topology"], "queue_dag", CONDITIONS[condition]["load"], duration, 0, seed,
                info["solution"], info["sim_cluster"], profile_resources=True, compact=True,
                record_query_samples=True, physical_cluster=info["physical"],
                machine_profile=info["profile"],
                machine_counts=TopologyModel(info["physical"]).machine_counts,
                scheduler_factory=factory)
        except Exception as error:
            traceback.print_exc(file=stream)
            write(output.with_suffix(".failure.json"),
                  {"condition": condition, "cell": cell, "seed": seed,
                   "error": repr(error), "traceback": traceback.format_exc()})
            raise
    executions = sum(s[0] for s in stats.values())
    scheduler = holder["scheduler"]
    row.update({"condition": condition, "cell": cell, "seed": seed, "duration_s": duration,
                "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                "gated_scheduler_sha256": digest(GATED),
                "solution_sha256": digest(info["solution"]),
                "sim_cluster_sha256": digest(info["sim_cluster"]),
                "physical_sha256": digest(info["physical"]),
                "admitted_edges": len(getattr(scheduler, "allowed_edges", ()) or ()),
                "decode_batches": {
                    "executions": executions,
                    "mean_batch": sum(s[1] for s in stats.values()) / max(1, executions),
                    "single_share": sum(s[2] for s in stats.values()) / max(1, executions)}})
    write(output, row)
    return rel(output)


def audit() -> dict:
    """Admitted edges per condition from an instantiated deployment."""
    from benchmarks.fixed_window import ModelName, load_graph_layout
    from rcaps.v3.resource_graph import from_simulator
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.cluster_simulator import ClusterSimulator

    result = {"gated_scheduler_sha256": digest(GATED), "conditions": {}}
    for condition, spec in CONDITIONS.items():
        info = runtime(condition)
        sim = ClusterSimulator(model_name=ModelName.LLaMa70B,
                               machine_num_dict=TopologyModel(info["physical"]).machine_counts)
        sim.from_ini_file(config_file_name=str(info["sim_cluster"]))
        scheduler = builder(condition, "gated")(sim)
        sim.set_scheduler(scheduler)
        sim.init_query_manager()
        sim.mark_as_ready()
        load_graph_layout(sim, info["solution"])
        scheduler._allow_placement_edge(sim.source_node.node_uid, 0)
        dag = from_simulator(sim)
        bandwidth = {(l.node_in.node_uid, l.node_out.node_uid): l.bandwidth for l in sim.links.values()}
        slow_links = sorted(v for v in bandwidth.values() if v <= 50_000_000)
        result["conditions"][condition] = {
            **spec, "sim_cluster": rel(info["sim_cluster"]),
            "sim_cluster_sha256": digest(info["sim_cluster"]),
            "full_edges": len(dag.edge_set), "canonical_edges": len(scheduler.canonical_edges),
            "admitted_edges": len(scheduler.allowed_edges),
            "detours": sorted([a, b] for a, b in scheduler.detour_edges),
            "slow_links": len(slow_links),
            "slow_link_Bps_range": [slow_links[0], slow_links[-1]] if slow_links else None}
    write(HERE / "audit.json", result)
    return result


def jobs(phase: str) -> list:
    if phase == "smoke":
        return [(c, cell, 100, 60, HERE / "runs/smoke" / c / f"{cell}.json")
                for c in CONDITIONS for cell in CELLS]
    return [(c, cell, seed, 1800, HERE / "runs/formal" / c / f"{cell}_seed{seed}.json")
            for seed in FORMAL_SEEDS for c in CONDITIONS for cell in CELLS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("audit", "smoke", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.phase == "audit":
        print(json.dumps(audit(), indent=2))
        return
    if args.phase == "report":
        from experiments.v3_gated_generalization.report import main as report
        report()
        return
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    if args.phase == "formal" and not (HERE / "protocol.json").exists():
        raise SystemExit("protocol.json must be committed before formal runs")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs(args.phase)}
        for future in as_completed(futures):
            try:
                print("done", future.result(), flush=True)
            except Exception as error:
                print("failed", futures[future][:3], repr(error), flush=True)


if __name__ == "__main__":
    main()

"""Run paired path-space/load/network windows on the frozen C1_multi layout."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import traceback
from collections import defaultdict
from functools import partial
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
PHYSICAL_REL = "artifact_evaluation/distributed_clusters/config/3cluster24.ini"
DEPLOY = ROOT / "rcaps/v3_layouts/multi"
LOADS = {"low": 50.0, "middle": 160.0, "high": 320.0}
NETWORKS = {"nominal": 1.0, "crosslink_4x": 4.0}
CELLS = ("canonical", "partial", "full")
FORMAL_SEEDS = (0, 1, 2)
SLOW_LINK_BPS = 50_000_000
FROZEN_SOURCES = (
    "benchmarks/fixed_window.py",
    "rcaps/v3/resource_graph.py",
    "rcaps/v3/scheduler.py",
    "rcaps/v3/routing.py",
    "rcaps/v3/queue_cost.py",
    "rcaps/v3/online_scheduler.py",
    "experiments/v3_pathspace_ablation/run.py",
    "experiments/v3_gated_pathspace/scheduler.py",
    "experiments/v3_gated_pathspace/audit.json",
    "experiments/v3_cluster42/kv_admission.py",
    "experiments/v3_dynamic_pathspace/scheduler.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def protocol_hash() -> str:
    return digest(HERE / "protocol.json")


def load_context():
    from experiments.v3_cycle_pricing.run import physical_input
    from experiments.m2_multistage_candidate.placement import validate
    from experiments.v3_pathspace_ablation.run import canonical_edges
    from rcaps.v3.resource_graph import LayerCompatibilityDag
    from rcaps.v3.topology import TopologyModel

    physical, topology = physical_input("C1_multi")
    state_path = DEPLOY / "placement.json"
    state = read(state_path)["state"]
    checked = validate(TopologyModel(physical), state)
    full = checked["dag"]
    canonical = canonical_edges(state, full)
    gated_audit = read(ROOT / "experiments/v3_gated_pathspace/audit.json")
    info = gated_audit["cases"]["C1_multi"]
    # gated_pathspace's audit records simulator node IDs; placement.json and
    # LayerCompatibilityDag use zero-based GPU IDs.
    detours = {tuple(node - 2 for node in item["edge"])
               for item in info["detours"]}
    partial_gpu = canonical | detours
    if len(detours) != 4 or not partial_gpu <= full.edge_set:
        raise ValueError("Frozen partial path space does not match the registered four detours")
    partial_edges = LayerCompatibilityDag(
        full.spans, tuple(sorted(partial_gpu, key=str)), full.layers)
    if partial_edges.path_count() == 0:
        raise ValueError("Partial path space has no complete execution route")

    # Simulator IDs are the graph's GPU IDs plus the fixed coordinator offset.
    offset = 2
    def translate(edges):
        return frozenset((a if isinstance(a, str) else a + offset,
                          b if isinstance(b, str) else b + offset) for a, b in edges)

    return {
        "physical": physical,
        "topology": topology,
        "state": state,
        "full_dag": full,
        "canonical_edges": translate(canonical),
        "partial_edges": translate(partial_gpu),
        "full_path_count": full.path_count(),
        "canonical_path_count": LayerCompatibilityDag(
            full.spans, tuple(sorted(canonical, key=str)), full.layers).path_count(),
        "partial_path_count": partial_edges.path_count(),
        "detours": sorted([list(edge) for edge in detours]),
    }


def audit() -> dict:
    context = load_context()
    from simulator.event_simulator.base_node import NodeType
    from benchmarks.fixed_window import ClusterSimulator, ModelName

    simulator = ClusterSimulator(model_name=ModelName.LLaMa70B,
                                 machine_num_dict={"A100": 4, "L4": 8, "T4": 12})
    simulator.from_ini_file(config_file_name=str(DEPLOY / "simulator_cluster.ini"))
    selected = []
    for link in simulator.links.values():
        if (link.node_in_type == NodeType.Compute and
                link.node_out_type == NodeType.Compute and
                link.bandwidth <= SLOW_LINK_BPS):
            selected.append({"link_uid": link.link_uid,
                             "from_uid": link.node_in.node_uid,
                             "to_uid": link.node_out.node_uid,
                             "nominal_Bps": link.bandwidth,
                             "latency_s": link.latency})
    if not selected:
        raise ValueError("No nominal slow compute-to-compute links were identified")
    if context["topology"] != "multi":
        raise ValueError("Unexpected frozen scenario")
    result = {
        "protocol_sha256": protocol_hash(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "physical_sha256": digest(context["physical"]),
        "solution_sha256": digest(DEPLOY / "solution.ini"),
        "sim_cluster_sha256": digest(DEPLOY / "simulator_cluster.ini"),
        "placement_sha256": digest(DEPLOY / "placement.json"),
        "runner_sha256": digest(HERE / "run.py"),
        "sources_sha256": {path: digest(ROOT / path) for path in FROZEN_SOURCES},
        "path_spaces": {
            "canonical": {"edges": len(context["canonical_edges"]),
                          "paths": context["canonical_path_count"]},
            "partial": {"edges": len(context["partial_edges"]),
                        "paths": context["partial_path_count"],
                        "fixed_detours_gpu_ids": context["detours"]},
            "full": {"edges": len(context["full_dag"].edge_set),
                     "paths": context["full_path_count"]},
        },
        "scaled_links": selected,
        "network_profiles": {
            name: {"factor": factor,
                   "capacities_Bps": [item["nominal_Bps"] * factor for item in selected]}
            for name, factor in NETWORKS.items()},
    }
    write(HERE / "audit.json", result)
    return result


def check_frozen() -> dict:
    recorded = read(HERE / "audit.json")
    if recorded["protocol_sha256"] != protocol_hash():
        raise ValueError("protocol.json changed after the audit")
    if recorded["sources_sha256"] != {path: digest(ROOT / path)
                                      for path in FROZEN_SOURCES}:
        raise ValueError("A frozen scheduler, runtime, or topology audit source changed")
    if recorded["runner_sha256"] != digest(HERE / "run.py"):
        raise ValueError("Experiment runner changed after the audit")
    context = load_context()
    actual = {
        "physical_sha256": digest(context["physical"]),
        "solution_sha256": digest(DEPLOY / "solution.ini"),
        "sim_cluster_sha256": digest(DEPLOY / "simulator_cluster.ini"),
        "placement_sha256": digest(DEPLOY / "placement.json"),
    }
    if any(recorded[key] != value for key, value in actual.items()):
        raise ValueError("A frozen C1_multi input changed after the audit")
    return recorded


def builder(cell: str, context: dict):
    from experiments.v3_dynamic_pathspace.scheduler import (
        KVCanonical, KVFull, ExecutedLayerKVAdmission)
    from experiments.v3_cycle_pricing.scheduler import RouteRecorder
    from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler

    if cell == "canonical":
        return partial(KVCanonical, allowed_edges=context["canonical_edges"])
    if cell == "full":
        return KVFull
    if cell == "partial":
        class FixedPartial(ExecutedLayerKVAdmission, RouteRecorder,
                           CanonicalGraphDagScheduler):
            """M3 over a fixed partial edge set shared by both networks."""
        return partial(FixedPartial, allowed_edges=context["partial_edges"])
    raise ValueError(cell)


def execute(load_label: str, network: str, cell: str, seed: int,
            duration: int, phase: str) -> dict:
    frozen = check_frozen()
    context = load_context()
    factor = NETWORKS[network]
    output = (HERE / "runs" / phase / load_label / network /
              f"{cell}_seed{seed}.json")
    identity = {
        "experiment": "v3_fixed_topology_path_crossover_v2_isolated_windows",
        "phase": phase,
        "topology": "C1_multi",
        "load_label": load_label,
        "offered_tokens_per_s": LOADS[load_label],
        "network_profile": network,
        "crosslink_capacity_factor": factor,
        "path_space": cell,
        "seed": seed,
        "duration_s": duration,
        "warmup_s": 0,
        "evaluation_protocol": "fixed_window_no_tail_drain",
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "protocol_sha256": frozen["protocol_sha256"],
        "physical_sha256": frozen["physical_sha256"],
        "solution_sha256": frozen["solution_sha256"],
        "sim_cluster_sha256": frozen["sim_cluster_sha256"],
        "placement_sha256": frozen["placement_sha256"],
        "sources_sha256": frozen["sources_sha256"],
    }
    if output.exists():
        previous = read(output)
        if all(previous.get(key) == value for key, value in identity.items()):
            return {"status": "reused", "source": str(output.relative_to(ROOT)),
                    "trace_sha256": previous["trace_sha256"]}
        raise ValueError(f"Existing result identity differs; not overwriting {output}")
    failure_path = output.with_suffix(".failure.json")
    if failure_path.exists():
        raise ValueError(f"A prior failure is preserved; inspect {failure_path}")

    from benchmarks import fixed_window
    from experiments.v3_cycle_pricing.run import physical_input
    from experiments.v3_cluster42.kv_admission import install_completion_wakeup
    from experiments.v3_pathspace_ablation.run import canonical_edges
    from experiments.m2_multistage_candidate.placement import validate
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.base_node import NodeType
    from simulator.event_simulator.request import RequestPhase

    holder = {}
    decode_batches = defaultdict(lambda: [0, 0, 0])
    base = builder(cell, context)
    nominal_slow_uids = {item["link_uid"] for item in frozen["scaled_links"]}

    def factory(simulator):
        changed = []
        for link in simulator.links.values():
            if link.link_uid not in nominal_slow_uids:
                continue
            if not (link.node_in_type == NodeType.Compute and
                    link.node_out_type == NodeType.Compute):
                raise ValueError("Network profile selected a non-compute link")
            old = link.bandwidth
            link.bandwidth = old * factor
            link.available_bandwidth = link.bandwidth
            changed.append({"link_uid": link.link_uid,
                            "nominal_Bps": old,
                            "effective_Bps": link.bandwidth,
                            "latency_s": link.latency})
        if len(changed) != len(nominal_slow_uids):
            raise ValueError("Nominal slow-link set changed after audit")
        for node in simulator.compute_nodes.values():
            original = node.start_execution
            def record(requests, _original=original, _uid=node.node_uid):
                count = sum(req.phase == RequestPhase.Increment for req in requests)
                if count:
                    batch = decode_batches[_uid]
                    batch[0] += 1
                    batch[1] += count
                    batch[2] += count == 1
                return _original(requests)
            node.start_execution = record
        scheduler = base(simulator)
        holder["scheduler"] = scheduler
        holder["scaled_links"] = changed
        install_completion_wakeup(simulator, scheduler)
        return scheduler

    output.parent.mkdir(parents=True, exist_ok=True)
    physical, topology = physical_input("C1_multi")
    machine_counts = TopologyModel(physical).machine_counts
    log_path = output.with_suffix(".log")
    try:
        with log_path.open("w", encoding="utf-8") as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            row = fixed_window.run(
                topology, "queue_dag", LOADS[load_label], duration, 0, seed,
                DEPLOY / "solution.ini", DEPLOY / "simulator_cluster.ini",
                profile_resources=False, compact=True, record_query_samples=True,
                physical_cluster=physical, machine_counts=machine_counts,
                scheduler_factory=factory)
            scheduler = holder["scheduler"]
            capacities = {str(uid): node.kv_cache.max_capacity
                          for uid, node in scheduler.simulator.compute_nodes.items()
                          if node.kv_cache is not None}
            peaks = {str(uid): amount for uid, amount in scheduler.peak_reserved.items()}
            executions = sum(item[0] for item in decode_batches.values())
            generated = sum(item[1] for item in decode_batches.values())
            row.update({
                **identity,
                "scaled_links": holder["scaled_links"],
                "path_records": {str(uid): {"hops": hops, "partial_hops": partial_hops}
                                 for uid, (hops, partial_hops) in
                                 getattr(scheduler, "route_records", {}).items()},
                "kv_admission": scheduler.kv_admission,
                "kv_capacity": capacities,
                "kv_peak_reserved": peaks,
                "kv_peak_fraction": max((amount / capacities[uid]
                                          for uid, amount in peaks.items()), default=0.0),
                "decode_batches": {
                    "executions": executions,
                    "decode_tokens": generated,
                    "mean_batch": generated / executions if executions else None,
                    "single_share": (sum(item[2] for item in decode_batches.values()) /
                                     executions if executions else None),
                },
            })
            if len(row.get("query_samples", {})) != row.get("arrivals"):
                raise ValueError("Incomplete per-query samples")
            write(output, row)
    except Exception as error:
        with log_path.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        write(failure_path, {**identity, "error": repr(error),
                             "traceback": traceback.format_exc(),
                             "log": str(log_path.relative_to(ROOT))})
        raise
    return {"status": "passed", "source": str(output.relative_to(ROOT)),
            "trace_sha256": row["trace_sha256"], "log": str(log_path.relative_to(ROOT))}


def jobs(phase: str):
    if phase == "dev":
        seed, duration = 102, 300
        return [(load, network, cell, seed, duration, phase)
                for load in LOADS for network in NETWORKS for cell in CELLS]
    if phase in {"formal", "formal_isolated"}:
        duration = 1800
        output_phase = "formal_isolated" if phase == "formal_isolated" else phase
        return [(load, network, cell, seed, duration, output_phase)
                for seed in FORMAL_SEEDS for load in LOADS
                for network in NETWORKS for cell in CELLS]
    if phase == "smoke":
        duration = 60
        return [("low", "nominal", cell, 100, duration, phase)
                for cell in CELLS]
    raise ValueError(phase)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("audit", "smoke", "dev", "formal", "formal_isolated"),
                        required=True)
    parser.add_argument("--limit", type=int, default=0,
                        help="Run only the first N jobs (development/debug only).")
    parser.add_argument("--one", nargs=6,
                        metavar=("LOAD", "NETWORK", "CELL", "SEED", "DURATION", "PHASE"),
                        help="Run one window in an isolated Python interpreter.")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Set PYTHONHASHSEED=0 before starting Python")
    if args.one:
        load, network, cell, seed, duration, phase = args.one
        if load not in LOADS or network not in NETWORKS or cell not in CELLS:
            raise SystemExit("Unknown load, network, or path-space cell")
        if phase not in {"smoke", "dev", "formal_isolated"}:
            raise SystemExit("Unknown single-window phase")
        print(json.dumps(execute(load, network, cell, int(seed),
                                 int(duration), phase), ensure_ascii=False), flush=True)
        return
    if args.phase == "audit":
        print(json.dumps(audit(), indent=2, ensure_ascii=False))
        return
    check_frozen()
    selected = jobs(args.phase)
    if args.limit:
        if args.phase in {"formal", "formal_isolated"}:
            raise SystemExit("Do not truncate the official formal matrix")
        selected = selected[:args.limit]
    index_path = HERE / f"{args.phase}_index.json"
    index = {"phase": args.phase, "jobs": {}, "failures": {}}
    for job in selected:
        load, network, cell, seed, _, _ = job
        key = f"{load}/{network}/{cell}/seed{seed}"
        try:
            index["jobs"][key] = execute(*job)
            print("PASS", key, index["jobs"][key]["source"], flush=True)
        except Exception as error:
            index["jobs"][key] = {"status": "failed", "error": repr(error)}
            index["failures"][key] = repr(error)
            print("FAIL", key, repr(error), flush=True)
            write(index_path, index)
            if args.phase == "formal":
                break
        write(index_path, index)
    print(json.dumps(index["failures"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

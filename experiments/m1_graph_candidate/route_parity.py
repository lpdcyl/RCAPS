"""Record fixed-trace M3 equivalence before considering historical reuse."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run

from .test_graph import GraphRecorder, OldRecorder


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(name: str, offered: float, *, seed: int = 100,
           duration: int = 60, natural_trace: bool = False) -> dict:
    directory = HERE / "layouts" / name
    trace = None if natural_trace else [(0.2 * index, 1000, 8) for index in range(12)]
    rows = []
    schedulers = []
    for scheduler_type in (OldRecorder, GraphRecorder):
        def factory(simulator, kind=scheduler_type):
            scheduler = kind(simulator)
            schedulers.append(scheduler)
            return scheduler
        rows.append(fixed_window_run(
            name, "queue_dag", offered, duration, 0, seed,
            directory / "solution.ini", directory / "simulator_cluster.ini",
            scheduler_factory=factory, compact=True,
            record_query_samples=True, trace_override=trace))
    routes_equal = schedulers[0].recorded_routes == schedulers[1].recorded_routes
    traces_equal = rows[0]["trace_sha256"] == rows[1]["trace_sha256"]
    metrics_equal = (all(rows[0][key] == rows[1][key] for key in FIELDS) and
                     rows[0]["query_samples"] == rows[1]["query_samples"] and
                     rows[0]["route_counts"] == rows[1]["route_counts"])
    runtime_dag = schedulers[1].execution_dag
    simulator = schedulers[1].simulator
    exported_runtime_edges = set()
    for link in simulator.links.values():
        left = ("source" if link.node_in.node_uid ==
                simulator.source_node.node_uid else link.node_in.node_uid)
        right = ("sink" if link.node_out.node_uid ==
                 simulator.sink_node.node_uid else link.node_out.node_uid)
        exported_runtime_edges.add((left, right))
    runtime_edges_equal = runtime_dag.edge_set == exported_runtime_edges
    deployment_dag = json.loads((HERE / "layout_audit.json").read_text())[name]
    edge_count_equal = len(runtime_dag.edges) == deployment_dag["compatibility_edges"]
    path_count_equal = runtime_dag.path_count() == deployment_dag["compatible_paths"]
    return {"scenario": name, "trace_kind": "offered_load" if natural_trace else "fixed_12",
            "trace": trace, "trace_sha256": rows[0]["trace_sha256"],
            "seed": seed, "duration_s": duration, "offered_tokens_per_s": offered,
            "arrivals": rows[0]["arrivals"],
            "route_assignments": len(schedulers[0].recorded_routes),
            "route_sequence_sha256": hashlib.sha256(json.dumps(
                schedulers[0].recorded_routes).encode()).hexdigest(),
            "routes_equal": routes_equal, "metrics_equal": metrics_equal,
            "traces_equal": traces_equal,
            "runtime_edges_equal": runtime_edges_equal,
            "runtime_edge_count_equal": edge_count_equal,
            "runtime_path_count_equal": path_count_equal,
            "passed": all((routes_equal, metrics_equal, traces_equal, runtime_edges_equal,
                           edge_count_equal,
                           path_count_equal)),
            "solution_sha256": digest(directory / "solution.ini"),
            "sim_cluster_sha256": digest(directory / "simulator_cluster.ini")}


def main() -> None:
    result = {name: verify(name, load) for name, load in
              (("single", 700.0), ("multi", 320.0))}
    result["source_sha256"] = {
        "resource_graph": digest(ROOT / "rcaps/placement/resource_graph.py"),
        "scheduler_adapter": digest(HERE / "scheduler.py"),
        "routing_implementation": digest(ROOT / "rcaps/scheduling/scheduler_queue_cost.py"),
        "scheduler_final": digest(ROOT / "rcaps/scheduling/scheduler_final.py")}
    output = HERE / "route_parity.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not all(result[name]["passed"] for name in ("single", "multi")):
        raise ValueError(f"Online route parity failed; inspect {output}")
    print(output)


if __name__ == "__main__":
    main()

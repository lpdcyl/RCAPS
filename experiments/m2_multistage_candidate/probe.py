"""Fixed-trace runtime regression for a merge and a second split."""

from __future__ import annotations

import json

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m1_graph_candidate.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.placement.topology import TopologyModel
from simulator.event_simulator.request import RequestPhase

from .placement import HERE, save, validate
from .prepare import files
from .search import _shape_requirements, assignments, build


class AuditedScheduler(GraphModeledQueueAwareDagScheduler):
    decode_checks = 0

    def schedule_transmission(self, node):
        for request in node.outbound_request_dict.values():
            if request.phase != RequestPhase.Increment:
                continue
            expected = self.session_paths.get(request.base_query_uid)
            actual = [stage.node_uid for stage in request.mini_pipeline[:-1]]
            if expected is None or expected != actual:
                raise ValueError("Decode route differs from its fixed prompt/KV route")
            type(self).decode_checks += 1
        return super().schedule_transmission(node)


def run_probe() -> dict:
    physical, template, topology = files("C1_single")
    model = TopologyModel(physical)
    results = {}
    for label, boundaries, widths in (
            ("split_merge", (48, 64), (1, 2, 1)),
            ("second_split", (48, 72), (1, 2, 4))):
        grouped = assignments(model, _shape_requirements(model.layers, boundaries,
                                                          widths), a100_prefix=False)
        state = next((candidate for bins in grouped
                      if (candidate := build(model, boundaries, widths, bins)) is not None),
                     None)
        if state is None:
            raise ValueError(f"No legal fixed-trace probe: {label}")
        directory = HERE / "probes" / label
        placement = save(model, template, state, directory,
                         {"probe": label, "status": "fixed_trace"})
        expected_edges = validate(model, state)["dag"].edge_set
        AuditedScheduler.decode_checks = 0
        row = fixed_window_run(
            topology, "queue_dag", 160.0, 120, 0, 100,
            directory / "solution.ini", directory / "simulator_cluster.ini",
            scheduler_factory=AuditedScheduler, compact=True,
            record_query_samples=True, physical_cluster=physical,
            machine_counts=model.machine_counts,
            trace_override=[(0.0, 128, 8), (1.0, 256, 8),
                            (2.0, 128, 8), (3.0, 256, 8)])
        if not any(sample["completed"] for sample in row["query_samples"].values()):
            raise ValueError(f"Fixed-trace probe did not finish a query: {label}")
        if AuditedScheduler.decode_checks == 0:
            raise ValueError(f"Fixed-trace probe did not exercise Decode: {label}")
        for encoded in row["route_counts"]:
            nodes = [int(token) - 2 for token in encoded.split("-")]
            if any(edge not in expected_edges for edge in
                   zip(("source", *nodes), (*nodes, "sink"))):
                raise ValueError(f"Runtime route not present in M1 DAG: {encoded}")
        results[label] = {"widths": widths, "boundaries": boundaries,
                          "placement_sha256": placement["solution_sha256"],
                          "sim_cluster_sha256": placement["sim_cluster_sha256"],
                          "compatible_paths": placement["compatible_paths"],
                          "actual_distinct_paths": len(row["route_counts"]),
                          "completed_queries": sum(sample["completed"] for sample in
                                                   row["query_samples"].values()),
                          "decode_path_checks": AuditedScheduler.decode_checks,
                          "trace_sha256": row["trace_sha256"]}
    output = HERE / "fixed_trace_probe.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    print(run_probe())

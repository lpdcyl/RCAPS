"""Graph, deployment and online-route parity for the isolated candidate."""

from __future__ import annotations

import ast
import json
import math
import unittest
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import patch

from benchmarks.fixed_window import run as fixed_window_run
from rcaps.placement import adaptive, static_resource
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.resource_graph import from_topology, layer_dag
from rcaps.placement.topology import TopologyModel
from rcaps.scheduling.scheduler_final import QueueAwareDagScheduler

from .scheduler import GraphModeledQueueAwareDagScheduler


HERE = Path(__file__).resolve().parent


class RouteRecorder:
    def __init__(self, simulator):
        super().__init__(simulator)
        self.recorded_routes = []

    def _route(self, request):
        result = super()._route(request)
        self.recorded_routes.append((request.base_query_uid,
                                     tuple((stage.link_uid, stage.node_uid,
                                            tuple(stage.layers_to_infer or ()))
                                           for stage in result)))
        return result


class OldRecorder(RouteRecorder, QueueAwareDagScheduler):
    pass


class GraphRecorder(RouteRecorder, GraphModeledQueueAwareDagScheduler):
    pass


class GraphCandidateTest(unittest.TestCase):
    def test_graph_matches_exported_edges_and_static_score(self):
        for name in ("single", "multi"):
            with self.subTest(scenario=name):
                physical, _ = scenario_files(name)
                model = TopologyModel(physical)
                record = json.loads((HERE / "layouts" / name / "placement.json")
                                    .read_text(encoding="utf-8"))
                state = {"stem": record["stem"],
                         "prefix_layers": record["prefix_layers"],
                         "branches": record["branches"],
                         "lengths": {int(node): end - start for node, (start, end)
                                     in record["intervals"].items()}}
                resources = from_topology(model)
                dag = layer_dag(resources, adaptive.intervals(model, state),
                                (state["stem"][0],))
                for left, right in dag.edges:
                    if left in dag.spans and right in dag.spans:
                        self.assertLess(dag.spans[left][1], dag.spans[right][1])
                cluster = ConfigParser()
                cluster.read(HERE / "layouts" / name / "simulator_cluster.ini")
                exported = set()
                for section in ast.literal_eval(cluster["Links"]["names"]):
                    edge = cluster[section]
                    def physical_id(value):
                        return (value if value in ("source", "sink") else
                                int(value.removeprefix("compute_node_")) - 2)
                    exported.add((physical_id(edge["in"]),
                                  physical_id(edge["out"])))
                self.assertEqual(dag.edge_set, exported)
                self.assertGreaterEqual(dag.path_count(), len(state["branches"]))
                with patch.object(adaptive, "interleaved_workload_graph",
                                  side_effect=AssertionError("event DAG used")):
                    scored = static_resource.measure(model, state)
                for key in ("ttft_s", "tpot_s", "bottleneck_s"):
                    self.assertTrue(math.isclose(scored[key],
                                                 record["metrics"][key],
                                                 rel_tol=1e-12, abs_tol=1e-10))

    def test_fixed_trace_uses_the_same_online_routes(self):
        trace = [(0.2 * index, 1000, 8) for index in range(12)]
        for name, offered in (("single", 700.0), ("multi", 320.0)):
            with self.subTest(scenario=name):
                directory = HERE / "layouts" / name
                rows = []
                schedulers = []
                for scheduler_type in (OldRecorder, GraphRecorder):
                    def factory(simulator, kind=scheduler_type):
                        scheduler = kind(simulator)
                        schedulers.append(scheduler)
                        return scheduler
                    rows.append(fixed_window_run(
                        name, "queue_dag", offered, 60, 0, 100,
                        directory / "solution.ini",
                        directory / "simulator_cluster.ini",
                        scheduler_factory=factory, compact=True,
                        record_query_samples=True, trace_override=trace))
                self.assertEqual(schedulers[0].recorded_routes,
                                 schedulers[1].recorded_routes)
                self.assertGreater(len(schedulers[0].recorded_routes), 0)
                self.assertEqual(rows[0]["route_counts"], rows[1]["route_counts"])
                for field in ("output_throughput_tokens_per_s", "ttft_p95_s",
                              "tpot_p95_s", "completion_fraction",
                              "backlog_at_window_end"):
                    self.assertEqual(rows[0][field], rows[1][field])
                self.assertEqual(rows[0]["query_samples"], rows[1]["query_samples"])
                self.assertEqual(schedulers[1].execution_dag.path_count(),
                                 json.loads((HERE / "layout_audit.json")
                                            .read_text(encoding="utf-8"))[name]
                                 ["compatible_paths"])


if __name__ == "__main__":
    unittest.main()

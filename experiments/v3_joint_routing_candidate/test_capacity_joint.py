"""Capacity sharing and route-label invariants on the released C1 placement."""

from __future__ import annotations

import unittest

from rcaps.v3.placement import validate

from .capacity import Stage, _gpu_work, expanded_graph, solve, workload_classes
from .capacity_route import Label, pareto_insert, resource_weights
from .joint import ROOT, case_inputs, read
from .joint_capacity import train_trace


class CapacityJointInvariants(unittest.TestCase):
    def test_shared_gpu_is_a_single_physical_capacity(self):
        model, _, template = case_inputs("C1_single")
        state = read(ROOT / "rcaps/v3_layouts/single/placement.json")["state"]
        checked = validate(model, state)
        stages, arcs = expanded_graph(model, state)
        self.assertGreater(len(stages), len(checked["spans"]))
        self.assertTrue(any(stage.first != checked["spans"][stage.gpu][0]
                            for stage in stages))
        self.assertTrue(any(arc.link[0] == "source" for arc in arcs))
        self.assertTrue(any(arc.link[1] == "sink" for arc in arcs))
        classes = workload_classes(train_trace("C1_single", "uniform"))
        lp = solve(model, template, state, classes)
        self.assertTrue(lp["success"])
        self.assertGreater(lp["requests_per_s"], 0)
        self.assertLessEqual(max(row["utilization"] for row in
                                 lp["resource_utilization"]), 1 + 1e-8)
        first_gpu = state["segments"][0]["replicas"][0][0]
        first_span = checked["spans"][first_gpu]
        work_per_request = sum(row.probability * _gpu_work(
            model, Stage(first_gpu, *first_span), row) for row in classes)
        utilization = {row["resource"]: row["utilization"] for row in
                       lp["resource_utilization"]}
        self.assertAlmostEqual(utilization[f"gpu:{first_gpu}"],
                               work_per_request * lp["requests_per_s"], places=6)
        self.assertTrue(resource_weights(lp))

    def test_pareto_pool_preserves_earliest_and_least_pressure(self):
        rows = []
        for index, (finish, pressure) in enumerate(
                [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)]):
            rows = pareto_insert(rows, Label(finish, pressure, (index,)), width=4)
        self.assertEqual(len(rows), 4)
        self.assertEqual(min(row.live_cost for row in rows), 1)
        self.assertEqual(min(row.pressure for row in rows), 1)
        self.assertEqual(rows, pareto_insert(rows, Label(6, 6, (6,)), width=4))


if __name__ == "__main__":
    unittest.main()

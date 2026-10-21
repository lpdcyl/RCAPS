"""Capacity and feasibility checks for the independent linear proxy."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.v3_joint_routing_candidate.capacity import (
    WorkloadClass, solve,
)
from experiments.v3_joint_routing_candidate.joint import case_inputs

from .model import evaluate


class LinearProxyTest(unittest.TestCase):
    def setUp(self):
        self.model, _, self.template = case_inputs("C1_multi")
        path = Path(__file__).resolve().parents[2] / "rcaps/v3_layouts/multi/placement.json"
        self.state = json.loads(path.read_text(encoding="utf-8"))["state"]

    def test_shared_physical_capacity_limits_fixed_rate(self):
        classes = (WorkloadClass("one", 750, 250, 1.0),)
        capacity = solve(self.model, self.template, self.state, classes)
        self.assertTrue(capacity["success"])
        rate = capacity["requests_per_s"]
        feasible = evaluate(self.model, self.template, self.state, classes, rate * 0.5)
        self.assertTrue(feasible["success"])
        self.assertGreater(feasible["minimum_service_seconds_per_request"], 0)
        self.assertLessEqual(feasible["max_resource_utilization"], 1 + 1e-7)
        infeasible = evaluate(self.model, self.template, self.state, classes, rate * 1.1)
        self.assertFalse(infeasible["success"])

    def test_invalid_workload_probability_rejected(self):
        with self.assertRaisesRegex(ValueError, "sum to one"):
            evaluate(self.model, self.template, self.state,
                     (WorkloadClass("bad", 750, 250, 0.9),), 0.2)


if __name__ == "__main__":
    unittest.main()

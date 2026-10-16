"""Regression checks for the isolated static M1 candidate."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.v2_method_comparisons.placement import static_measure as legacy_measure
from rcaps.placement import adaptive, static_resource
from rcaps.placement.partition import scenario as scenario_files
from rcaps.placement.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]


class StaticResourceTest(unittest.TestCase):
    def test_normalized_score_matches_legacy_static_candidates(self):
        for scenario in ("single", "multi"):
            with self.subTest(scenario=scenario):
                physical, _ = scenario_files(scenario)
                model = TopologyModel(physical)
                states = [adaptive.reference_state(model, scenario), *
                          adaptive.initial_states(model, fixed_structure=False)]
                old_reference = legacy_measure(model, states[0])
                new_reference = static_resource.measure(model, states[0])
                for state in states:
                    old = legacy_measure(model, state)
                    new = static_resource.measure(model, state)
                    for field in ("ttft_s", "tpot_s"):
                        self.assertTrue(math.isclose(old[field], new[field],
                                                      rel_tol=1e-12, abs_tol=1e-10))
                    self.assertTrue(math.isclose(old["bottleneck_s"],
                                                  6 * new["bottleneck_s"],
                                                  rel_tol=1e-12, abs_tol=1e-10))
                    self.assertEqual(old["bottleneck_resource"],
                                     new["bottleneck_resource"])
                    self.assertTrue(math.isclose(
                        adaptive.objective(old, old_reference),
                        adaptive.objective(new, new_reference),
                        rel_tol=1e-12, abs_tol=1e-10))

    def test_static_search_never_builds_request_event_graph(self):
        physical, _ = scenario_files("single")
        model = TopologyModel(physical)
        with patch.object(adaptive, "interleaved_workload_graph",
                          side_effect=AssertionError("event graph used")):
            state, metadata = adaptive.optimize(
                model, "single", fixed_structure=False,
                evaluator=static_resource.measure)
        self.assertEqual(len(state["branches"]), 2)
        self.assertGreater(metadata["candidate_evaluations"], 0)

    def test_default_search_preserves_frozen_v2_layout(self):
        for scenario in ("single", "multi"):
            with self.subTest(scenario=scenario):
                physical, _ = scenario_files(scenario)
                model = TopologyModel(physical)
                state, _ = adaptive.optimize(model, scenario, fixed_structure=False)
                frozen = json.loads((ROOT / "rcaps/v2_layouts" /
                                     f"{scenario}_adaptive/placement.json").read_text())
                self.assertEqual(state["stem"], frozen["stem"])
                self.assertEqual(state["prefix_layers"], frozen["prefix_layers"])
                self.assertEqual(state["branches"], frozen["branches"])
                self.assertEqual({str(node): list(pair) for node, pair in
                                  adaptive.intervals(model, state).items()},
                                 frozen["intervals"])


if __name__ == "__main__":
    unittest.main()

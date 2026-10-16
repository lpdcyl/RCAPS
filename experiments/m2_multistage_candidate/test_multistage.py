"""Regression checks for the bounded multi-stage placement candidate."""

from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from rcaps.placement import adaptive, static_resource
from rcaps.placement.partition import scenario
from rcaps.placement.resource_graph import from_topology
from rcaps.placement.topology import TopologyModel

from .placement import from_legacy, measure, validate
from .prepare import legacy_state
from .search import _shape_requirements, assignments, build


class MultiStageTest(unittest.TestCase):
    def test_single_boundary_static_score_is_unchanged(self):
        for name in ("single", "multi"):
            with self.subTest(topology=name):
                model = TopologyModel(scenario(name)[0])
                legacy = adaptive.reference_state(model, name)
                expected = static_resource.measure(model, legacy)
                actual = measure(model, from_legacy(legacy, model))
                for field in ("ttft_s", "tpot_s", "bottleneck_s"):
                    self.assertTrue(math.isclose(actual[field], expected[field],
                                                 rel_tol=1e-12, abs_tol=1e-10))

    def test_existing_static_candidate_is_score_equivalent(self):
        for case, topology in (("C1_single", "single"), ("C1_multi", "multi")):
            model = TopologyModel(scenario(topology)[0])
            state = legacy_state(case, model)
            boundary = state["segments"][0]["end"]
            old = {"stem": state["segments"][0]["replicas"][0],
                   "prefix_layers": boundary,
                   "branches": state["segments"][1]["replicas"],
                   "lengths": state["lengths"]}
            expected, actual = static_resource.measure(model, old), measure(model, state)
            for field in ("ttft_s", "tpot_s", "bottleneck_s"):
                self.assertTrue(math.isclose(actual[field], expected[field],
                                             rel_tol=1e-12, abs_tol=1e-10),
                                (case, field))

    def test_split_merge_and_second_split_have_complete_paths(self):
        model = TopologyModel(scenario("single")[0])
        for boundaries, widths in (((48, 64), (1, 2, 1)),
                                   ((48, 72), (1, 2, 4))):
            with self.subTest(widths=widths):
                grouped = assignments(model, _shape_requirements(
                    model.layers, boundaries, widths), a100_prefix=False)
                self.assertTrue(grouped)
                state = build(model, boundaries, widths, grouped[0])
                self.assertIsNotNone(state)
                checked = validate(model, state)
                self.assertGreaterEqual(checked["dag"].path_count(), widths[-1])
                self.assertLessEqual(checked["layer_copies"],
                                     sum(model.capacity.values()))
                self.assertGreaterEqual(checked["idle_gpus"], 0)

    def test_unreachable_replica_and_layer_capacity_are_rejected(self):
        model = TopologyModel(scenario("single")[0])
        boundaries, widths = (48, 64), (1, 2, 1)
        grouped = assignments(model, _shape_requirements(
            model.layers, boundaries, widths), a100_prefix=False)
        state = build(model, boundaries, widths, grouped[0])
        self.assertIsNotNone(state)
        prefix_exit = state["segments"][0]["replicas"][0][-1]
        middle_entry = state["segments"][1]["replicas"][0][0]
        removed = f"Link-{min(prefix_exit, middle_entry)}-{max(prefix_exit, middle_entry)}"
        altered = TopologyModel(scenario("single")[0])
        self.assertTrue(altered.config.remove_section(removed))
        from_topology.cache_clear()
        with self.assertRaisesRegex(ValueError, "reached|link"):
            validate(altered, state)
        from_topology.cache_clear()
        overloaded = {"segments": state["segments"],
                      "lengths": dict(state["lengths"])}
        overloaded["lengths"][prefix_exit] = model.capacity[prefix_exit] + 1
        with self.assertRaisesRegex(ValueError, "capacity"):
            validate(model, overloaded)

    def test_zero_kv_capacity_is_rejected(self):
        model = TopologyModel(scenario("single")[0])
        legacy = adaptive.reference_state(model, "single")
        state = from_legacy(legacy, model)
        with patch.object(model.manager, "get_kv_cache_capacity", return_value=0):
            with self.assertRaisesRegex(ValueError, "KV capacity"):
                validate(model, state)


if __name__ == "__main__":
    unittest.main()

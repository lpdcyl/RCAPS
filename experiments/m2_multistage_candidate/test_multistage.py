"""Regression checks for V3 multistage placement and resource legality."""

from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from rcaps.v3.resource_graph import from_topology
from rcaps.v3.topology import TopologyModel

from .placement import measure, validate
from .prepare import files, initial_state
from .search import _shape_requirements, assignments, build


class MultiStageTest(unittest.TestCase):
    def test_frozen_single_boundary_reference(self):
        for case in ("C1_single", "C1_multi"):
            with self.subTest(case=case):
                model = TopologyModel(files(case)[0])
                actual = measure(model, initial_state(case, model))
                self.assertTrue(all(math.isfinite(actual[field]) and actual[field] > 0
                                    for field in ("ttft_s", "tpot_s", "bottleneck_s")))

    def test_split_merge_and_second_split_have_complete_paths(self):
        model = TopologyModel(files("C1_single")[0])
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
                self.assertLessEqual(checked["layer_copies"], sum(model.capacity.values()))

    def test_unreachable_replica_and_layer_capacity_are_rejected(self):
        physical = files("C1_single")[0]
        model = TopologyModel(physical)
        boundaries, widths = (48, 64), (1, 2, 1)
        grouped = assignments(model, _shape_requirements(
            model.layers, boundaries, widths), a100_prefix=False)
        state = build(model, boundaries, widths, grouped[0])
        self.assertIsNotNone(state)
        prefix_exit = state["segments"][0]["replicas"][0][-1]
        middle_entry = state["segments"][1]["replicas"][0][0]
        removed = f"Link-{min(prefix_exit, middle_entry)}-{max(prefix_exit, middle_entry)}"
        altered = TopologyModel(physical)
        self.assertTrue(altered.config.remove_section(removed))
        from_topology.cache_clear()
        with self.assertRaisesRegex(ValueError, "reached|link"):
            validate(altered, state)
        from_topology.cache_clear()
        overloaded = {"segments": state["segments"], "lengths": dict(state["lengths"])}
        overloaded["lengths"][prefix_exit] = model.capacity[prefix_exit] + 1
        with self.assertRaisesRegex(ValueError, "capacity"):
            validate(model, overloaded)

    def test_zero_kv_capacity_is_rejected(self):
        model = TopologyModel(files("C1_single")[0])
        state = initial_state("C1_single", model)
        with patch.object(model.manager, "get_kv_cache_capacity", return_value=0):
            with self.assertRaisesRegex(ValueError, "KV capacity"):
                validate(model, state)


if __name__ == "__main__":
    unittest.main()

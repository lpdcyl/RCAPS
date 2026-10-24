"""Regression checks using in-memory test fixtures, never formal outputs."""

from __future__ import annotations

import copy
import unittest

from experiments.v3_path_crossover import report, run, validate


class RawResultChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Read an existing authentic result; test mutations stay in memory.
        cls.frozen = run.check_frozen()
        cls.authentic = run.read(run.HERE / "runs/formal_isolated/low/nominal/canonical_seed0.json")

    def issues(self, result):
        return validate.validate_result(result, self.frozen, "low", "nominal", "canonical", 0)

    def test_authentic_result_and_raw_trace(self):
        self.assertEqual(self.issues(self.authentic), [])

    def test_wrong_formal_seed_is_rejected(self):
        row = copy.deepcopy(self.authentic)
        row["seed"] = 102
        self.assertIn("identity mismatch: seed", self.issues(row))

    def test_missing_request_is_rejected(self):
        row = copy.deepcopy(self.authentic)
        row["query_samples"].pop(next(iter(row["query_samples"])))
        self.assertIn("request sample count differs from arrivals", self.issues(row))

    def test_changed_request_lengths_break_hash(self):
        row = copy.deepcopy(self.authentic)
        next(iter(row["query_samples"].values()))["input_tokens"] += 1
        self.assertIn("trace hash cannot be reconstructed from raw request samples", self.issues(row))

    def test_fabricated_latency_metric_is_rejected(self):
        row = copy.deepcopy(self.authentic)
        row["tpot_p95_s"] *= 0.9
        self.assertIn("P95 TPOT differs from request samples", self.issues(row))

    def test_kv_overcommit_is_rejected(self):
        row = copy.deepcopy(self.authentic)
        uid = next(iter(row["kv_capacity"]))
        row["kv_peak_reserved"][uid] = row["kv_capacity"][uid] + 1
        self.assertTrue(any("KV reservation exceeds capacity" in issue for issue in self.issues(row)))

    def test_unregistered_network_change_is_rejected(self):
        row = copy.deepcopy(self.authentic)
        row["scaled_links"][0]["latency_s"] += 0.001
        self.assertTrue(any("network intervention mismatch" in issue for issue in self.issues(row)))


def summary_fixture():
    # Deliberately synthetic analysis-unit-test data, never persisted as runs.
    return {(load, network, cell, seed): {
        "output_throughput_tokens_per_s": 100.0,
        "ttft_p95_s": 1.0, "tpot_p95_s": {"canonical": 1.0, "partial": 2.0, "full": 3.0}[cell],
        "completion_fraction": 0.9, "backlog_at_window_end": 1,
        "route_counts": {}, "path_records": {}, "decode_batches": {"mean_batch": 2, "single_share": 0.2},
        "kv_peak_fraction": 0.5, "arrivals": 10, "queries_with_tpot_samples": 9,
        "kv_admission": {"deferred_checks": 0},
    } for load in run.LOADS for network in run.NETWORKS
      for cell in run.CELLS for seed in run.FORMAL_SEEDS}


class PreregisteredWinnerChecks(unittest.TestCase):
    def test_global_latency_winner_failing_guardrail_means_no_winner(self):
        rows = summary_fixture()
        for (load, network, cell, seed), row in rows.items():
            if cell == "canonical":
                row["output_throughput_tokens_per_s"] = 90
        result = report.summarize(rows)
        self.assertTrue(all(v is None for v in result["winner_map"].values()))
        self.assertFalse(result["crossover_confirmed"])

    def test_one_percent_gap_is_required(self):
        rows = summary_fixture()
        for (_load, _network, cell, _seed), row in rows.items():
            if cell == "partial":
                row["tpot_p95_s"] = 1.005
        self.assertTrue(all(v is None for v in report.summarize(rows)["winner_map"].values()))

    def test_fixed_winner_does_not_imply_crossover(self):
        result = report.summarize(summary_fixture())
        self.assertTrue(all(v == "canonical" for v in result["winner_map"].values()))
        self.assertFalse(result["crossover_confirmed"])

    def test_paired_crossover_requires_two_same_seed_directions(self):
        rows = summary_fixture()
        for (_load, network, cell, _seed), row in rows.items():
            if network == "crosslink_4x":
                row["tpot_p95_s"] = {"canonical": 2.0, "partial": 1.0, "full": 3.0}[cell]
        result = report.summarize(rows)
        self.assertTrue(result["crossover_confirmed"])
        self.assertTrue(all(c["paired_seed_directions"] == 3 for c in result["confirmed_comparisons"]))

    def test_one_paired_direction_does_not_confirm_mean_winner_changes(self):
        rows = summary_fixture()
        for (_load, network, cell, seed), row in rows.items():
            if network == "nominal" and cell == "partial":
                row["tpot_p95_s"] = (4.0, 0.5, 0.5)[seed]
            if network == "crosslink_4x":
                row["tpot_p95_s"] = {"canonical": 2.0, "partial": 1.0, "full": 3.0}[cell]
        result = report.summarize(rows)
        self.assertTrue(result["crossover_comparisons"])
        self.assertTrue(all(c["paired_seed_directions"] == 1 for c in result["crossover_comparisons"]))
        self.assertFalse(result["crossover_confirmed"])

    def test_two_paired_directions_confirm_crossover(self):
        rows = summary_fixture()
        for (_load, network, cell, seed), row in rows.items():
            if network == "nominal" and cell == "partial":
                row["tpot_p95_s"] = (2.0, 2.0, 0.5)[seed]
            if network == "crosslink_4x":
                row["tpot_p95_s"] = {"canonical": 2.0, "partial": 1.0, "full": 3.0}[cell]
        result = report.summarize(rows)
        self.assertTrue(result["crossover_confirmed"])
        self.assertTrue(all(c["paired_seed_directions"] == 2 for c in result["confirmed_comparisons"]))

    def test_nonadjacent_loads_are_compared_when_middle_has_no_winner(self):
        rows = summary_fixture()
        for (load, _network, cell, _seed), row in rows.items():
            if load == "middle":
                row["tpot_p95_s"] = 1.0
            if load == "high":
                row["tpot_p95_s"] = {"canonical": 2.0, "partial": 1.0, "full": 3.0}[cell]
        result = report.summarize(rows)
        self.assertTrue(result["crossover_confirmed"])
        self.assertTrue(all(c["from"].startswith("low/") and c["to"].startswith("high/")
                            for c in result["confirmed_comparisons"]))

    def test_completed_cohort_diagnostic_preserves_primary_decision(self):
        analysis = {"crossover_confirmed": True, "confirmed_comparisons": [{
            "axis": "network", "from": "high/nominal", "to": "high/crosslink_4x",
            "winner_from": "full", "winner_to": "partial", "paired_seed_directions": 3,
        }], "common_completed": {}}
        for seed in run.FORMAL_SEEDS:
            analysis["common_completed"][f"high/seed{seed}"] = {"cells": {
                "nominal/full": {"p95_tpot_s": 2 if seed < 2 else 0.9},
                "nominal/partial": {"p95_tpot_s": 1.0},
                "crosslink_4x/full": {"p95_tpot_s": 2.0},
                "crosslink_4x/partial": {"p95_tpot_s": 1.0},
            }}
        result = report.common_completed_sensitivity(analysis)
        self.assertTrue(analysis["crossover_confirmed"])
        self.assertFalse(result["any_primary_crossover_preserves_direction_rule"])
        self.assertEqual(result["comparisons"][0]["common_completed_paired_seed_directions"], 1)

    def test_completed_cohort_diagnostic_detects_robust_direction(self):
        analysis = {"confirmed_comparisons": [{
            "axis": "load", "from": "middle/nominal", "to": "high/nominal",
            "winner_from": "partial", "winner_to": "full", "paired_seed_directions": 3,
        }], "common_completed": {}}
        for seed in run.FORMAL_SEEDS:
            analysis["common_completed"][f"middle/seed{seed}"] = {"cells": {
                "nominal/partial": {"p95_tpot_s": 1.0}, "nominal/full": {"p95_tpot_s": 2.0}}}
            analysis["common_completed"][f"high/seed{seed}"] = {"cells": {
                "nominal/partial": {"p95_tpot_s": 2.0}, "nominal/full": {"p95_tpot_s": 1.0}}}
        result = report.common_completed_sensitivity(analysis)
        self.assertTrue(result["any_primary_crossover_preserves_direction_rule"])
        self.assertEqual(result["comparisons"][0]["common_completed_paired_seed_directions"], 3)


if __name__ == "__main__":
    unittest.main()

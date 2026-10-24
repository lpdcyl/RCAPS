"""Evidence gates: no favorable conclusion from censored or mispaired metrics."""

import copy
import unittest

from experiments.v3_adaptive_space_cohort.report import crossover, p95, recompute, unique_winner
from experiments.v3_adaptive_space_cohort.run import registered_job


class EvidenceTests(unittest.TestCase):
    def test_independent_event_reconstruction_keeps_long_requests(self):
        samples = {
            "1": {"arrival_s": 0, "decode_completion_times_s": [1, 2], "finish_s": 2},
            "2": {"arrival_s": 4, "decode_completion_times_s": [6, 8, 10], "finish_s": 10},
        }
        window, life = recompute(samples, cutoff=7), recompute(samples)
        self.assertEqual(window["completed"], 1)
        self.assertEqual(life["completed"], 2)
        self.assertEqual(window["output_tokens_completed"], 3)
        self.assertEqual(life["output_tokens_completed"], 5)
        self.assertAlmostEqual(window["tpot_p95_s"], 1)
        self.assertAlmostEqual(life["tpot_p95_s"], 1.95)

    def test_token_on_window_boundary_belongs_to_tail(self):
        samples = {"1": {"arrival_s": 1, "decode_completion_times_s": [2, 5], "finish_s": 5}}
        metrics = recompute(samples, cutoff=5)
        self.assertEqual(metrics["completed"], 0)
        self.assertEqual(metrics["output_tokens_completed"], 1)
        self.assertIsNone(metrics["tpot_p95_s"])

    def test_single_output_has_no_fabricated_tpot(self):
        metrics = recompute({"1": {"arrival_s": 0, "decode_completion_times_s": [2], "finish_s": 2}})
        self.assertIsNone(metrics["tpot_p95_s"])
        self.assertEqual(metrics["completed"], 1)

    def test_percentile_matches_linear_definition(self):
        self.assertAlmostEqual(p95([1, 10]), 9.55)

    def test_latency_winner_cannot_be_replaced_after_guardrail_filter(self):
        policies = {
            "full": {"lifecycle_tpot_mean_s": 1, "window_throughput_mean": 90, "window_completion_mean": 1},
            "partial": {"lifecycle_tpot_mean_s": 2, "window_throughput_mean": 100, "window_completion_mean": 1},
            "canonical": {"lifecycle_tpot_mean_s": 3, "window_throughput_mean": 100, "window_completion_mean": 1},
        }
        self.assertIsNone(unique_winner(policies))

    def test_small_gap_does_not_make_unique_winner(self):
        policies = {p: {"lifecycle_tpot_mean_s": t, "window_throughput_mean": 100,
                        "window_completion_mean": 1} for p, t in (("partial", 1), ("full", 1.005))}
        self.assertIsNone(unique_winner(policies))

    def condition(self, winner, first, second, prefix_first=None, prefix_second=None):
        policies = {}
        for policy, all_values, prefix in (("partial", first, prefix_first), ("full", second, prefix_second)):
            prefix = all_values if prefix is None else prefix
            policies[policy] = {"lifecycle_tpot_per_seed_s": all_values,
                                "prefix_tpot_per_seed_s": prefix,
                                "prefix_tpot_mean_s": sum(prefix) / len(prefix)}
        return {"winner": winner, "policies": policies}

    def test_three_primary_seeds_cannot_override_one_prefix_seed(self):
        a = self.condition("partial", [1, 1, 1], [2, 2, 2])
        b = self.condition("full", [2, 2, 2], [1, 1, 1], [1, 1, 2], [2, 2, 1])
        gate = crossover(a, b)
        self.assertEqual(gate["all_request_matching_seeds"], 3)
        self.assertEqual(gate["prefix_matching_seeds"], 1)
        self.assertFalse(gate["confirmed"])

    def test_same_policy_in_both_states_is_not_crossover(self):
        a = self.condition("partial", [1, 1, 1], [2, 2, 2])
        self.assertFalse(crossover(a, copy.deepcopy(a))["confirmed"])

    def test_two_matching_seeds_and_prefix_means_pass(self):
        a = self.condition("partial", [1, 1, 2], [2, 2, 1])
        b = self.condition("full", [2, 2, 1], [1, 1, 2])
        self.assertTrue(crossover(a, b)["confirmed"])

    def test_formal_seed_replacement_is_rejected(self):
        with self.assertRaises(ValueError):
            registered_job("formal", "high", "nominal", "full", 102)

    def test_unregistered_condition_is_rejected(self):
        with self.assertRaises(ValueError):
            registered_job("formal", "low", "nominal", "full", 0)


if __name__ == "__main__":
    unittest.main()

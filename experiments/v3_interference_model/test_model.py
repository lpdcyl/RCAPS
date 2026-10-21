"""Formula and traffic-accounting checks for the frozen T0.6 model."""

from __future__ import annotations

import unittest

from .model import (LinkMoments, effective_bandwidth, from_message_sizes,
                    from_trace_shares, path_weighted_wait, payload_bytes)


class InterferenceModelTests(unittest.TestCase):
    def test_zero_decode_load_leaves_prompt_residual(self):
        m = LinkMoments(2, 0, 1, 0, 1.5, 0)
        self.assertAlmostEqual(m.wait_decode_s, 2 * 1.5 / 2)

    def test_bandwidth_doubling_approaches_quarter_wait(self):
        m = from_message_sizes([20, 40], [1], 100, 10)
        doubled = from_message_sizes([20, 40], [1], 100, 20)
        self.assertAlmostEqual(doubled.wait_decode_s / m.wait_decode_s, 0.25,
                               delta=0.002)

    def test_prompt_rate_halves_prompt_term(self):
        m = LinkMoments(2, 1, 1, 0.1, 1.5, 0.01)
        half = LinkMoments(1, 1, 1, 0.1, 1.5, 0.01)
        prompt_term = m.lambda_prompt * m.second_prompt_s2 / (2 * (1-m.rho_decode))
        self.assertAlmostEqual(m.wait_decode_s - half.wait_decode_s,
                               prompt_term / 2)

    def test_saturation_and_min_bandwidth(self):
        m = LinkMoments(1, 10, 1, 0.1, 1, 0.01)
        self.assertEqual(m.wait_decode_s, float("inf"))
        self.assertEqual(effective_bandwidth(20, 15, 30), 15)

    def test_payload_and_equal_split_trace(self):
        edge = (1, 2)
        moments = from_trace_shares([(10, 2), (20, 4)], 2, {edge: 0.5},
                                    {edge: 12}, 2, 4)[edge]
        self.assertEqual(payload_bytes(2, 4, 10), 60)
        self.assertEqual(moments.lambda_prompt, 0.5)
        self.assertEqual(moments.lambda_decode, 1.5)
        self.assertAlmostEqual(moments.mean_prompt_s, 7.5)
        self.assertAlmostEqual(path_weighted_wait({edge: 0.5}, {edge: moments}),
                               0.5 * moments.wait_decode_s)


if __name__ == "__main__":
    unittest.main()

import unittest
import numpy as np

from real_data_stress_pipeline.run_pipeline import (
    g0, longest_run, month, month_label, returns, stationary_sample, wilson,
)

class StressPipelineContractTests(unittest.TestCase):
    def test_world_bank_month_encodings(self):
        self.assertEqual(month("1980M01"), 1980 * 12)
        self.assertEqual(month("1980-M1"), 1980 * 12)
        self.assertEqual(month("1980-01"), 1980 * 12)
        self.assertEqual(month("198001"), 1980 * 12)
        self.assertIsNone(month("1980"))
        self.assertIsNone(month("1980M13"))

    def test_month_label_round_trip(self):
        self.assertEqual(month_label(2024 * 12 + 11), "2024-12")

    def test_contiguous_selection_does_not_fill_gaps(self):
        xs, ys = longest_run({1: 10.0, 2: 11.0, 4: 13.0, 5: 14.0, 6: 15.0})
        self.assertEqual(xs, [4, 5, 6])
        self.assertEqual(ys, [13.0, 14.0, 15.0])

    def test_log_returns_only_use_adjacent_points(self):
        xs, ys = returns([1970*12+1, 1970*12+2, 1970*12+3], [10.0, 11.0, 12.1])
        self.assertEqual(xs, ["1970-03", "1970-04"])
        self.assertAlmostEqual(ys[0], np.log(1.1), places=12)
        self.assertAlmostEqual(ys[1], np.log(1.1), places=12)

    def test_g0_rejects_short_and_degenerate(self):
        self.assertFalse(g0(np.linspace(0.01, 0.05, 86), 87)["passed"])
        self.assertFalse(g0([0.0] * 100, 87)["passed"])

    def test_g0_accepts_non_degenerate_long_series(self):
        values = np.random.default_rng(12).normal(0, 0.01, 540)
        self.assertTrue(g0(values, 501)["passed"])

    def test_stationary_bootstrap_is_repeatable(self):
        values = np.arange(100, dtype=float)
        left = stationary_sample(values, np.random.default_rng(5), 12)
        right = stationary_sample(values, np.random.default_rng(5), 12)
        np.testing.assert_array_equal(left, right)
        self.assertEqual(left.size, values.size)

    def test_wilson_interval(self):
        low, high = wilson(5, 100)
        self.assertLess(low, 0.05)
        self.assertGreater(high, 0.05)
        self.assertIsNone(wilson(0, 0))

if __name__ == "__main__":
    unittest.main()

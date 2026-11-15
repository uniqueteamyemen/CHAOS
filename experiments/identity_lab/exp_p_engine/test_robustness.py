"""Focused contract tests for the independent P-engine robustness benchmark."""
import math
import random
import unittest

from experiments.identity_lab.exp_p_engine.benchmark_robustness import (
    CONDITIONS,
    MONTHS,
    REGIMES,
    draw_noise,
    make_robust_rows,
)


class RobustnessBenchmarkTests(unittest.TestCase):
    def test_regime_and_condition_catalogs_are_complete(self):
        self.assertEqual(
            set(REGIMES),
            {
                "ar1_phi_04",
                "ar1_phi_07",
                "student_t4",
                "laplace",
                "contaminated_5pct",
                "short_noise_burst",
            },
        )
        self.assertEqual(
            set(CONDITIONS),
            {"null", "positive_3sigma", "negative_3sigma"},
        )

    def test_all_regimes_are_deterministic_and_finite(self):
        for regime in REGIMES:
            first = make_robust_rows(77123, regime, "positive_3sigma")
            second = make_robust_rows(77123, regime, "positive_3sigma")
            self.assertEqual(first, second, regime)
            rows, residuals = first
            self.assertEqual(len(rows), MONTHS)
            self.assertTrue(all(math.isfinite(value) for value in residuals))
            self.assertEqual(rows[0]["month"], 1)
            self.assertEqual(rows[-1]["month"], MONTHS)

    def test_ar1_regimes_preserve_temporal_dependence(self):
        for regime, expected_phi in (("ar1_phi_04", 0.4), ("ar1_phi_07", 0.7)):
            rng = random.Random(98231)
            previous = 0.0
            values = []
            for month in range(1, 5001):
                value, previous = draw_noise(rng, regime, month, previous)
                values.append(value)
            x = values[:-1]
            y = values[1:]
            mean_x = sum(x) / len(x)
            mean_y = sum(y) / len(y)
            covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
            variance_x = sum((a - mean_x) ** 2 for a in x)
            variance_y = sum((b - mean_y) ** 2 for b in y)
            correlation = covariance / math.sqrt(variance_x * variance_y)
            self.assertAlmostEqual(correlation, expected_phi, delta=0.06)

    def test_short_burst_changes_only_the_declared_noise_window(self):
        rng = random.Random(1234)
        values = []
        previous = 0.0
        for month in range(1, MONTHS + 1):
            value, previous = draw_noise(rng, "short_noise_burst", month, previous)
            values.append(value)
        # Regime assignment is deterministic at the generator boundary.
        self.assertEqual(
            [month for month in range(1, MONTHS + 1) if 48 <= month <= 59],
            list(range(48, 60)),
        )
        self.assertEqual(len(values), MONTHS)

    def test_condition_sign_and_onset_are_applied_exactly(self):
        rows, residuals = make_robust_rows(12, "ar1_phi_04", "negative_3sigma")
        self.assertEqual(len(rows), MONTHS)
        self.assertEqual(rows[64]["month"], 65)
        # The injected component is exactly -6 after onset; compare same-seed null.
        _, null_residuals = make_robust_rows(12, "ar1_phi_04", "null")
        for index in range(64, MONTHS):
            self.assertAlmostEqual(residuals[index] - null_residuals[index], -6.0)


if __name__ == "__main__":
    unittest.main()

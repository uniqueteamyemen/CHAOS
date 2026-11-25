"""Focused tests for the independent AR(1)/heavy-tail CUSUM holdout."""
import unittest

from experiments.identity_lab.exp_p_engine_holdout.robust_holdout import (
    NULL_SCENARIOS,
    generate_residuals,
    select_training_candidates,
    residuals_to_stock_rows,
)


def fake_sweep():
    keys = ("k=0.50|h=8.5", "k=0.50|h=24.0")
    results = {}
    for scenario in (
        "stable_null", "rising_noise_null", "elevated_noise_null",
        "positive_step_3sigma", "negative_step_3sigma",
        "transition_positive_3sigma", "transition_negative_3sigma",
    ):
        results[scenario] = {"parameters": {}}
        for key in keys:
            results[scenario]["parameters"][key] = {}
            for variant in ("C", "E", "F"):
                is_null = scenario in NULL_SCENARIOS
                high = key.endswith("24.0")
                results[scenario]["parameters"][key][variant] = {
                    "false_alarm_rate": 0.02 if high else 0.20,
                    "sensitivity": (
                        0.95 if variant == "C" and high else
                        0.60 if high else 0.99
                    ),
                    "mean_detection_delay": 20.0 if high else 8.0,
                }
    return {"results": results}


class RobustHoldoutTests(unittest.TestCase):
    def test_selection_uses_only_training_null_gate_and_directional_sensitivity(self):
        selected = select_training_candidates(fake_sweep())
        c = next(item for item in selected if item["variant"] == "C" and item["selection_status"] != "fixed_default_control")
        self.assertEqual((c["k"], c["h"]), (0.5, 24.0))
        e = next(item for item in selected if item["variant"] == "E")
        self.assertEqual(e["selection_status"], "diagnostic_only_low_training_sensitivity")

    def test_ar1_heavy_tail_holdout_is_deterministic_and_changes_with_seed(self):
        first = generate_residuals(123, "student_t3_ar1_null")
        same = generate_residuals(123, "student_t3_ar1_null")
        other = generate_residuals(124, "student_t3_ar1_null")
        self.assertEqual(first, same)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 140)

    def test_variance_only_null_has_no_mean_shift(self):
        base = generate_residuals(456, "gaussian_ar1_null")
        jump = generate_residuals(456, "gaussian_ar1_variance_jump_null")
        # Same seed drives the same Gaussian sequence before the variance jump.
        self.assertEqual(base[:64], jump[:64])
        self.assertNotEqual(base[64:], jump[64:])

    def test_ledger_adapter_preserves_residuals(self):
        values = [0.5, -1.0, 2.5, -0.2]
        rows = residuals_to_stock_rows(values)
        self.assertEqual(len(rows), len(values))
        for index, row in enumerate(rows):
            expected = row["opening"] + row["arrivals"] - row["dispensed"] - row["expired"]
            self.assertAlmostEqual(expected - row["closing"], values[index])


if __name__ == "__main__":
    unittest.main()

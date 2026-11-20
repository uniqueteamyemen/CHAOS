import unittest
import numpy as np

from scripts.audits.p2_2_4_markov_injected_break_power import (
    inject_scenario,
    planned_break_index,
    summarize_records,
    extract_markov_rho_diagnostics,
    resolve_audit_source_commit,
)


class MarkovInjectedBreakPowerTests(unittest.TestCase):
    def test_audit_metadata_prefers_exact_checked_out_source_commit(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {
            "AUDIT_SOURCE_COMMIT": "checked-out-head-sha",
            "GITHUB_SHA": "synthetic-merge-sha",
        }):
            self.assertEqual(resolve_audit_source_commit(), "checked-out-head-sha")

    def test_rho_diagnostics_expose_three_distinct_coefficients(self):
        self.assertEqual(
            extract_markov_rho_diagnostics({
                "rho_raw": 0.94, "rho_used": 0.88, "rho_cusum_used": 0.71,
            }),
            {"rho_raw": 0.94, "rho_clipped": 0.88, "rho_cusum_used": 0.71},
        )

    def test_rho_diagnostics_reject_missing_or_inconsistent_values(self):
        with self.assertRaisesRegex(ArithmeticError, "rho_used"):
            extract_markov_rho_diagnostics({
                "rho_raw": 0.94, "rho_cusum_used": 0.71,
            })
        with self.assertRaisesRegex(ArithmeticError, "inconsistent_with_raw"):
            extract_markov_rho_diagnostics({
                "rho_raw": 0.94, "rho_used": 0.70, "rho_cusum_used": 0.71,
            })

    def test_summary_keeps_three_rho_distributions_separate(self):
        rows = [
            {
                "series_id": "energy_a", "category": "energy",
                "scenario": "mean_shift_2_5_initial_MAD",
                "sample_length": 100, "input_variant": "raw",
                "clean_detection": True, "post_break_alarm": True,
                "pre_break_alarm": False, "detection_delay_steps": 5,
                "rho_raw": 0.94, "rho_clipped": 0.88, "rho_cusum_used": 0.71,
            },
            {
                "series_id": "energy_a", "category": "energy",
                "scenario": "mean_shift_2_5_initial_MAD",
                "sample_length": 100, "input_variant": "raw",
                "clean_detection": True, "post_break_alarm": True,
                "pre_break_alarm": False, "detection_delay_steps": 7,
                "rho_raw": 0.91, "rho_clipped": 0.88, "rho_cusum_used": 0.68,
            },
        ]
        summary = summarize_records(rows)
        per_series = summary["per_series"][
            "energy_a|mean_shift_2_5_initial_MAD|n=100|raw"
        ]
        self.assertAlmostEqual(per_series["rho_raw_distribution"]["median"], 0.925)
        self.assertAlmostEqual(per_series["rho_clipped_distribution"]["median"], 0.88)
        self.assertAlmostEqual(per_series["rho_cusum_used_distribution"]["median"], 0.695)

    def test_break_index_is_predeclared_and_after_quiet_period(self):
        self.assertEqual(planned_break_index(100), 70)
        self.assertEqual(planned_break_index(539), 377)
        with self.assertRaises(ValueError):
            planned_break_index(80)

    def test_mean_shift_preserves_prefix_and_applies_fixed_quiet_scale_step(self):
        values = np.random.default_rng(31).normal(0.0, 0.05, 120)
        changed, effect, parameter = inject_scenario(
            values, "mean_shift_2_5_initial_MAD", 84
        )
        np.testing.assert_array_equal(changed[:84], values[:84])
        np.testing.assert_allclose(changed[84:] - values[84:], effect, rtol=0, atol=1e-15)
        self.assertIn("2.5", parameter)

    def test_volatility_jump_scales_deviations_without_changing_prefix_or_center(self):
        values = np.random.default_rng(32).normal(0.0, 0.04, 120)
        changed, multiplier, parameter = inject_scenario(
            values, "volatility_jump_2x", 84
        )
        center = float(np.median(values[:40]))
        np.testing.assert_array_equal(changed[:84], values[:84])
        np.testing.assert_allclose(
            changed[84:] - center,
            2.0 * (values[84:] - center),
            rtol=0.0,
            atol=1e-15,
        )
        self.assertEqual(multiplier, 2.0)
        self.assertIn("median", parameter)

    def test_series_aggregation_is_equal_weighted(self):
        rows = [
            {
                "series_id": "energy_a", "category": "energy",
                "scenario": "mean_shift_2_5_initial_MAD",
                "sample_length": 100, "input_variant": "raw",
                "clean_detection": True, "post_break_alarm": True,
                "pre_break_alarm": False, "detection_delay_steps": 5,
            },
            {
                "series_id": "energy_a", "category": "energy",
                "scenario": "mean_shift_2_5_initial_MAD",
                "sample_length": 100, "input_variant": "raw",
                "clean_detection": True, "post_break_alarm": True,
                "pre_break_alarm": False, "detection_delay_steps": 7,
            },
            {
                "series_id": "energy_b", "category": "energy",
                "scenario": "mean_shift_2_5_initial_MAD",
                "sample_length": 100, "input_variant": "raw",
                "clean_detection": False, "post_break_alarm": False,
                "pre_break_alarm": True, "detection_delay_steps": None,
            },
        ]
        summary = summarize_records(rows)
        category = summary["by_category"][
            "energy|n=100|mean_shift_2_5_initial_MAD|raw"
        ]
        self.assertEqual(category["series_count"], 2)
        self.assertEqual(category["clean_detection_probability_mean_across_series"], 0.5)


if __name__ == "__main__":
    unittest.main()

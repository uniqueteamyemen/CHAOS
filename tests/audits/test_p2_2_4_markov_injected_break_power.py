import unittest
import numpy as np

from scripts.audits.p2_2_4_markov_injected_break_power import (
    inject_scenario,
    planned_break_index,
    summarize_records,
)


class MarkovInjectedBreakPowerTests(unittest.TestCase):
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

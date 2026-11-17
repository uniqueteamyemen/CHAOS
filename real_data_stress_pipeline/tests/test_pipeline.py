import unittest
import numpy as np

from real_data_stress_pipeline.run_pipeline import (
    g0, g1, boot, longest_run, month, label_month, returns, stationary_sample, wilson, series_category, shock_eval,
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
        self.assertEqual(label_month(2024 * 12 + 11), "2024-12")

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

    def test_g1_passes_stationary_white_noise_screen(self):
        values = np.random.default_rng(12).normal(0, 0.01, 540)
        result = g1(values)
        self.assertTrue(result["passed"], result)
        self.assertLess(result["adf_p_value"], 0.05)
        self.assertGreaterEqual(result["kpss_p_value"], 0.05)

    def test_g1_rejects_trended_series(self):
        values = np.linspace(0, 10, 540) + np.random.default_rng(12).normal(0, 0.01, 540)
        result = g1(values)
        self.assertFalse(result["passed"])
        self.assertFalse(result["kpss_does_not_reject_level_stationarity"])

    def test_g1_does_not_test_short_series(self):
        result = g1(np.random.default_rng(4).normal(size=86))
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "NOT_TESTED")

    def test_stationary_bootstrap_is_skipped_when_g1_fails(self):
        result = boot(
            np.random.default_rng(4).normal(size=100),
            "test-series",
            12,
            {"passed": False, "status": "SCREEN_FAIL"},
        )
        self.assertEqual(result["status"], "SKIPPED_G1_SCREEN_FAILED")
        self.assertEqual(result["replicates"], 0)
        self.assertTrue(all(mode["runs"] == 0 for mode in result["by_mode"].values()))


    def test_series_categories_respect_domain_terms(self):
        self.assertEqual(series_category({"domain": "commodity", "name": "Crude Oil, Brent"}), "energy")
        self.assertEqual(series_category({"domain": "commodity", "name": "Copper"}), "metals")
        self.assertEqual(series_category({"domain": "commodity", "name": "Cocoa"}), "agriculture_food")
        self.assertEqual(series_category({"domain": "macro", "name": "CPI"}), "macro")

    def test_oil_anchor_excludes_non_energy_series(self):
        import json
        from pathlib import Path
        contract = json.loads((Path(__file__).resolve().parents[1] / "shock_event_contract.json").read_text(encoding="utf-8"))
        copper = {"domain": "commodity", "name": "Copper", "axis": ["2014-06"]}
        results = shock_eval(copper, [], contract)
        oil = next(x for x in results if x["event_id"] == "OIL_2014")
        self.assertFalse(oil["eligible"])

    def test_alarm_is_not_reused_for_overlapping_anchor_windows(self):
        import json
        from pathlib import Path
        contract = json.loads((Path(__file__).resolve().parents[1] / "shock_event_contract.json").read_text(encoding="utf-8"))
        series = {"domain": "macro", "name": "GEM CPI", "axis": ["2021-02"]}
        events = [{"detection_time": 0, "status": "CONFIRMED"}]
        matches = shock_eval(series, events, contract)
        matched = [x for x in matches if x["matched"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["event_id"], "COVID_2020")

if __name__ == "__main__":
    unittest.main()

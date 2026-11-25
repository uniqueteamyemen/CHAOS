import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_b3_2_retest.engine_b3_2_retest import (
    CalibratedSequentialBreakEngineB32,
)
from experiments.identity_lab.exp_sequential_break_b3_2_retest.benchmark_b3_2_retest import (
    CASES,
    classify_result,
)


class B32MinimalRetestTests(unittest.TestCase):
    def test_original_eight_case_matrix_is_preserved(self):
        self.assertEqual(
            [case[0] for case in CASES],
            [
                "gauss_r0.3_null",
                "gauss_r0.7_null",
                "gauss_r0.7_vjump",
                "t3_r0.3_null",
                "t3_r0.7_null",
                "t3_r0.7_vjump",
                "pos_shift_3.0s",
                "neg_shift_3.0s",
            ],
        )
        self.assertEqual(len(CASES), 8)

    def test_default_resolution_horizon_is_fourteen(self):
        engine = CalibratedSequentialBreakEngineB32()
        self.assertEqual(engine.resolution_horizon, 14)
        self.assertEqual(engine.return_to_baseline_z, 1.5)

    def test_rho_adjustment_matches_proposed_heuristic(self):
        rng = np.random.default_rng(412)
        values = np.r_[rng.normal(0.0, 1.0, 40), np.zeros(60)]
        adjusted = CalibratedSequentialBreakEngineB32(
            rho_bias_correction=True
        ).analyze(values)["diagnostics"]
        raw = CalibratedSequentialBreakEngineB32(
            rho_bias_correction=False
        ).analyze(values)["diagnostics"]

        expected = min(
            0.90,
            adjusted["rho_raw"] + (1.0 + 3.0 * adjusted["rho_raw"]) / 40.0,
        )
        self.assertAlmostEqual(adjusted["rho_adjusted"], expected, places=6)
        self.assertAlmostEqual(adjusted["rho_used"], expected, places=6)
        self.assertAlmostEqual(raw["rho_used"], raw["rho_raw"], places=6)
        self.assertAlmostEqual(raw["rho_raw"], adjusted["rho_raw"], places=6)

    def test_spike_requires_observed_reversion_to_be_transient(self):
        rng = np.random.default_rng(42)
        values = np.zeros(90, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55] = 10.0
        result = CalibratedSequentialBreakEngineB32(
            anomaly_z_thresh=4.5,
            break_percent_thresh=100.0,
        ).analyze(values)
        matching = [
            item for item in result["transient_anomalies"]
            if item["time"] == 55
        ]
        self.assertTrue(matching)
        self.assertGreater(matching[0]["resolved_at"], 55)
        self.assertLessEqual(matching[0]["resolution_age"], 14)
        self.assertLess(matching[0]["return_z"], 1.5)

    def test_nonreverting_pending_alert_is_not_called_transient(self):
        rng = np.random.default_rng(43)
        values = np.zeros(85, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55:] = np.where(np.arange(30) % 2 == 0, 8.0, -8.0)
        result = CalibratedSequentialBreakEngineB32(
            anomaly_z_thresh=4.5,
            break_percent_thresh=100.0,
        ).analyze(values)
        self.assertFalse(
            any(item["time"] == 55 for item in result["transient_anomalies"])
        )
        self.assertTrue(
            any(item["time"] == 55 for item in result["unresolved_alerts"])
        )

    def test_level_shift_pending_survives_longer_detection_delay(self):
        rng = np.random.default_rng(44)
        values = np.r_[
            rng.normal(0.0, 0.05, size=65),
            rng.normal(4.0, 0.05, size=75),
        ]
        result = CalibratedSequentialBreakEngineB32(
            anomaly_z_thresh=4.5,
            break_percent_thresh=85.0,
            resolution_horizon=14,
        ).analyze(values)
        resolved = [
            pending
            for event in result["structural_breaks"]
            for pending in event["resolved_pending_alerts"]
            if pending["time"] >= 65
        ]
        self.assertTrue(result["structural_breaks"])
        self.assertTrue(resolved)
        self.assertEqual(resolved[0]["status"], "RESOLVED_STRUCTURAL")

    def test_lifecycle_conservation_on_heavy_tail_correlated_series(self):
        rng = np.random.default_rng(46)
        innovations = rng.standard_t(df=3, size=140) / np.sqrt(3.0)
        values = np.empty(140)
        values[0] = innovations[0]
        rho = 0.7
        for idx in range(1, 140):
            values[idx] = (
                rho * values[idx - 1]
                + np.sqrt(1.0 - rho**2) * innovations[idx]
            )
        result = CalibratedSequentialBreakEngineB32().analyze(values)
        lifecycle = result["pending_lifecycle"]
        self.assertTrue(lifecycle["accounting_complete"])
        self.assertEqual(
            lifecycle["opened_count"],
            lifecycle["resolved_structural_count"]
            + lifecycle["resolved_transient_count"]
            + lifecycle["unresolved_count"],
        )

    def test_combined_counts_any_structural_transient_or_unresolved(self):
        result = {
            "structural_breaks": [{"detection_time": 70, "direction": -1}],
            "transient_anomalies": [],
            "unresolved_alerts": [{"time": 62}],
        }
        metrics = classify_result(result, shift_sigma=3.0, onset=65)
        self.assertTrue(metrics["combined_any_alert"])
        self.assertFalse(metrics["correct_structural_sequence"])
        self.assertTrue(metrics["wrong_direction_structural_sequence"])
        self.assertTrue(metrics["pre_onset_unresolved_sequence"])
        self.assertTrue(metrics["pre_onset_combined_sequence"])


if __name__ == "__main__":
    unittest.main()

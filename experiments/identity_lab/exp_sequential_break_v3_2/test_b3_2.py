import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_v3_2.engine_b3_2 import (
    CalibratedSequentialBreakEngineB32,
)
from experiments.identity_lab.exp_sequential_break_v3_2.benchmark_b3_2 import (
    classify_trial,
    generate_series,
    wilson_interval,
)


def empty_lifecycle(opened=0, structural=0, transient=0, unresolved=0):
    return {
        "opened_count": opened,
        "resolved_structural_count": structural,
        "resolved_transient_count": transient,
        "unresolved_count": unresolved,
        "accounting_complete": (
            opened == structural + transient + unresolved
        ),
    }


class SequentialBreakEngineB32Tests(unittest.TestCase):
    def test_default_resolution_horizon_is_fourteen(self):
        self.assertEqual(CalibratedSequentialBreakEngineB32().resolution_horizon, 14)

    def test_rho_heuristic_matches_proposed_formula(self):
        quiet = np.array([
            0.2, -0.1, 0.4, 0.1, -0.3, 0.5, 0.3, -0.2,
            0.6, 0.2, -0.1, 0.4, 0.1, -0.3, 0.5, 0.3,
            -0.2, 0.6, 0.2, -0.1, 0.4, 0.1, -0.3, 0.5,
            0.3, -0.2, 0.6, 0.2, -0.1, 0.4, 0.1, -0.3,
            0.5, 0.3, -0.2, 0.6, 0.2, -0.1, 0.4, 0.1,
        ], dtype=float)
        adjusted_engine = CalibratedSequentialBreakEngineB32(
            rho_bias_correction=True
        )
        raw, adjusted, used = adjusted_engine._estimate_rho(quiet)
        self.assertAlmostEqual(
            adjusted,
            min(0.90, raw + (1.0 + 3.0 * raw) / 40.0),
            places=10,
        )
        self.assertAlmostEqual(used, adjusted, places=10)

        raw_engine = CalibratedSequentialBreakEngineB32(
            rho_bias_correction=False
        )
        raw2, adjusted2, used2 = raw_engine._estimate_rho(quiet)
        self.assertAlmostEqual(raw2, raw, places=10)
        self.assertAlmostEqual(adjusted2, adjusted, places=10)
        self.assertAlmostEqual(used2, raw, places=10)

    def test_spike_resolves_transient_only_after_observed_reversion(self):
        rng = np.random.default_rng(42)
        series = np.zeros(90, dtype=float)
        series[:40] = rng.normal(0.0, 0.05, size=40)
        series[55] = 10.0
        result = CalibratedSequentialBreakEngineB32(
            anomaly_z_thresh=4.5,
            break_percent_thresh=95.0,
            resolution_horizon=14,
        ).analyze(series)
        matching = [
            item for item in result["transient_anomalies"]
            if item["time"] == 55
        ]
        self.assertTrue(matching)
        self.assertEqual(matching[0]["status"], "RESOLVED_TRANSIENT")
        self.assertGreater(matching[0]["resolved_at"], 55)
        self.assertLess(matching[0]["resolution_age"], 15)

    def test_nonreverting_spike_is_not_marked_transient(self):
        rng = np.random.default_rng(43)
        series = np.zeros(85, dtype=float)
        series[:40] = rng.normal(0.0, 0.05, size=40)
        series[55:] = np.where(np.arange(30) % 2 == 0, 8.0, -8.0)
        result = CalibratedSequentialBreakEngineB32(
            anomaly_z_thresh=4.5,
            break_percent_thresh=100.0,
            resolution_horizon=14,
        ).analyze(series)
        self.assertFalse(
            any(item["time"] == 55 for item in result["transient_anomalies"])
        )
        self.assertTrue(
            any(item["time"] == 55 for item in result["unresolved_alerts"])
        )

    def test_pending_shift_is_resolved_as_structural(self):
        rng = np.random.default_rng(44)
        series = np.r_[
            rng.normal(0.0, 0.05, size=65),
            rng.normal(4.0, 0.05, size=75),
        ]
        result = CalibratedSequentialBreakEngineB32(
            anomaly_z_thresh=4.5,
            break_percent_thresh=85.0,
            resolution_horizon=14,
        ).analyze(series)
        resolved = [
            pending
            for item in result["structural_breaks"]
            for pending in item["resolved_pending_alerts"]
        ]
        self.assertTrue(result["structural_breaks"])
        self.assertTrue(resolved)
        self.assertTrue(
            all(x["status"] == "RESOLVED_STRUCTURAL" for x in resolved)
        )

    def test_series_end_preserves_unresolved_pending_alert(self):
        rng = np.random.default_rng(45)
        series = np.zeros(56, dtype=float)
        series[:40] = rng.normal(0.0, 0.05, size=40)
        series[55] = 10.0
        result = CalibratedSequentialBreakEngineB32().analyze(series)
        self.assertTrue(
            any(x["time"] == 55 for x in result["unresolved_alerts"])
        )
        self.assertFalse(
            any(x["time"] == 55 for x in result["transient_anomalies"])
        )

    def test_pending_lifecycle_is_conserved(self):
        series = generate_series(
            np.random.default_rng(46),
            dist="t3", rho=0.7, var_jump=True, shift_sigma=2.5,
        )
        result = CalibratedSequentialBreakEngineB32().analyze(series)
        life = result["pending_lifecycle"]
        self.assertTrue(life["accounting_complete"])
        self.assertEqual(
            life["opened_count"],
            life["resolved_structural_count"]
            + life["resolved_transient_count"]
            + life["unresolved_count"],
        )

    def test_combined_alert_union_includes_wrong_direction_and_pending(self):
        result = {
            "structural_breaks": [{"detection_time": 70, "direction": -1}],
            "transient_anomalies": [],
            "unresolved_alerts": [{"time": 62}],
            "pending_lifecycle": empty_lifecycle(
                opened=1, unresolved=1
            ),
        }
        metrics = classify_trial(result, shift_sigma=3.0, onset=65)
        self.assertTrue(metrics["combined_sequence"])
        self.assertFalse(metrics["correct_structural_sequence"])
        self.assertTrue(metrics["wrong_structural_sequence"])
        self.assertTrue(metrics["pre_onset_combined_sequence"])

    def test_detection_delay_uses_earliest_correct_structural_event(self):
        result = {
            "structural_breaks": [
                {"detection_time": 74, "direction": 1},
                {"detection_time": 69, "direction": 1},
                {"detection_time": 67, "direction": -1},
            ],
            "transient_anomalies": [],
            "unresolved_alerts": [],
            "pending_lifecycle": empty_lifecycle(),
        }
        metrics = classify_trial(result, shift_sigma=3.0, onset=65)
        self.assertEqual(metrics["detection_delay"], 4)
        self.assertTrue(metrics["correct_structural_sequence"])
        self.assertTrue(metrics["wrong_structural_sequence"])

    def test_generator_reproducibility_and_post_onset_shift(self):
        a = generate_series(
            np.random.default_rng(1234),
            dist="t3", rho=0.7, var_jump=False, shift_sigma=0.0,
        )
        shifted = generate_series(
            np.random.default_rng(1234),
            dist="t3", rho=0.7, var_jump=False, shift_sigma=2.5,
        )
        self.assertTrue(np.array_equal(a[:65], shifted[:65]))
        self.assertTrue(np.allclose(shifted[65:] - a[65:], 2.5))

    def test_wilson_interval(self):
        lo, hi = wilson_interval(25, 500)
        self.assertLessEqual(lo, 0.05)
        self.assertGreaterEqual(hi, 0.05)


if __name__ == "__main__":
    unittest.main()

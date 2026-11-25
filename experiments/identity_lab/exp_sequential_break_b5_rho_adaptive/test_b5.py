import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_b5_rho_adaptive.engine_b5 import (
    RhoAdaptiveTransientKendallEngineB5,
)


def quiet_low_rho(seed: int = 43) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 0.05, size=40)


def quiet_high_rho(seed: int = 731) -> np.ndarray:
    rng = np.random.default_rng(seed)
    innovations = rng.normal(0.0, 0.05, size=40)
    values = np.zeros(40, dtype=float)
    for i in range(1, values.size):
        values[i] = 0.85 * values[i - 1] + innovations[i]
    return values


def series_with_spikes(quiet: np.ndarray, points: int) -> np.ndarray:
    values = np.zeros(90, dtype=float)
    values[:40] = quiet
    values[55 : 55 + points] = 10.0
    return values


class B5RhoAdaptiveTests(unittest.TestCase):
    def test_requested_b4_inherited_configuration(self):
        engine = RhoAdaptiveTransientKendallEngineB5()
        self.assertEqual(engine.anomaly_z_thresh, 3.8)
        self.assertEqual(engine.winsor_cap, 1.8)
        self.assertEqual(engine.persistence_z_thresh, 1.45)
        self.assertEqual(engine.break_percent_thresh, 85.0)
        self.assertEqual(engine.resolution_horizon, 14)
        self.assertEqual(engine.return_to_baseline_z, 1.5)
        self.assertTrue(engine.rho_bias_correction)

    def test_half_strength_rho_correction_is_exact(self):
        rng = np.random.default_rng(90210)
        values = np.r_[rng.normal(0.0, 1.0, 40), rng.normal(0.0, 1.0, 100)]
        result = RhoAdaptiveTransientKendallEngineB5().analyze(values)
        diagnostics = result["diagnostics"]
        rho_raw = diagnostics["rho_raw"]
        expected_adjusted = rho_raw + 0.5 * (
            (1.0 + 3.0 * max(0.0, rho_raw)) / 40.0
        )
        expected_used = float(np.clip(expected_adjusted, 0.0, 0.88))
        self.assertAlmostEqual(diagnostics["rho_adjusted"], expected_adjusted, places=6)
        self.assertAlmostEqual(diagnostics["rho_used"], expected_used, places=6)
        self.assertGreaterEqual(diagnostics["rho_used"], 0.0)
        self.assertLessEqual(diagnostics["rho_used"], 0.88)

    def test_low_rho_uses_two_same_direction_points(self):
        result = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(series_with_spikes(quiet_low_rho(), 2))
        self.assertLessEqual(result["diagnostics"]["rho_used"], 0.50)
        terminal_times = (
            [x["time"] for x in result["transient_anomalies"]]
            + [x["time"] for x in result["unresolved_alerts"]]
            + [
                p["time"]
                for b in result["structural_breaks"]
                for p in b["resolved_pending_alerts"]
            ]
        )
        self.assertIn(56, terminal_times)

    def test_high_rho_rejects_two_points_but_accepts_three(self):
        quiet = quiet_high_rho()
        two = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(series_with_spikes(quiet, 2))
        self.assertGreater(two["diagnostics"]["rho_used"], 0.50)
        self.assertEqual(two["pending_lifecycle"]["opened_count"], 0)

        three = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(series_with_spikes(quiet, 3))
        self.assertGreater(three["diagnostics"]["rho_used"], 0.50)
        terminal_times = (
            [x["time"] for x in three["transient_anomalies"]]
            + [x["time"] for x in three["unresolved_alerts"]]
            + [
                p["time"]
                for b in three["structural_breaks"]
                for p in b["resolved_pending_alerts"]
            ]
        )
        self.assertIn(57, terminal_times)

    def test_single_extreme_point_does_not_open_pending(self):
        result = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(series_with_spikes(quiet_low_rho(), 1))
        self.assertEqual(result["pending_lifecycle"]["opened_count"], 0)

    def test_opposite_sign_pair_does_not_open_pending(self):
        values = np.zeros(90, dtype=float)
        values[:40] = quiet_low_rho(44)
        values[55] = 10.0
        values[56] = -10.0
        result = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(values)
        self.assertEqual(result["pending_lifecycle"]["opened_count"], 0)

    def test_transient_requires_observed_return_to_quiet_band(self):
        result = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(series_with_spikes(quiet_low_rho(45), 2))
        matched = [x for x in result["transient_anomalies"] if x["time"] == 56]
        self.assertTrue(matched)
        self.assertLess(matched[0]["return_z"], 1.5)
        self.assertGreater(matched[0]["resolved_at"], 56)
        self.assertLessEqual(matched[0]["resolution_age"], 14)

    def test_nonreverting_pending_remains_unresolved(self):
        values = np.zeros(90, dtype=float)
        values[:40] = quiet_low_rho(46)
        values[55:57] = 10.0
        values[57:] = np.where(np.arange(33) % 2 == 0, -10.0, 10.0)
        result = RhoAdaptiveTransientKendallEngineB5(
            break_percent_thresh=100.0
        ).analyze(values)
        self.assertFalse(any(x["time"] == 56 for x in result["transient_anomalies"]))
        self.assertTrue(any(x["time"] == 56 for x in result["unresolved_alerts"]))

    def test_pending_lifecycle_accounting_is_exact(self):
        values = np.r_[quiet_high_rho(47), np.zeros(100, dtype=float)]
        result = RhoAdaptiveTransientKendallEngineB5().analyze(values)
        lifecycle = result["pending_lifecycle"]
        self.assertTrue(lifecycle["accounting_complete"])
        self.assertEqual(
            lifecycle["opened_count"],
            lifecycle["resolved_structural_count"]
            + lifecycle["resolved_transient_count"]
            + lifecycle["unresolved_count"],
        )


if __name__ == "__main__":
    unittest.main()

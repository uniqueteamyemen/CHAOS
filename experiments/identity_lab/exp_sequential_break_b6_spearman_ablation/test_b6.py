import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.engine_b6 import (
    PearsonSpearmanFixedGateEngineB6,
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
    values = np.zeros(140, dtype=float)
    values[:40] = quiet
    values[55 : 55 + points] = 10.0
    return values


class B6CorrelationAblationTests(unittest.TestCase):
    def test_required_configuration_is_fixed(self):
        for method in ("pearson", "spearman"):
            engine = PearsonSpearmanFixedGateEngineB6(
                correlation_method=method,
                break_percent_thresh=83.5,
            )
            self.assertEqual(engine.quiet_end, 40)
            self.assertEqual(engine.window_size, 12)
            self.assertEqual(engine.anomaly_z_thresh, 3.8)
            self.assertEqual(engine.winsor_cap, 1.8)
            self.assertEqual(engine.persistence_z_thresh, 1.45)
            self.assertEqual(engine.break_percent_thresh, 83.5)
            self.assertEqual(engine.resolution_horizon, 14)
            self.assertFalse(engine.rho_bias_correction)

    def test_pearson_rho_is_raw_clipped_without_inflation(self):
        quiet = quiet_high_rho(90210)
        values = np.r_[quiet, np.zeros(100)]
        result = PearsonSpearmanFixedGateEngineB6(
            correlation_method="pearson"
        ).analyze(values)
        center = float(np.median(quiet))
        spread = max(float(np.median(np.abs(quiet - center)) * 1.4826), 1e-6)
        q_norm = (quiet - center) / spread
        expected_raw = float(np.corrcoef(q_norm[:-1], q_norm[1:])[0, 1])
        expected_used = float(np.clip(expected_raw, 0.0, 0.88))
        diag = result["diagnostics"]
        self.assertAlmostEqual(diag["rho_raw"], expected_raw, places=6)
        self.assertAlmostEqual(diag["rho_used"], expected_used, places=6)
        self.assertAlmostEqual(diag["rho_adjusted"], expected_raw, places=6)
        self.assertFalse(diag["rho_bias_correction_enabled"])
        self.assertEqual(diag["rho_method"], "pearson")

    def test_spearman_rho_uses_double_argsort_and_matrix_scalar(self):
        quiet = quiet_high_rho(90211)
        values = np.r_[quiet, np.zeros(100)]
        result = PearsonSpearmanFixedGateEngineB6(
            correlation_method="spearman"
        ).analyze(values)
        r0 = np.argsort(np.argsort(quiet[:-1])).astype(float)
        r1 = np.argsort(np.argsort(quiet[1:])).astype(float)
        expected_raw = float(np.corrcoef(r0, r1)[0, 1])
        expected_used = float(np.clip(expected_raw, 0.0, 0.88))
        diag = result["diagnostics"]
        self.assertAlmostEqual(diag["rho_raw"], expected_raw, places=6)
        self.assertAlmostEqual(diag["rho_used"], expected_used, places=6)
        self.assertEqual(diag["rho_method"], "spearman")
        self.assertIsInstance(diag["rho_used"], float)
        self.assertGreaterEqual(diag["rho_used"], 0.0)
        self.assertLessEqual(diag["rho_used"], 0.88)

    def test_constant_quiet_window_falls_back_to_zero_rho(self):
        values = np.zeros(140, dtype=float)
        for method in ("pearson", "spearman"):
            result = PearsonSpearmanFixedGateEngineB6(
                correlation_method=method
            ).analyze(values)
            self.assertEqual(result["diagnostics"]["rho_raw"], 0.0)
            self.assertEqual(result["diagnostics"]["rho_used"], 0.0)

    def test_invalid_correlation_method_is_rejected(self):
        with self.assertRaises(ValueError):
            PearsonSpearmanFixedGateEngineB6(correlation_method="kendall")

    def test_three_points_open_pending_and_two_points_do_not(self):
        quiet = quiet_low_rho()
        engine = PearsonSpearmanFixedGateEngineB6(
            correlation_method="pearson",
            break_percent_thresh=100.0,
        )
        two = engine.analyze(series_with_spikes(quiet, 2))
        three = engine.analyze(series_with_spikes(quiet, 3))
        self.assertEqual(two["pending_lifecycle"]["opened_count"], 0)
        terminal_times = (
            [x["time"] for x in three["transient_anomalies"]]
            + [x["time"] for x in three["unresolved_alerts"]]
            + [
                pending["time"]
                for item in three["structural_breaks"]
                for pending in item["resolved_pending_alerts"]
            ]
        )
        self.assertIn(57, terminal_times)

    def test_three_point_gate_requires_one_sign(self):
        values = np.zeros(140, dtype=float)
        values[:40] = quiet_low_rho(44)
        values[55:58] = [10.0, 10.0, -10.0]
        result = PearsonSpearmanFixedGateEngineB6(
            break_percent_thresh=100.0
        ).analyze(values)
        self.assertEqual(result["pending_lifecycle"]["opened_count"], 0)

    def test_transient_requires_observed_return_to_baseline(self):
        result = PearsonSpearmanFixedGateEngineB6(
            break_percent_thresh=100.0
        ).analyze(series_with_spikes(quiet_low_rho(45), 3))
        matched = [item for item in result["transient_anomalies"] if item["time"] == 57]
        self.assertTrue(matched)
        self.assertLess(matched[0]["return_z"], 1.5)
        self.assertGreater(matched[0]["resolved_at"], 57)
        self.assertLessEqual(matched[0]["resolution_age"], 14)

    def test_nonreverting_alert_is_unresolved_and_accounted_once(self):
        values = np.zeros(140, dtype=float)
        values[:40] = quiet_low_rho(46)
        values[55:58] = 10.0
        values[58:] = np.where(np.arange(82) % 2 == 0, -10.0, 10.0)
        result = PearsonSpearmanFixedGateEngineB6(
            break_percent_thresh=100.0
        ).analyze(values)
        life = result["pending_lifecycle"]
        self.assertFalse(any(item["time"] == 57 for item in result["transient_anomalies"]))
        self.assertTrue(any(item["time"] == 57 for item in result["unresolved_alerts"]))
        self.assertTrue(life["accounting_complete"])
        self.assertEqual(
            life["opened_count"],
            life["resolved_structural_count"]
            + life["resolved_transient_count"]
            + life["unresolved_count"],
        )


if __name__ == "__main__":
    unittest.main()

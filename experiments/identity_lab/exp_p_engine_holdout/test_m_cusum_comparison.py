"""Unit tests for the submitted Gemini M-CUSUM implementation and ablations."""
import unittest

from experiments.identity_lab.exp_p_engine_holdout.m_cusum_comparison import (
    run_mcusum,
    _m_score,
)


class GeminiMcusumTests(unittest.TestCase):
    def test_huber_scores_are_bounded_by_psi_parameter(self):
        values = [(-1.0 if i % 2 == 0 else 1.0) for i in range(40)] + [1e9, -1e9, 1e9]
        _, diag = run_mcusum(values)
        self.assertEqual(diag["max_abs_psi"], 2.0)

    def test_input_and_quiet_window_validation(self):
        with self.assertRaisesRegex(ValueError, "quiet_window_invalid"):
            run_mcusum([1.0, 2.0, 3.0])
        with self.assertRaisesRegex(ValueError, "series_nonfinite"):
            run_mcusum([float("nan")] + [1.0, -1.0] * 30)

    def test_original_algorithm_repeats_alerts_after_first_crossing(self):
        values = [(-1.0 if i % 2 == 0 else 1.0) for i in range(40)] + [10.0] * 15
        alerts, _ = run_mcusum(values)
        self.assertGreater(len(alerts), 1)
        self.assertTrue(all("time" in alert and "direction" in alert for alert in alerts))

    def test_alert_scoring_uses_first_onset_direction_not_pre_onset_alert(self):
        alerts = [
            {"time": 50, "direction": 1, "stat": 8.0},
            {"time": 66, "direction": -1, "stat": 9.0},
            {"time": 68, "direction": 1, "stat": 8.0},
        ]
        score = _m_score(alerts, "positive_step_3sigma")
        self.assertTrue(score["pre_onset_false_alarm"])
        self.assertTrue(score["detected"])
        self.assertTrue(score["wrong_direction"])
        self.assertEqual(score["delay"], 3)

    def test_ablation_switches_do_not_change_input_or_psi_bound(self):
        values = [(-1.0 if i % 2 == 0 else 1.0) for i in range(40)] + [5.0] * 20
        full, full_diag = run_mcusum(values)
        no_sn, no_sn_diag = run_mcusum(values, use_self_normalizer=False)
        no_rho, no_rho_diag = run_mcusum(values, use_adaptive_k=False)
        self.assertLessEqual(full_diag["max_abs_psi"], 2.0)
        self.assertEqual(full_diag["max_abs_psi"], no_sn_diag["max_abs_psi"])
        self.assertEqual(full_diag["max_abs_psi"], no_rho_diag["max_abs_psi"])
        self.assertIn("rho_used", full_diag)
        self.assertEqual(no_sn_diag["self_normalizer_enabled"], False)
        self.assertEqual(no_rho_diag["adaptive_k_enabled"], False)


if __name__ == "__main__":
    unittest.main()

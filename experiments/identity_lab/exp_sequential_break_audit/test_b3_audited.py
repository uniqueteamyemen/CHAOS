import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import (
    AuditedSequentialBreakEngineB3,
    classify_trial,
    generate_series,
)


class AuditedSequentialBreakEngineB3Tests(unittest.TestCase):
    def test_rejects_invalid_shapes_and_nonfinite_data(self):
        engine = AuditedSequentialBreakEngineB3()
        with self.assertRaisesRegex(ValueError, "one_dimensional"):
            engine.analyze(np.ones((2, 100)))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            engine.analyze(np.r_[np.ones(40), np.nan, np.ones(20)])

    def test_rho_estimation_returns_finite_scalar(self):
        series = generate_series(
            np.random.default_rng(731),
            dist="gauss",
            rho=0.5,
            var_jump=False,
            shift_sigma=0.0,
        )
        result = AuditedSequentialBreakEngineB3().analyze(series)
        rho = result["diagnostics"]["rho_estimate"]
        self.assertIsInstance(rho, float)
        self.assertTrue(np.isfinite(rho))
        self.assertGreaterEqual(rho, 0.0)
        self.assertLessEqual(rho, 0.88)

    def test_isolated_spike_resolves_to_transient_once(self):
        rng = np.random.default_rng(42)
        series = np.zeros(100, dtype=float)
        series[:40] = rng.normal(0.0, 0.05, size=40)
        series[55] = 10.0

        result = AuditedSequentialBreakEngineB3(
            break_percent_thresh=85.0,
            resolution_horizon=6,
        ).analyze(series)

        self.assertFalse(result["structural_breaks"])
        self.assertTrue(any(x["time"] == 55 for x in result["transient_anomalies"]))
        lifecycle = result["pending_lifecycle"]
        self.assertTrue(lifecycle["accounting_complete"])
        self.assertEqual(
            lifecycle["opened_count"],
            lifecycle["resolved_structural_count"]
            + lifecycle["resolved_transient_count"]
            + lifecycle["unresolved_count"],
        )

    def test_end_of_series_preserves_unresolved_pending_spike(self):
        rng = np.random.default_rng(43)
        series = np.zeros(52, dtype=float)
        series[:40] = rng.normal(0.0, 0.05, size=40)
        series[51] = 10.0

        result = AuditedSequentialBreakEngineB3().analyze(series)

        self.assertTrue(any(x["time"] == 51 for x in result["unresolved_alerts"]))
        self.assertTrue(
            all(x["status"] == "UNRESOLVED_AT_END" for x in result["unresolved_alerts"])
        )
        self.assertTrue(result["pending_lifecycle"]["accounting_complete"])

    def test_shift_resolves_pending_as_structural_when_break_arrives_in_horizon(self):
        rng = np.random.default_rng(44)
        series = np.zeros(110, dtype=float)
        series[:40] = rng.normal(0.0, 0.04, size=40)
        series[52:] = 4.0

        result = AuditedSequentialBreakEngineB3(
            break_percent_thresh=85.0,
            resolution_horizon=30,
        ).analyze(series)

        self.assertTrue(result["structural_breaks"])
        resolved = [
            p
            for brk in result["structural_breaks"]
            for p in brk["resolved_pending_alerts"]
        ]
        self.assertTrue(resolved)
        self.assertTrue(
            all(p["status"] == "RESOLVED_STRUCTURAL" for p in resolved)
        )
        self.assertTrue(result["pending_lifecycle"]["accounting_complete"])

    def test_combined_metric_includes_wrong_direction_structural_alerts(self):
        result = {
            "structural_breaks": [
                {"detection_time": 70, "direction": -1},
            ],
            "transient_anomalies": [],
            "unresolved_alerts": [],
        }
        metrics = classify_trial(result, shift_sigma=3.0, onset=65)
        self.assertFalse(metrics["structural_metric"])
        self.assertTrue(metrics["any_structural_alert"])
        self.assertTrue(metrics["combined_any_alert"])

    def test_delay_uses_earliest_directionally_correct_detection(self):
        result = {
            "structural_breaks": [
                {"detection_time": 72, "direction": 1},
                {"detection_time": 69, "direction": 1},
                {"detection_time": 67, "direction": -1},
            ],
            "transient_anomalies": [],
            "unresolved_alerts": [],
        }
        metrics = classify_trial(result, shift_sigma=3.0, onset=65)
        self.assertEqual(metrics["detection_delay"], 4)
        self.assertEqual(metrics["correct_structural_events"], 2)
        self.assertEqual(metrics["wrong_direction_structural_events"], 1)

    def test_combined_is_sequence_union_not_event_sum(self):
        result = {
            "structural_breaks": [
                {"detection_time": 80, "direction": 1},
            ],
            "transient_anomalies": [
                {"time": 90},
                {"time": 95},
            ],
            "unresolved_alerts": [
                {"time": 100},
            ],
        }
        metrics = classify_trial(result, shift_sigma=0.0)
        self.assertTrue(metrics["combined_any_alert"])
        self.assertEqual(metrics["correct_structural_events"], 0)


if __name__ == "__main__":
    unittest.main()

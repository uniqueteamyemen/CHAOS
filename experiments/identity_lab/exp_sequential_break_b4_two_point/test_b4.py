import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import (
    AuditedSequentialBreakEngineB3,
)
from experiments.identity_lab.exp_sequential_break_b4_two_point.engine_b4 import (
    TwoPointTransientWinsor18EngineB4,
)


class B4MinimalChangeTests(unittest.TestCase):
    def test_requested_configuration(self):
        engine = TwoPointTransientWinsor18EngineB4()
        self.assertEqual(engine.anomaly_z_thresh, 3.8)
        self.assertEqual(engine.winsor_cap, 1.8)
        self.assertEqual(engine.persistence_z_thresh, 1.45)
        self.assertEqual(engine.resolution_horizon, 14)
        self.assertEqual(engine.return_to_baseline_z, 1.5)
        self.assertFalse(engine.rho_bias_correction)

    def test_rho_used_is_raw_b3_1_lag1_estimate(self):
        rng = np.random.default_rng(90210)
        values = np.r_[rng.normal(0.0, 1.0, 40), rng.normal(0.0, 1.0, 100)]
        b31 = AuditedSequentialBreakEngineB3().analyze(values)
        b4 = TwoPointTransientWinsor18EngineB4().analyze(values)
        self.assertAlmostEqual(b4["diagnostics"]["rho_used"], b4["diagnostics"]["rho_raw"], places=6)
        self.assertAlmostEqual(b4["diagnostics"]["rho_used"], b31["diagnostics"]["rho_estimate"], places=6)

    def test_single_extreme_point_does_not_open_pending(self):
        rng = np.random.default_rng(42)
        values = np.zeros(90, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55] = 10.0
        result = TwoPointTransientWinsor18EngineB4(break_percent_thresh=100.0).analyze(values)
        self.assertEqual(result["pending_lifecycle"]["opened_count"], 0)

    def test_two_consecutive_same_direction_points_open_pending(self):
        rng = np.random.default_rng(43)
        values = np.zeros(90, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55:57] = 10.0
        result = TwoPointTransientWinsor18EngineB4(break_percent_thresh=100.0).analyze(values)
        terminal_times = (
            [x["time"] for x in result["transient_anomalies"]]
            + [x["time"] for x in result["unresolved_alerts"]]
            + [p["time"] for b in result["structural_breaks"] for p in b["resolved_pending_alerts"]]
        )
        self.assertIn(56, terminal_times)
        lifecycle = result["pending_lifecycle"]
        self.assertEqual(
            lifecycle["opened_count"],
            lifecycle["resolved_structural_count"] + lifecycle["resolved_transient_count"] + lifecycle["unresolved_count"],
        )

    def test_opposite_sign_pair_does_not_open_pending(self):
        rng = np.random.default_rng(44)
        values = np.zeros(90, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55] = 10.0
        values[56] = -10.0
        result = TwoPointTransientWinsor18EngineB4(break_percent_thresh=100.0).analyze(values)
        self.assertEqual(result["pending_lifecycle"]["opened_count"], 0)

    def test_transient_requires_observed_return_to_quiet_band(self):
        rng = np.random.default_rng(45)
        values = np.zeros(90, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55:57] = 10.0
        result = TwoPointTransientWinsor18EngineB4(break_percent_thresh=100.0).analyze(values)
        matched = [x for x in result["transient_anomalies"] if x["time"] == 56]
        self.assertTrue(matched)
        self.assertLess(matched[0]["return_z"], 1.5)
        self.assertGreater(matched[0]["resolved_at"], 56)
        self.assertLessEqual(matched[0]["resolution_age"], 14)

    def test_nonreverting_pair_is_not_resolved_as_transient(self):
        rng = np.random.default_rng(46)
        values = np.zeros(90, dtype=float)
        values[:40] = rng.normal(0.0, 0.05, size=40)
        values[55:] = np.where(np.arange(35) % 2 == 0, 10.0, -10.0)
        result = TwoPointTransientWinsor18EngineB4(break_percent_thresh=100.0).analyze(values)
        self.assertFalse(any(x["time"] == 56 for x in result["transient_anomalies"]))
        self.assertTrue(any(x["time"] == 56 for x in result["unresolved_alerts"]))

    def test_horizon_and_lifecycle_accounting(self):
        rng = np.random.default_rng(47)
        values = np.r_[rng.normal(0.0, 0.05, 40), rng.normal(0.0, 1.0, 100)]
        result = TwoPointTransientWinsor18EngineB4().analyze(values)
        self.assertEqual(TwoPointTransientWinsor18EngineB4().resolution_horizon, 14)
        lifecycle = result["pending_lifecycle"]
        self.assertTrue(lifecycle["accounting_complete"])
        self.assertEqual(
            lifecycle["opened_count"],
            lifecycle["resolved_structural_count"] + lifecycle["resolved_transient_count"] + lifecycle["unresolved_count"],
        )


if __name__ == "__main__":
    unittest.main()

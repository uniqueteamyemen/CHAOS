"""Governance tests for C3 equal-risk calibration."""
import unittest

from p1_4_validation.c3.run_equal_risk_calibration import (
    CANDIDATES,
    FOCUS_GRID,
    HUBER_GRID,
    MIN_VALID_REPLICATES,
    P0_TARGET,
    REPLICATES,
    calibrate_arm,
    deterministic_seed,
    validate_holdout,
)


class C3EqualRiskCalibrationTests(unittest.TestCase):
    def test_frozen_protocol_constants(self):
        self.assertEqual(REPLICATES, 1000)
        self.assertEqual(MIN_VALID_REPLICATES, 950)
        self.assertEqual(P0_TARGET, 0.10)
        self.assertEqual(len(CANDIDATES), 3)
        self.assertEqual(FOCUS_GRID[0], 15)
        self.assertGreaterEqual(FOCUS_GRID[-1], 1200)
        self.assertEqual(HUBER_GRID[0], 4)
        self.assertGreaterEqual(HUBER_GRID[-1], 200)

    def test_threshold_selected_on_development_and_holdout_cannot_retune(self):
        development = [0.0] * 1000
        holdout = [100.0] * 1000
        result = calibrate_arm(development, holdout, (10, 20, 30))
        self.assertEqual(result["frozen_threshold"], 10.0)
        self.assertEqual(result["development_status"], "CALIBRATED")
        self.assertEqual(result["holdout"]["status"], "FAIL")
        self.assertFalse(result["holdout_retuning"])
        self.assertEqual(result["frozen_threshold"], 10.0)

    def test_insufficient_development_fails_closed(self):
        result = calibrate_arm([0.0] * (MIN_VALID_REPLICATES - 1), [0.0] * 1000, (10, 20))
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIsNone(result["frozen_threshold"])
        self.assertEqual(result["holdout"]["status"], "NOT_RUN_NO_DEVELOPMENT_THRESHOLD")

    def test_no_development_threshold_is_not_calibratable(self):
        # Every predeclared threshold alarms in more than the allowed null share.
        result = calibrate_arm([100.0] * 1000, [0.0] * 1000, (1, 2, 3))
        self.assertEqual(result["status"], "NOT_CALIBRATABLE")
        self.assertIsNone(result["frozen_threshold"])
        self.assertEqual(result["holdout"]["status"], "NOT_RUN_NO_DEVELOPMENT_THRESHOLD")

    def test_seed_ledger_is_deterministic_and_phase_separated(self):
        d1 = deterministic_seed("UNRATE", 1, "development", 7)
        d2 = deterministic_seed("UNRATE", 1, "development", 7)
        h1 = deterministic_seed("UNRATE", 1, "holdout", 7)
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, h1)

    def test_non_finite_or_empty_threshold_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "C3_INVALID_THRESHOLD"):
            calibrate_arm([0.0] * 1000, [0.0] * 1000, (float("inf"),))
        with self.assertRaisesRegex(ValueError, "C3_INVALID_THRESHOLD"):
            validate_holdout([0.0] * 1000, float("nan"))
        with self.assertRaisesRegex(ValueError, "C3_EMPTY_THRESHOLD_GRID"):
            calibrate_arm([0.0] * 1000, [0.0] * 1000, ())


if __name__ == "__main__":
    unittest.main()

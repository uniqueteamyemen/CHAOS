"""Governance tests for C3 independent equal-risk calibration."""
import unittest
from pathlib import Path

from p1_4_validation.c3.run_equal_risk_calibration import (
    CANDIDATES,
    FOCUS_GRID,
    HUBER_GRID,
    MIN_VALID_REPLICATES,
    P0_TARGET,
    REPLICATES,
    calibrate_arm,
    deterministic_seed,
)
from p1_4_validation.c3.run_historical_break_evaluation import load_evaluation_contract


class C3EqualRiskCalibrationTests(unittest.TestCase):
    def test_non_finite_or_empty_threshold_configuration_is_rejected(self):
        from p1_4_validation.c3.run_equal_risk_calibration import validate_holdout
        with self.assertRaisesRegex(ValueError, "C3_INVALID_THRESHOLD"):
            calibrate_arm([0.0] * 1000, [0.0] * 1000, (float("inf"),))
        with self.assertRaisesRegex(ValueError, "C3_INVALID_THRESHOLD"):
            validate_holdout([0.0] * 1000, float("nan"))
        with self.assertRaisesRegex(ValueError, "C3_EMPTY_THRESHOLD_GRID"):
            calibrate_arm([0.0] * 1000, [0.0] * 1000, ())

    def test_frozen_protocol_constants(self):
        self.assertEqual(REPLICATES, 1000)
        self.assertEqual(MIN_VALID_REPLICATES, 950)
        self.assertEqual(P0_TARGET, 0.10)
        self.assertEqual(len(CANDIDATES), 3)
        self.assertEqual(FOCUS_GRID[0], 15)
        self.assertGreaterEqual(FOCUS_GRID[-1], 1200)
        self.assertEqual(HUBER_GRID[0], 4)
        self.assertGreaterEqual(HUBER_GRID[-1], 200)

    def test_development_uses_empirical_p0_not_development_wilson(self):
        development = [0.0] * 900 + [10.0] * 100
        holdout = [0.0] * 1000
        result = calibrate_arm(development, holdout, (10, 20))
        self.assertEqual(result["frozen_threshold"], 10.0)
        self.assertEqual(result["development"]["p0"], 0.10)
        self.assertGreater(result["development"]["wilson_upper_95_one_sided"], P0_TARGET)
        self.assertEqual(result["status"], "VALIDATED")
        self.assertFalse(result["holdout_retuning"])

    def test_holdout_failure_never_retunes_development_threshold(self):
        development = [0.0] * 1000
        holdout = [100.0] * 1000
        result = calibrate_arm(development, holdout, (10, 20, 30))
        self.assertEqual(result["frozen_threshold"], 10.0)
        self.assertEqual(result["development_status"], "CALIBRATED")
        self.assertEqual(result["holdout"]["status"], "FAIL")
        self.assertEqual(result["status"], "NOT_VALIDATED")
        self.assertFalse(result["holdout_retuning"])

    def test_insufficient_development_abstains(self):
        result = calibrate_arm(
            [0.0] * (MIN_VALID_REPLICATES - 1), [0.0] * 1000, (10, 20)
        )
        self.assertEqual(result["status"], "ABSTAINED")
        self.assertIsNone(result["frozen_threshold"])
        self.assertEqual(result["holdout"]["status"], "NOT_RUN_NO_DEVELOPMENT_THRESHOLD")

    def test_no_development_threshold_abstains(self):
        result = calibrate_arm([100.0] * 1000, [0.0] * 1000, (1, 2, 3))
        self.assertEqual(result["status"], "ABSTAINED")
        self.assertEqual(result["raw_calibration_status"], "NOT_CALIBRATABLE")
        self.assertIsNone(result["frozen_threshold"])

    def test_insufficient_holdout_abstains_without_retuning(self):
        result = calibrate_arm([0.0] * 1000, [0.0] * 949, (10, 20))
        self.assertEqual(result["status"], "ABSTAINED")
        self.assertEqual(result["frozen_threshold"], 10.0)
        self.assertEqual(result["holdout"]["status"], "INCONCLUSIVE")
        self.assertFalse(result["holdout_retuning"])

    def test_seed_ledger_is_deterministic_and_phase_separated(self):
        d1 = deterministic_seed("UNRATE", 1, "development", 7)
        d2 = deterministic_seed("UNRATE", 1, "development", 7)
        h1 = deterministic_seed("UNRATE", 1, "holdout", 7)
        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, h1)

    def test_expected_signs_and_twelve_month_window_are_explicit(self):
        root = Path(__file__).resolve().parents[2]
        _contract, events = load_evaluation_contract(
            root / "p1_4_validation/c3/c3_source_contract_v1.json"
        )
        self.assertEqual(
            {series_id: event["expected_sign"] for series_id, event in events.items()},
            {"UNRATE": 1, "ICSA": 1, "WCOILBRENTEU": -1},
        )
        self.assertTrue(
            all(event["matching_window_months"] == 12 for event in events.values())
        )


if __name__ == "__main__":
    unittest.main()

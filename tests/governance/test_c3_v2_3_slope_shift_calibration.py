"""Tests for preregistered Development/Holdout threshold gates."""
import json
import unittest
from pathlib import Path

from p1_4_validation.c3.c3_v2_3_slope_shift_calibration import (
    evaluate_holdout,
    select_dev_threshold,
)

PROTOCOL = Path(__file__).resolve().parents[2] / "p1_4_validation" / "c3" / "c3_v2_3_slope_shift_preregistration.json"


class C3V23PreregistrationTests(unittest.TestCase):
    def test_protocol_freezes_seed_count_gates_and_series(self):
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(protocol["status"], "PRE_REGISTERED")
        self.assertEqual(protocol["null_protocol"]["replicates_per_phase"], 2000)
        self.assertEqual(protocol["risk_gates"]["development_wilson_u95_max"], 0.085)
        self.assertEqual(protocol["risk_gates"]["holdout_wilson_u95_max"], 0.10)
        self.assertEqual(protocol["analysis"]["target_series"], ["ICSA", "UNRATE", "PAYEMS"])
        self.assertEqual(
            protocol["null_protocol"]["seed_namespace"],
            "CHAOS:C3_V2_3_LOCAL_SLOPE_SHIFT_2000X2_V1_PREREG_20261127",
        )

    def test_threshold_is_selected_from_development_only(self):
        dev_scores = [0.0] * 1800 + [3.0] * 100 + [4.0] * 100
        selected = select_dev_threshold(
            dev_scores, [3.0, 4.0], target_u95=0.085, min_valid=1900
        )
        self.assertEqual(selected["status"], "CALIBRATED")
        self.assertEqual(selected["frozen_threshold"], 4.0)
        self.assertLessEqual(selected["development"]["wilson_upper_95_one_sided"], 0.085)

    def test_holdout_applies_one_frozen_threshold_without_retuning(self):
        holdout_scores = [0.0] * 1800 + [4.0] * 200
        report = evaluate_holdout(
            holdout_scores, 4.0, target_u95=0.10, min_valid=1900
        )
        self.assertTrue(report["evaluated"])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["frozen_threshold"], 4.0)
        self.assertFalse(report["holdout_retuning"])

    def test_holdout_not_evaluated_without_dev_threshold(self):
        report = evaluate_holdout(
            [0.0] * 2000, None, target_u95=0.10, min_valid=1900
        )
        self.assertFalse(report["evaluated"])
        self.assertEqual(report["status"], "NOT_RUN_NO_DEVELOPMENT_THRESHOLD")


if __name__ == "__main__":
    unittest.main()

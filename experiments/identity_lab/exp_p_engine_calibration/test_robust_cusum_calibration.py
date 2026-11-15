"""Unit tests for confidence-bound based robust CUSUM threshold selection."""
import unittest

from experiments.identity_lab.exp_p_engine_calibration.robust_cusum_calibration import (
    evaluate_gates,
    select_thresholds,
    NULL_SCENARIOS,
    SHIFT_SCENARIOS,
    VARIANTS,
)


def fake_cell(false_upper, sensitivity_lower, pre_upper):
    result = {}
    for scenario in NULL_SCENARIOS:
        result[scenario] = {
            variant: {"false_alarm_wilson95": [0.0, false_upper]}
            for variant in VARIANTS
        }
    for scenario in SHIFT_SCENARIOS:
        result[scenario] = {
            variant: {
                "pre_onset_false_alarm_wilson95": [0.0, pre_upper],
                "sensitivity_wilson95": [sensitivity_lower, 1.0],
            }
            for variant in VARIANTS
        }
    return result


class RobustCusumCalibrationTests(unittest.TestCase):
    def test_all_three_confidence_bound_gates_are_required(self):
        cell = fake_cell(0.04, 0.80, 0.04)
        gates = evaluate_gates(cell, "C")
        self.assertTrue(gates["all_gates_pass"])
        cell["student_t3_ar1_variance_jump_null"]["C"]["false_alarm_wilson95"][1] = 0.06
        gates = evaluate_gates(cell, "C")
        self.assertFalse(gates["null_gate_pass"])
        self.assertFalse(gates["all_gates_pass"])

    def test_pre_onset_false_alarm_gate_is_not_ignored(self):
        cell = fake_cell(0.03, 0.90, 0.08)
        gates = evaluate_gates(cell, "E")
        self.assertTrue(gates["null_gate_pass"])
        self.assertFalse(gates["pre_onset_gate_pass"])
        self.assertFalse(gates["all_gates_pass"])

    def test_selects_lowest_h_that_passes_all_gates(self):
        calibration = {
            "parameter_results": {
                "24.0": fake_cell(0.08, 0.90, 0.03),
                "32.0": fake_cell(0.04, 0.82, 0.04),
                "40.0": fake_cell(0.03, 0.85, 0.03),
            }
        }
        selections = select_thresholds(calibration)
        self.assertEqual(selections["C"]["h"], 32.0)
        self.assertEqual(selections["E"]["h"], 32.0)
        self.assertEqual(selections["F"]["h"], 32.0)

    def test_no_candidate_is_selected_when_sensitivity_bound_fails(self):
        calibration = {"parameter_results": {"96.0": fake_cell(0.01, 0.70, 0.02)}}
        selections = select_thresholds(calibration)
        self.assertIsNone(selections["C"])


if __name__ == "__main__":
    unittest.main()

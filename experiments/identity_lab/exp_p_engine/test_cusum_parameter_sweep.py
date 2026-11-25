"""Tests for detector-isolated CUSUM k/h parameter-sweep scoring."""
import unittest
from experiments.identity_lab.exp_p_engine.cusum_parameter_sweep import score_cusum_hits

class CusumParameterSweepTests(unittest.TestCase):
    def test_null_scoring_counts_only_cusum_hits_after_quiet_window(self):
        result = score_cusum_hits([
            {"detector": "cusum_positive", "time": 40, "sign": 1},
            {"detector": "sign_run", "time": 60, "sign": 1},
            {"detector": "cusum_negative", "time": 41, "sign": -1},
        ], scenario="stable_null")
        self.assertTrue(result["false_alarm"])
        self.assertEqual(result["false_alarm_events"], 1)

    def test_break_scoring_separates_pre_onset_alarm_and_correct_detection(self):
        result = score_cusum_hits([
            {"detector": "cusum_positive", "time": 55, "sign": 1},
            {"detector": "cusum_negative", "time": 67, "sign": -1},
            {"detector": "cusum_positive", "time": 70, "sign": 1},
        ], scenario="positive_step_3sigma", onset=65)
        self.assertTrue(result["pre_onset_false_alarm"])
        self.assertTrue(result["detected"])
        self.assertTrue(result["wrong_direction"])
        self.assertEqual(result["delay"], 5)

    def test_break_without_correct_direction_is_a_miss(self):
        result = score_cusum_hits([
            {"detector": "cusum_negative", "time": 68, "sign": -1},
        ], scenario="positive_step_3sigma", onset=65)
        self.assertFalse(result["detected"])
        self.assertIsNone(result["delay"])

if __name__ == "__main__":
    unittest.main()

"""Tests for independent robust CUSUM holdout selection."""
import unittest
from experiments.identity_lab.exp_p_engine_calibration.robust_cusum_holdout import (
    selected_candidates, NULL_SCENARIOS, SHIFT_SCENARIOS,
)


class RobustCusumHoldoutTests(unittest.TestCase):
    def test_only_stage_j_selections_and_fixed_control_are_used(self):
        calibration = {"selections": {
            "C": {"k": 0.5, "h": 64.0},
            "E": None,
            "F": {"k": 0.5, "h": 80.0},
        }}
        candidates = selected_candidates(calibration)
        self.assertEqual(
            [(item["variant"], item["h"]) for item in candidates],
            [("C", 8.5), ("C", 64.0), ("F", 80.0)],
        )

    def test_holdout_scenario_sets_cover_nulls_and_both_directions(self):
        self.assertEqual(len(NULL_SCENARIOS), 4)
        self.assertEqual(len(SHIFT_SCENARIOS), 6)
        self.assertTrue(any("positive" in item for item in SHIFT_SCENARIOS))
        self.assertTrue(any("negative" in item for item in SHIFT_SCENARIOS))


if __name__ == "__main__":
    unittest.main()

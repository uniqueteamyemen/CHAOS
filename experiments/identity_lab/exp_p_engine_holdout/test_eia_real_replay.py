"""Focused contracts for the EIA real-data replay."""
import unittest
from experiments.identity_lab.exp_p_engine_holdout.eia_real_replay import (
    inject_copy, ordinal_day, iso_day,
)

class EiaRealReplayTests(unittest.TestCase):
    def test_date_ordinal_round_trip(self):
        self.assertEqual(iso_day(ordinal_day("2026-10-30")), "2026-10-30")

    def test_injection_creates_copy_and_leaves_source_unchanged(self):
        source = [
            {"time": "2015-01-09", "residual": 1.0},
            {"time": "2015-01-16", "residual": -2.0},
            {"time": "2015-01-23", "residual": 0.5},
        ]
        result = inject_copy(source, 1, 3.0)
        self.assertEqual([item["residual"] for item in source], [1.0, -2.0, 0.5])
        self.assertEqual([item["residual"] for item in result], [1.0, 1.0, 3.5])
        self.assertIsNot(source[0], result[0])

if __name__ == "__main__":
    unittest.main()

"""Tests for fixed-policy FOCuS scale ablation and PAYEMS report visibility."""
import unittest
from datetime import date, timedelta

import numpy as np

from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3
from p1_4_validation.c3.run_c3_v2_2_focus_ablation import (
    ablation_matrix,
    rearm_mad_diagnostics,
    robust_mad,
)


class C3V22FocusAblationTests(unittest.TestCase):
    def test_matrix_contains_two_wcoil_arms_and_full_unrate_factorial(self):
        matrix = ablation_matrix()
        self.assertEqual(len(matrix), 10)
        wcoil = [row for row in matrix if row["series_id"] == "WCOILBRENTEU"]
        unrate = [row for row in matrix if row["series_id"] == "UNRATE"]
        self.assertEqual(len(wcoil), 2)
        self.assertEqual(
            {(row["threshold"], row["rearm_points"], row["scale_points"]) for row in wcoil},
            {(250.0, 20, None), (250.0, 20, 40)},
        )
        self.assertEqual(len(unrate), 8)
        self.assertEqual(
            {
                (row["threshold"], row["rearm_points"], row["scale_points"])
                for row in unrate
            },
            {
                (threshold, rearm, scale)
                for threshold in (175.0, 200.0)
                for rearm in (4, 5)
                for scale in (None, 40)
            },
        )

    def test_robust_mad_reports_raw_and_gaussian_consistent_scale(self):
        result = robust_mad(np.asarray([1.0, 2.0, 3.0, 4.0, 100.0]))
        self.assertEqual(result["median"], 3.0)
        self.assertEqual(result["mad_raw"], 1.0)
        self.assertAlmostEqual(result["mad_sigma"], 1.4826)

    def test_rearm_diagnostics_compare_legacy_and_trailing_40_windows(self):
        values = np.arange(60, dtype=float)
        rows = [
            {
                "observation_date": (date(2020, 1, 1) + timedelta(days=7 * i)).isoformat(),
                "observation_date_obj": date(2020, 1, 1) + timedelta(days=7 * i),
            }
            for i in range(60)
        ]
        diagnostics = rearm_mad_diagnostics(
            values,
            rows,
            {"rearm_intervals": [{
                "start_inclusive": 45,
                "end_exclusive": 49,
            }]},
            rearm_points=4,
            target_anchor=None,
        )
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["legacy_scale_window"]["mad"]["n"], 4)
        self.assertEqual(diagnostics[0]["scale40_window"]["mad"]["n"], 40)
        self.assertEqual(
            diagnostics[0]["scale40_window"]["start_index"], 9
        )
        self.assertNotEqual(
            diagnostics[0]["legacy_scale_window"]["mad"]["mad_sigma"],
            diagnostics[0]["scale40_window"]["mad"]["mad_sigma"],
        )

    def test_payems_report_rows_include_each_detector_not_only_bartlett(self):
        profile = {
            "detector_summary": {
                "FOCuS (monthly rearm 4; weekly rearm 20)": {
                    "role": "CANDIDATE", "validated_all_series": True,
                    "matched_event_series_pairs": 3, "total_event_series_pairs": 15,
                    "matched_episode_clusters": 2, "episode_clusters_with_any_registered_pair": 7,
                    "total_unmatched_alarm_count": 1,
                },
                "Post-Quiet Huber + MAD": {
                    "role": "CANDIDATE", "validated_all_series": True,
                    "matched_event_series_pairs": 0, "total_event_series_pairs": 15,
                    "matched_episode_clusters": 0, "episode_clusters_with_any_registered_pair": 7,
                    "total_unmatched_alarm_count": 0,
                },
                "Post-Quiet Huber + Bartlett LRV": {
                    "role": "CANDIDATE", "validated_all_series": True,
                    "matched_event_series_pairs": 2, "total_event_series_pairs": 15,
                    "matched_episode_clusters": 2, "episode_clusters_with_any_registered_pair": 7,
                    "total_unmatched_alarm_count": 6,
                },
                "Hybrid: FOCuS + Huber confirmation": {
                    "role": "CANDIDATE", "validated_all_series": False,
                    "matched_event_series_pairs": 1, "total_event_series_pairs": 15,
                    "matched_episode_clusters": 1, "episode_clusters_with_any_registered_pair": 7,
                    "total_unmatched_alarm_count": 1,
                },
                "global_selection": {"status": "NO_GLOBAL_WINNER"},
            }
        }
        rows = c3.payems_detector_rows(profile)
        by_name = {row["detector"]: row for row in rows}
        self.assertIn("FOCuS (monthly rearm 4; weekly rearm 20)", by_name)
        self.assertIn("Post-Quiet Huber + MAD", by_name)
        self.assertIn("Post-Quiet Huber + Bartlett LRV", by_name)
        self.assertIn("Hybrid: FOCuS + Huber confirmation", by_name)
        self.assertEqual(by_name["Post-Quiet Huber + Bartlett LRV"]["unmatched_alarms"], 6)
        self.assertEqual(by_name["FOCuS (monthly rearm 4; weekly rearm 20)"]["matched_pairs"], 3)
        self.assertEqual(
            by_name["Hybrid: FOCuS + Huber confirmation"]["validation"],
            "NOT_VALIDATED",
        )


if __name__ == "__main__":
    unittest.main()

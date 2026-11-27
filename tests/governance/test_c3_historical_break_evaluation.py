"""Governance tests for C3 directional and bounded historical event matching."""
import csv
import io
import json
import unittest
from datetime import date
from unittest.mock import patch

import numpy as np

from p1_4_validation.injection_runner import focus_reset_rearm
from p1_4_validation.c3.run_historical_break_evaluation import (
    CSV_FIELDNAMES,
    add_calendar_months,
    audit_prefix_replay,
    csv_export_row,
    extract_hits,
    score_events,
    ensure_causal_release_order,
)


def rows(dates, frequency="Monthly"):
    return [{
        "available_at": value.isoformat(),
        "available_at_obj": value,
        "frequency": frequency,
    } for value in dates]


class C3HistoricalEvaluationTests(unittest.TestCase):
    def test_first_release_availability_must_follow_observation_order(self):
        ordered = rows([date(2020, 1, 8), date(2020, 1, 15), date(2020, 1, 22)])
        ensure_causal_release_order("TEST_SERIES", ordered)
        unordered = rows([date(2020, 1, 8), date(2020, 1, 22), date(2020, 1, 15)])
        with self.assertRaisesRegex(
            ValueError, "C3_NON_MONOTONIC_FIRST_RELEASE_AVAILABILITY:TEST_SERIES:2"
        ):
            ensure_causal_release_order("TEST_SERIES", unordered)

    def test_baseline_alarm_count_excludes_quiet_and_matched_early_alarm(self):
        data = rows([
            date(2004, 1, 1), date(2004, 2, 1), date(2004, 3, 1),
            date(2004, 4, 1), date(2004, 5, 1), date(2004, 6, 1),
        ])
        hits = [
            {"index": 2, "sign": 1},
            {"index": 4, "sign": -1},
            {"index": 5, "sign": 1},
        ]
        result = score_events(
            data, "2004-05-01", hits, quiet_points=1, expected_sign=1,
        )
        self.assertEqual(result["false_alarms_before_anchor"], 1)
        self.assertEqual(result["hit_miss"], "HIT")
        self.assertEqual(result["match_status"], "MATCHED")
        self.assertEqual(result["detection_available_at"], "2004-06-01")
        self.assertEqual(result["detection_lag_days"], 31)
        self.assertEqual(result["matching_window_months"], 12)

    def test_weekly_lag_uses_available_at(self):
        data = rows(
            [date(2020, 3, 5), date(2020, 3, 12), date(2020, 3, 19)],
            frequency="Weekly, ending Saturday",
        )
        result = score_events(
            data, "2020-03-11", [{"index": 2, "sign": 1}],
            quiet_points=1, expected_sign=1,
        )
        self.assertEqual(result["hit_miss"], "HIT")
        self.assertEqual(result["detection_lag_days"], 8)
        self.assertEqual(result["lag_unit"], "weeks")
        self.assertEqual(result["detection_lag_weeks_or_months"], 1.143)

    def test_opposite_direction_is_miss(self):
        result = score_events(
            rows([date(2020, 1, 1), date(2020, 1, 15)]),
            "2020-01-15", [{"index": 1, "sign": -1}],
            quiet_points=0, expected_sign=1,
        )
        self.assertEqual(result["hit_miss"], "MISS")
        self.assertEqual(result["match_status"], "WRONG_SIGN")
        self.assertEqual(result["wrong_sign_within_window_count"], 1)
        self.assertIsNone(result["detection_available_at"])

    def test_correct_direction_outside_twelve_month_window_is_miss(self):
        result = score_events(
            rows([date(2018, 12, 31), date(2020, 1, 15)]),
            "2020-01-15", [{"index": 0, "sign": 1}],
            quiet_points=0, expected_sign=1,
        )
        self.assertEqual(result["hit_miss"], "MISS")
        self.assertEqual(result["match_status"], "OUT_OF_WINDOW")
        self.assertEqual(result["out_of_window_alarm_count"], 1)

    def test_early_warning_inside_window_is_a_match_with_negative_lag(self):
        result = score_events(
            rows([date(2020, 2, 11), date(2020, 3, 11)]),
            "2020-03-11", [{"index": 0, "sign": 1}],
            quiet_points=0, expected_sign=1,
        )
        self.assertEqual(result["hit_miss"], "HIT")
        self.assertEqual(result["detection_lag_days"], -29)
        self.assertEqual(result["false_alarms_before_anchor"], 0)

    def test_calendar_window_handles_leap_day_and_rejects_other_window(self):
        self.assertEqual(add_calendar_months(date(2020, 2, 29), 12), date(2021, 2, 28))
        self.assertEqual(add_calendar_months(date(2020, 3, 31), -1), date(2020, 2, 29))
        with self.assertRaisesRegex(ValueError, "MUST_BE_12_MONTHS"):
            score_events(
                rows([date(2020, 1, 1)]), "2020-01-01", [],
                quiet_points=0, expected_sign=1, matching_window_months=18,
            )

    def test_csv_schema_covers_every_metric_and_serializes_alarm_dates(self):
        data = rows(
            [date(2020, 1, 1), date(2020, 1, 8), date(2020, 1, 15)],
            frequency="Weekly",
        )
        metrics = score_events(
            data, "2020-01-15",
            [{"index": 1, "sign": 1}, {"index": 2, "sign": -1}],
            quiet_points=1, expected_sign=1,
        )
        required_fixed_fields = {
            "event_id", "series_id", "detector", "detector_status",
        }
        self.assertEqual(
            set(CSV_FIELDNAMES) - required_fixed_fields,
            set(metrics),
        )
        row = {
            "event_id": "TEST_EVENT",
            "series_id": "TEST_SERIES",
            "detector": "TEST_DETECTOR",
            "detector_status": "OK",
            "metrics": metrics,
        }
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerow(csv_export_row(row))
        parsed = next(csv.DictReader(io.StringIO(buffer.getvalue())))
        self.assertEqual(json.loads(parsed["baseline_alarm_dates"]), [])
        self.assertEqual(json.loads(parsed["all_post_anchor_alarm_dates"]), ["2020-01-15"])
        self.assertEqual(json.loads(parsed["wrong_sign_alarm_dates"]), ["2020-01-15"])
        self.assertEqual(parsed["detection_index"], "1")

    def test_empty_match_is_explicit_miss(self):
        result = score_events(
            rows([date(2004, 1, 1), date(2004, 2, 1), date(2004, 3, 1)]),
            "2004-02-15", [], quiet_points=1, expected_sign=1,
        )
        self.assertEqual(result["hit_miss"], "MISS")
        self.assertEqual(result["match_status"], "NO_MATCH")
        self.assertIsNone(result["detection_lag_days"])
        self.assertEqual(result["false_alarms_before_anchor"], 0)

    @patch("p1_4_validation.c3.run_historical_break_evaluation.focus_reset_rearm")
    def test_focus_uses_multi_alert_reset_rearm(self, reset_rearm):
        reset_rearm.return_value = {
            "status": "OK",
            "hits": [
                {"index": 48, "sign": 1, "detection_index": 48},
                {"index": 93, "sign": -1, "detection_index": 93},
            ],
            "rearm_intervals": [{"start_inclusive": 49, "end_exclusive": 69}],
            "initial_calibration_observations": 40,
            "rearm_calibration_observations": 20,
        }
        hits, status, metadata = extract_hits(
            "FOCuS", np.arange(180.0), threshold=21.0
        )
        self.assertEqual(status, "OK")
        self.assertEqual([hit["index"] for hit in hits], [48, 93])
        self.assertTrue(metadata["reset_rearm"])
        self.assertEqual(metadata["rearm_calibration_observations"], 20)
        reset_rearm.assert_called_once()
        self.assertEqual(reset_rearm.call_args.kwargs["threshold"], 21.0)
        self.assertEqual(reset_rearm.call_args.kwargs["min_series_length"], 41)

    @patch("p2_b_benchmark.p2c_engine.focus_detector")
    def test_reset_rearm_restarts_with_20_observations_after_each_alert(self, focus_detector):
        values = np.arange(150, dtype=float)
        calls = []

        def fake_focus(segment, *, quiet_points, threshold):
            calls.append((np.asarray(segment).copy(), quiet_points))
            if len(calls) == 1:
                return {"status": "OK", "hits": [{
                    "detection_index": 50, "estimated_change_index": 47, "sign": 1,
                }]}
            if len(calls) == 2:
                return {"status": "OK", "hits": [{
                    "detection_index": 30, "estimated_change_index": 27, "sign": -1,
                }]}
            return {"status": "OK", "hits": []}

        focus_detector.side_effect = fake_focus
        result = focus_reset_rearm(
            values, threshold=7.0, quiet_points=40, rearm_quiet_points=20
        )
        self.assertEqual(
            [row["detection_index"] for row in result["hits"]], [50, 81]
        )
        self.assertEqual([row[1] for row in calls], [40, 20, 20])
        self.assertEqual(result["rearm_intervals"], [
            {"start_inclusive": 51, "end_exclusive": 71},
            {"start_inclusive": 82, "end_exclusive": 102},
        ])

    @patch("p1_4_validation.c3.run_historical_break_evaluation.extract_hits")
    def test_each_alarm_is_replayed_on_its_exact_prefix(self, mocked_extract):
        hits = [{"index": 50, "sign": 1}, {"index": 80, "sign": -1}]

        def replay(detector, values, threshold=None):
            return [hit for hit in hits if hit["index"] < len(values)], "OK", {}

        mocked_extract.side_effect = replay
        count = audit_prefix_replay("FOCuS", np.arange(100.0), hits, threshold=17.0)
        self.assertEqual(count, 2)
        self.assertEqual(
            [call.args[1].size for call in mocked_extract.call_args_list],
            [51, 81],
        )


if __name__ == "__main__":
    unittest.main()

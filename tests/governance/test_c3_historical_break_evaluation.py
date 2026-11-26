"""Contract tests for the pinned C3 historical evaluation."""
import unittest
from datetime import date

from p1_4_validation.c3.run_historical_break_evaluation import score_events


def rows(dates, frequency="Monthly"):
    return [{
        "available_at": d.isoformat(),
        "available_at_obj": d,
        "frequency": frequency,
    } for d in dates]


class C3HistoricalEvaluationTests(unittest.TestCase):
    def test_baseline_alarm_count_excludes_first_40_and_uses_available_at(self):
        data = rows([
            date(2004, 1, 1), date(2004, 2, 1), date(2004, 3, 1),
            date(2004, 4, 1), date(2004, 5, 1), date(2004, 6, 1),
        ])
        hits = [{"index": 2, "sign": 1}, {"index": 4, "sign": -1},
                {"index": 5, "sign": 1}]
        result = score_events(data, "2004-05-01", hits, quiet_points=1)
        self.assertEqual(result["false_alarms_before_anchor"], 1)
        self.assertEqual(result["hit_miss"], "HIT")
        self.assertEqual(result["detection_available_at"], "2004-05-01")
        self.assertEqual(result["detection_lag_days"], 0)

    def test_weekly_lag_uses_release_availability_date(self):
        data = rows([date(2020, 3, 5), date(2020, 3, 12),
                     date(2020, 3, 19)], frequency="Weekly, ending Saturday")
        result = score_events(data, "2020-03-11", [{"index": 2, "sign": 1}], quiet_points=1)
        self.assertEqual(result["hit_miss"], "HIT")
        self.assertEqual(result["detection_lag_days"], 8)
        self.assertEqual(result["lag_unit"], "weeks")
        self.assertEqual(result["detection_lag_weeks_or_months"], 1.143)

    def test_miss_is_explicit_and_has_no_lag(self):
        data = rows([date(2004, 1, 1), date(2004, 2, 1), date(2004, 3, 1)])
        result = score_events(data, "2004-02-15", [], quiet_points=1)
        self.assertEqual(result["hit_miss"], "MISS")
        self.assertIsNone(result["detection_lag_days"])
        self.assertEqual(result["false_alarms_before_anchor"], 0)


if __name__ == "__main__":
    unittest.main()

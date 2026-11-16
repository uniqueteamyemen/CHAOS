import unittest
from datetime import datetime, timezone

from structural_engine.isolated_break_detector_v1.run_real_data import (
    month_axis,
    monthly_counts,
    quarterly_axis,
    quarterly_counts,
)


class RealDataAggregationTests(unittest.TestCase):
    def test_calendar_axes_cover_frozen_window(self):
        self.assertEqual(len(month_axis()), 300)
        self.assertEqual(len(quarterly_axis()), 100)
        self.assertEqual(month_axis()[0], "2000-01")
        self.assertEqual(month_axis()[-1], "2024-12")
        self.assertEqual(quarterly_axis()[0], "2000-Q1")
        self.assertEqual(quarterly_axis()[-1], "2024-Q4")

    def test_quarterly_aggregation_preserves_event_counts(self):
        timestamps = [
            datetime(2000, 1, 3, tzinfo=timezone.utc),
            datetime(2000, 2, 3, tzinfo=timezone.utc),
            datetime(2000, 3, 3, tzinfo=timezone.utc),
            datetime(2000, 4, 3, tzinfo=timezone.utc),
        ]
        monthly = monthly_counts(timestamps)
        quarterly = quarterly_counts(timestamps)
        self.assertEqual(monthly[:4], [1, 1, 1, 1])
        self.assertEqual(quarterly[:2], [3, 1])
        self.assertEqual(sum(monthly), len(timestamps))
        self.assertEqual(sum(quarterly), len(timestamps))

    def test_out_of_window_events_are_rejected(self):
        timestamps = [datetime(1999, 12, 31, tzinfo=timezone.utc)]
        with self.assertRaisesRegex(ValueError, "outside_frozen_query_window"):
            quarterly_counts(timestamps)


if __name__ == "__main__":
    unittest.main()

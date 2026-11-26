"""Regression tests for C3 v2 Wilson calibration and event assignment."""
import unittest
from datetime import date
from unittest.mock import patch

from p1_4_validation.c3 import run_c3_v2_equal_risk_evaluation as c3


def event(event_id, anchor, episode="EPISODE"):
    return {
        "event_id": event_id,
        "episode_id": episode,
        "series_id": "TEST",
        "anchor_date": anchor,
        "anchor_type": "TEST_ANCHOR",
        "expected_sign": 1,
    }


def data_rows(dates):
    return [{
        "available_at": value.isoformat(),
        "available_at_obj": value,
        "frequency": "Monthly",
    } for value in dates]


class C3V2EqualRiskTests(unittest.TestCase):
    def test_registered_series_tape_requires_full_pre_event_and_matching_window_coverage(self):
        dates = []
        year, month = 2018, 1
        for _ in range(80):
            dates.append(date(year, month, 1))
            month += 1
            if month == 13:
                year += 1
                month = 1
        rows = [
            {
                "observation_date_obj": value,
                "available_at_obj": value + __import__("datetime").timedelta(days=5),
                "frequency": "Monthly",
                "units": "units",
            }
            for value in dates
        ]
        config = {
            "series_id": "TEST",
            "observation_start": dates[0].isoformat(),
            "observation_end": dates[-1].isoformat(),
            "minimum_observation_count": 60,
            "frequency": "Monthly",
            "units": "units",
        }
        events = [{
            "event_id": "EVENT_2022",
            "anchor_date": "2022-05-01",
            "expected_sign_by_series": {"TEST": 1},
        }]
        c3.validate_registered_series_tape("TEST", rows, config, events)

        too_early = [{
            **events[0],
            "anchor_date": "2021-03-01",
        }]
        with self.assertRaisesRegex(ValueError, "C3_V2_FIRST_40_NOT_PRE_EVENT"):
            c3.validate_registered_series_tape("TEST", rows, config, too_early)

        short_end = rows[:60]
        short_config = {**config, "observation_end": short_end[-1]["observation_date_obj"].isoformat()}
        with self.assertRaisesRegex(ValueError, "C3_V2_EVENT_WINDOW_END_NOT_COVERED"):
            c3.validate_registered_series_tape("TEST", short_end, short_config, events)

    def test_registered_series_rejects_frequency_or_units_drift(self):
        import datetime

        dates = []
        year, month = 2018, 1
        for _ in range(80):
            dates.append(date(year, month, 1))
            month += 1
            if month == 13:
                year += 1
                month = 1
        rows = [{
            "observation_date_obj": value,
            "available_at_obj": value + datetime.timedelta(days=5),
            "frequency": "Weekly",
            "units": "wrong units",
        } for value in dates]
        config = {
            "observation_start": dates[0].isoformat(),
            "observation_end": dates[-1].isoformat(),
            "minimum_observation_count": 60,
            "frequency": "Monthly",
            "units": "units",
        }
        events = [{
            "event_id": "EVENT_2022",
            "anchor_date": "2022-05-01",
            "expected_sign_by_series": {"TEST": 1},
        }]
        with self.assertRaisesRegex(ValueError, "C3_V2_FREQUENCY_CONTRACT_MISMATCH"):
            c3.validate_registered_series_tape("TEST", rows, config, events)

    def test_development_threshold_uses_wilson_upper_not_empirical_p0(self):
        development = [10.0] * 100 + [0.0] * 900
        holdout = [0.0] * 1000
        result = c3.choose_threshold_by_dev_wilson(
            development, holdout, (10, 20)
        )
        self.assertEqual(result["frozen_threshold"], 20.0)
        self.assertEqual(result["development"]["p0"], 0.0)
        self.assertLessEqual(
            result["development"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )
        self.assertEqual(result["status"], "VALIDATED")

    def test_holdout_failure_keeps_development_threshold_frozen(self):
        development = [0.0] * 1000
        holdout = [100.0] * 1000
        result = c3.choose_threshold_by_dev_wilson(
            development, holdout, (10, 20, 30)
        )
        self.assertEqual(result["frozen_threshold"], 10.0)
        self.assertEqual(result["status"], "NOT_VALIDATED")
        self.assertFalse(result["holdout_retuning"])
        self.assertGreater(
            result["holdout"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )

    def test_invalid_thresholds_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "C3_V2_INVALID_THRESHOLD"):
            c3.choose_threshold_by_dev_wilson([0.0] * 1000, [0.0] * 1000, (float("nan"),))
        with self.assertRaisesRegex(ValueError, "C3_V2_INVALID_THRESHOLD"):
            c3.finite_positive_threshold(float("inf"))

    @patch.object(c3, "post_quiet_huber_detector")
    def test_huber_historical_path_allows_multi_alert_replay(self, detector):
        detector.return_value = {
            "status": "OK",
            "hits": [
                {"index": 60, "sign": 1},
                {"index": 120, "sign": -1},
                {"index": 180, "sign": 1},
            ],
            "metadata": {"max_events": c3.MAX_EVENTS},
        }
        import numpy as np
        hits, status, _ = c3.extract_detector_hits(
            "Post-Quiet Huber + MAD", np.arange(220.0), threshold=25.0
        )
        self.assertEqual(status, "OK")
        self.assertEqual([hit["index"] for hit in hits], [60, 120, 180])
        self.assertEqual(detector.call_args.kwargs["max_events"], c3.MAX_EVENTS)

    def test_hybrid_requires_focus_and_one_huber_same_sign_within_one_point(self):
        def fake_extract(detector, values, threshold=None):
            if detector == "FOCuS (reset-rearm)":
                return [
                    {"index": 10, "sign": 1},
                    {"index": 20, "sign": -1},
                ], "OK", {}
            if detector == "Post-Quiet Huber + MAD":
                return [{"index": 11, "sign": 1}], "OK", {}
            if detector == "Post-Quiet Huber + Bartlett LRV":
                return [{"index": 21, "sign": -1}], "OK", {}
            raise AssertionError(detector)

        thresholds = {
            "FOCuS (reset-rearm)": 100.0,
            "Post-Quiet Huber + MAD": 20.0,
            "Post-Quiet Huber + Bartlett LRV": 20.0,
        }
        with patch.object(c3, "extract_detector_hits", side_effect=fake_extract):
            hits, metadata = c3.hybrid_confirmation_hits(
                __import__("numpy").arange(40.0), thresholds
            )
        self.assertEqual([(row["index"], row["sign"]) for row in hits], [(11, 1), (21, -1)])
        self.assertEqual(metadata["status"], "OK")

    def test_available_hybrid_members_with_no_alert_are_not_abstentions(self):
        import numpy as np

        def fake_extract(detector, values, threshold=None):
            return [], "OK", {}

        thresholds = {
            "FOCuS (reset-rearm)": 100.0,
            "Post-Quiet Huber + MAD": 20.0,
            "Post-Quiet Huber + Bartlett LRV": None,
        }
        with patch.object(c3, "extract_detector_hits", side_effect=fake_extract):
            hits, metadata = c3.hybrid_confirmation_hits(
                np.zeros(80, dtype=float), thresholds
            )
        self.assertEqual(hits, [])
        self.assertEqual(metadata["status"], "OK")
        self.assertEqual(metadata["huber_members"], ["Post-Quiet Huber + MAD"])

    def test_wrong_direction_does_not_confirm_hybrid(self):
        def fake_extract(detector, values, threshold=None):
            if detector == "FOCuS (reset-rearm)":
                return [{"index": 10, "sign": 1}], "OK", {}
            if detector == "Post-Quiet Huber + MAD":
                return [{"index": 10, "sign": -1}], "OK", {}
            return [], "OK", {}

        thresholds = {
            "FOCuS (reset-rearm)": 100.0,
            "Post-Quiet Huber + MAD": 20.0,
            "Post-Quiet Huber + Bartlett LRV": None,
        }
        with patch.object(c3, "extract_detector_hits", side_effect=fake_extract):
            hits, metadata = c3.hybrid_confirmation_hits(
                __import__("numpy").arange(40.0), thresholds
            )
        self.assertEqual(hits, [])
        self.assertEqual(metadata["status"], "OK")

    def test_hybrid_must_pass_development_and_holdout_wilson_gates(self):
        import numpy as np

        dev = [np.asarray([1.0 if index < 50 else 0.0]) for index in range(1000)]
        holdout = [np.asarray([1.0 if index < 50 else 0.0]) for index in range(1000)]
        thresholds = {
            "FOCuS (reset-rearm)": 100.0,
            "Post-Quiet Huber + MAD": 20.0,
            "Post-Quiet Huber + Bartlett LRV": None,
        }

        def fake_hybrid(trace, _thresholds):
            return ([{"index": 0, "sign": 1}] if trace[0] else []), {"status": "OK"}

        with patch.object(c3, "hybrid_confirmation_hits", side_effect=fake_hybrid):
            result = c3.calibrate_ensemble(dev, holdout, thresholds)

        self.assertEqual(result["status"], "VALIDATED")
        self.assertLessEqual(
            result["development"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )
        self.assertLessEqual(
            result["holdout"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )
        self.assertFalse(result["holdout_retuning"])

    def test_hybrid_no_alert_paths_are_valid_zero_alarm_replicates(self):
        import numpy as np

        traces = [np.zeros(40, dtype=float) for _ in range(1000)]
        thresholds = {
            "FOCuS (reset-rearm)": 100.0,
            "Post-Quiet Huber + MAD": 20.0,
            "Post-Quiet Huber + Bartlett LRV": None,
        }
        with patch.object(
            c3, "hybrid_confirmation_hits",
            return_value=([], {"status": "OK"}),
        ):
            result = c3.calibrate_ensemble(traces, traces, thresholds)

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["development"]["valid_replicates"], 1000)
        self.assertEqual(result["development"]["alarm_traces"], 0)
        self.assertEqual(result["holdout"]["valid_replicates"], 1000)
        self.assertEqual(result["holdout"]["alarm_traces"], 0)
        self.assertLessEqual(
            result["development"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )
        self.assertLessEqual(
            result["holdout"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )

    def test_hybrid_abstains_when_development_wilson_gate_fails(self):
        import numpy as np

        dev = [np.asarray([1.0 if index < 100 else 0.0]) for index in range(1000)]
        holdout = [np.asarray([0.0]) for _ in range(1000)]
        thresholds = {
            "FOCuS (reset-rearm)": 100.0,
            "Post-Quiet Huber + MAD": 20.0,
            "Post-Quiet Huber + Bartlett LRV": None,
        }

        def fake_hybrid(trace, _thresholds):
            return ([{"index": 0, "sign": 1}] if trace[0] else []), {"status": "OK"}

        with patch.object(c3, "hybrid_confirmation_hits", side_effect=fake_hybrid):
            result = c3.calibrate_ensemble(dev, holdout, thresholds)

        self.assertEqual(result["status"], "ABSTAINED")
        self.assertEqual(result["raw_status"], "DEVELOPMENT_WILSON_GATE_FAILED")
        self.assertGreater(
            result["development"]["wilson_upper_95_one_sided"], c3.P0_TARGET
        )

    def test_one_alert_cannot_be_reused_for_two_overlapping_event_windows(self):
        rows = data_rows([
            date(2020, 4, 1),
            date(2020, 6, 1),
            date(2021, 8, 1),
        ])
        events = [
            event("EVENT_A", "2020-04-15", "EP_A"),
            event("EVENT_B", "2020-05-15", "EP_B"),
        ]
        hits = [{"index": 0, "sign": 1}]
        results, unmatched = c3.match_events_one_to_one(
            rows, events, hits, "TEST_DETECTOR"
        )
        matched = [row for row in results if row["hit_miss"] == "HIT"]
        missed = [row for row in results if row["hit_miss"] == "MISS"]
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(missed), 1)
        self.assertEqual(unmatched["matched_alarm_count"], 1)
        self.assertEqual(unmatched["unmatched_alarm_count"], 0)

    def test_matching_maximizes_event_coverage_before_minimizing_total_lag(self):
        rows = data_rows([
            date(2019, 5, 1),
            date(2020, 6, 1),
        ])
        events = [
            event("EVENT_A", "2020-01-01", "EP_A"),
            event("EVENT_B", "2020-12-01", "EP_B"),
        ]
        hits = [
            {"index": 0, "sign": 1},
            {"index": 1, "sign": 1},
        ]
        results, unmatched = c3.match_events_one_to_one(
            rows, events, hits, "TEST_DETECTOR"
        )
        self.assertEqual(
            {row["event_id"] for row in results if row["hit_miss"] == "HIT"},
            {"EVENT_A", "EVENT_B"},
        )
        assignments = {row["event_id"]: row["detection_index"] for row in results}
        self.assertEqual(assignments["EVENT_A"], 0)
        self.assertEqual(assignments["EVENT_B"], 1)
        self.assertEqual(unmatched["matched_event_count"], 2)
        self.assertEqual(unmatched["unmatched_alarm_count"], 0)

    def test_early_warning_is_a_match_with_negative_lag(self):
        rows = data_rows([
            date(2020, 2, 1),
            date(2020, 3, 1),
        ])
        results, _ = c3.match_events_one_to_one(
            rows, [event("COVID", "2020-03-11")],
            [{"index": 0, "sign": 1}], "TEST_DETECTOR",
        )
        self.assertEqual(results[0]["hit_miss"], "HIT")
        self.assertLess(results[0]["detection_lag_days"], 0)


if __name__ == "__main__":
    unittest.main()

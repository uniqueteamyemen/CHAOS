"""Regression tests for C3 v2 Wilson calibration and event assignment."""
import csv
import hashlib
import io
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
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

    def test_cadence_aware_focus_rearm_windows(self):
        self.assertEqual(c3.focus_rearm_points_for_frequency("Monthly"), 10)
        self.assertEqual(c3.focus_rearm_points_for_frequency("Weekly, ending Friday"), 20)
        self.assertEqual(c3.focus_rearm_points_for_frequency("Weekly, ending Saturday"), 20)
        with self.assertRaisesRegex(ValueError, "FOCUS_UNSUPPORTED_SERIES_FREQUENCY"):
            c3.focus_rearm_points_for_frequency("Daily")

    def test_hybrid_receives_only_holdout_eligible_member_thresholds(self):
        arms = {
            "FOCuS (reset-rearm)": {"status": "VALIDATED", "frozen_threshold": 225.0},
            "Post-Quiet Huber + MAD": {"status": "NOT_VALIDATED", "frozen_threshold": 80.0},
            "Post-Quiet Huber + Bartlett LRV": {"status": "VALIDATED", "frozen_threshold": 100.0},
        }
        self.assertEqual(
            c3.eligible_hybrid_member_thresholds(arms),
            {
                "FOCuS (reset-rearm)": 225.0,
                "Post-Quiet Huber + MAD": None,
                "Post-Quiet Huber + Bartlett LRV": 100.0,
            },
        )

    def test_payems_first_difference_uses_archived_predecessor_and_keeps_current_available_at(self):
        raw_text = (
            "observation_date,PAYEMS_19660808,PAYEMS_19660902,PAYEMS_19661010\n"
            "1966-07-01,100,100,100\n"
        )
        raw_bytes = raw_text.encode("utf-8")
        batch_path = "raw_vintage_batches/PAYEMS/batch_001.csv"
        manifest = {
            "raw_vintage_batches": [{
                "batch": 1,
                "requested_vintage_dates": ["1966-08-08", "1966-09-02", "1966-10-10"],
                "file": batch_path,
                "bytes": len(raw_bytes),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            }]
        }
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "source.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(batch_path, raw_bytes)
            by_series = {
                "PAYEMS": [
                    {
                        "series_id": "PAYEMS", "observation_date": "1966-08-01",
                        "available_at": "1966-09-02", "value": "110",
                        "value_float": 110.0,
                        "observation_date_obj": date(1966, 8, 1),
                        "available_at_obj": date(1966, 9, 2),
                        "frequency": "Monthly", "units": "Thousands of persons",
                        "value_semantics": "FIRST_ALFRED_VINTAGE_VALUE",
                    },
                    {
                        "series_id": "PAYEMS", "observation_date": "1966-09-01",
                        "available_at": "1966-10-10", "value": "107",
                        "value_float": 107.0,
                        "observation_date_obj": date(1966, 9, 1),
                        "available_at_obj": date(1966, 10, 10),
                        "frequency": "Monthly", "units": "Thousands of persons",
                        "value_semantics": "FIRST_ALFRED_VINTAGE_VALUE",
                    },
                ]
            }
            contract = {"series": [{
                "series_id": "PAYEMS",
                "frequency": "Monthly",
                "units": "Thousands of persons",
                "analysis_units": "Monthly change in thousands of persons",
                "series_transform": "first_difference",
            }]}
            transformed, audit = c3.apply_causal_series_transforms(
                archive_path, manifest, by_series, contract
            )

        rows = transformed["PAYEMS"]
        self.assertEqual([row["value_float"] for row in rows], [10.0, -3.0])
        self.assertEqual([row["available_at"] for row in rows], ["1966-09-02", "1966-10-10"])
        self.assertEqual(rows[0]["value_semantics"], "CAUSAL_FIRST_DIFFERENCE_OF_FIRST_ALFRED_RELEASES")
        self.assertEqual(audit["PAYEMS"]["predecessor"]["observation_date"], "1966-07-01")
        self.assertEqual(audit["PAYEMS"]["predecessor"]["available_at"], "1966-08-08")
        self.assertFalse(audit["PAYEMS"]["source_archive_mutated"])

    def test_markdown_comparison_includes_read_only_baselines(self):
        historical = [
            {"detector": "A_FAST", "hit_miss": "HIT", "episode_id": "EP_A", "detection_lag_days": 7},
            {"detector": "A_CONSENSUS", "hit_miss": "MISS", "episode_id": "EP_B", "detection_lag_days": None},
        ]
        summary = c3.summarize_detector_results({}, historical, {})
        report = {
            "status": "OPTIMIZATION_RUN",
            "run_id": "TEST",
            "evaluation_commit": "TEST",
            "cohort": {"event_count": 1, "episode_clusters": 1, "event_series_pairs": 1, "series_count": 0},
            "source_integrity": {"archive_sha256": "A", "tape_sha256": "B"},
            "calibration": {},
            "historical_results": [],
            "detector_summary": summary,
            "replay_command": "python replay.py",
            "report_json_sha256": "TEST",
        }
        markdown = c3.markdown_report(report)
        self.assertIn("| A_FAST | READ_ONLY |", markdown)
        self.assertIn("| A_CONSENSUS | READ_ONLY |", markdown)

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

    def test_hybrid_confirms_same_sign_within_eight_observations(self):
        def fake_extract(detector, values, threshold=None, rearm_quiet_points=c3.REARM_POINTS):
            if detector == "FOCuS (reset-rearm)":
                return [
                    {"index": 10, "sign": 1},
                    {"index": 20, "sign": -1},
                ], "OK", {}
            if detector == "Post-Quiet Huber + MAD":
                return [{"index": 18, "sign": 1}], "OK", {}
            if detector == "Post-Quiet Huber + Bartlett LRV":
                return [{"index": 28, "sign": -1}], "OK", {}
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
        self.assertEqual([(row["index"], row["sign"]) for row in hits], [(18, 1), (28, -1)])
        self.assertEqual(metadata["status"], "OK")
        self.assertEqual(c3.HYBRID_MAX_GAP, 8)

    def test_available_hybrid_members_with_no_alert_are_not_abstentions(self):
        import numpy as np

        def fake_extract(detector, values, threshold=None, rearm_quiet_points=c3.REARM_POINTS):
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
        def fake_extract(detector, values, threshold=None, rearm_quiet_points=c3.REARM_POINTS):
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

        def fake_hybrid(trace, _thresholds, rearm_quiet_points=c3.REARM_POINTS):
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

        def fake_hybrid(trace, _thresholds, rearm_quiet_points=c3.REARM_POINTS):
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

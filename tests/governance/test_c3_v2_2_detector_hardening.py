"""Regression tests for the isolated C3 v2.2 detector-hardening experiment."""
import unittest
from unittest.mock import patch

import numpy as np

from p1_4_validation import injection_runner
from p1_4_validation.c3 import run_c3_v2_equal_risk_evaluation as c3


class C3V22HardeningTests(unittest.TestCase):
    def test_rearm_wait_and_dispersion_windows_are_separate_and_causal(self):
        values = np.arange(120, dtype=float)
        calls = []

        def fake_focus_detector(series, *, quiet_points, threshold):
            calls.append((np.asarray(series, dtype=float).copy(), quiet_points))
            if len(calls) == 1:
                return {
                    "status": "OK",
                    "hits": [{
                        "detection_index": 40,
                        "estimated_change_index": 40,
                        "sign": 1,
                    }],
                }
            return {
                "status": "OK",
                "hits": [{
                    "detection_index": 41,
                    "estimated_change_index": 40,
                    "sign": -1,
                }],
            }

        with patch("p2_b_benchmark.p2c_engine.focus_detector", side_effect=fake_focus_detector):
            result = injection_runner.focus_reset_rearm(
                values,
                threshold=100.0,
                quiet_points=40,
                rearm_quiet_points=4,
                rearm_scale_points=40,
                max_events=2,
                min_series_length=41,
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], 40)
        self.assertEqual(calls[1][1], 40)
        # First alert is at 40. Four re-arm observations 41..44 set the
        # center; the 40-point causal history ends at 44 and supplies scale.
        rearm_reference = calls[1][0][:40]
        expected_center = float(np.median(values[41:45]))
        expected_scale_median = float(np.median(values[5:45]))
        shifted = values[5:45] - expected_scale_median + expected_center
        self.assertAlmostEqual(float(np.median(rearm_reference)), expected_center)
        self.assertAlmostEqual(float(np.median(np.abs(rearm_reference - np.median(rearm_reference)))),
                               float(np.median(np.abs(shifted - np.median(shifted)))))
        self.assertEqual(result["hits"][0]["index"], 40)
        self.assertEqual(result["hits"][1]["index"], 46)
        self.assertEqual(result["rearm_intervals"], [{
            "start_inclusive": 41,
            "end_exclusive": 45,
        }])
        self.assertEqual(result["rearm_scale_observations"], 40)
        self.assertEqual(
            result["rearm_scale_policy"],
            "TRAILING_CAUSAL_SCALE_WINDOW_TRANSLATED_TO_REARM_CENTER",
        )

    def test_legacy_rearm_path_remains_available_without_scale_window(self):
        values = np.arange(100, dtype=float)
        calls = []

        def fake_focus_detector(series, *, quiet_points, threshold):
            calls.append(quiet_points)
            if len(calls) == 1:
                return {"status": "OK", "hits": [{
                    "detection_index": 40, "estimated_change_index": 40, "sign": 1,
                }]}
            return {"status": "OK", "hits": []}

        with patch("p2_b_benchmark.p2c_engine.focus_detector", side_effect=fake_focus_detector):
            result = injection_runner.focus_reset_rearm(
                values, threshold=100.0, quiet_points=40,
                rearm_quiet_points=4, max_events=12, min_series_length=41,
            )

        self.assertEqual(calls, [40, 4])
        self.assertEqual(result["rearm_intervals"], [{
            "start_inclusive": 41,
            "end_exclusive": 45,
        }])
        self.assertIsNone(result["rearm_scale_observations"])

    def test_joint_hybrid_calibration_selects_pair_on_development_only(self):
        traces_dev = [np.zeros(50, dtype=float) for _ in range(1000)]
        traces_hold = [np.ones(50, dtype=float) for _ in range(1000)]

        def no_alarm(detector, values, threshold=None, rearm_quiet_points=c3.REARM_POINTS,
                     rearm_scale_points=None):
            return [], "OK", {}

        with patch.object(c3, "extract_detector_hits", side_effect=no_alarm):
            result = c3.calibrate_ensemble(
                traces_dev,
                traces_hold,
                rearm_quiet_points=4,
                rearm_scale_points=40,
                focus_grid=(10, 20),
                huber_grid=(5, 10),
            )

        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["joint_calibration"]["tested_threshold_pairs"], 8)
        self.assertEqual(result["joint_calibration"]["eligible_threshold_pairs"], 8)
        self.assertEqual(
            result["joint_calibration"]["selected_pair"],
            {
                "focus_threshold": 10.0,
                "huber_detector": "Post-Quiet Huber + MAD",
                "huber_threshold": 5.0,
            },
        )
        self.assertFalse(result["holdout_retuning"])
        self.assertEqual(result["holdout"]["alarm_traces"], 0)

    def test_hybrid_abstains_when_no_joint_pair_passes_development_risk_gate(self):
        traces = [np.zeros(50, dtype=float) for _ in range(1000)]

        def always_alarm(detector, values, threshold=None, rearm_quiet_points=c3.REARM_POINTS,
                         rearm_scale_points=None):
            return [{"index": 45, "sign": 1}], "OK", {}

        with patch.object(c3, "extract_detector_hits", side_effect=always_alarm):
            result = c3.calibrate_ensemble(
                traces, traces,
                rearm_quiet_points=4,
                rearm_scale_points=40,
                focus_grid=(10,),
                huber_grid=(5,),
            )

        self.assertEqual(result["status"], "ABSTAINED")
        self.assertEqual(
            result["raw_status"],
            "NO_JOINT_PAIR_MET_DEVELOPMENT_WILSON_GATE",
        )
        self.assertEqual(result["holdout"]["status"], "NOT_RUN")

    def test_payems_trailing_means_are_causal_and_keep_right_edge_available_at(self):
        rows = []
        for index, value in enumerate((3.0, 6.0, 9.0, 12.0, 15.0)):
            rows.append({
                "observation_date": f"2020-0{index + 1}-01",
                "available_at": f"2020-0{index + 1}-05",
                "value": str(value),
                "value_float": value,
                "series_transform": "first_difference",
                "units": "monthly change",
            })

        d3 = c3.causal_rolling_mean_rows(rows, 3)
        self.assertEqual([row["value_float"] for row in d3], [6.0, 9.0, 12.0])
        self.assertEqual(
            [row["available_at"] for row in d3],
            ["2020-03-05", "2020-04-05", "2020-05-05"],
        )
        self.assertEqual(d3[0]["source_window_start_observation"], "2020-01-01")
        self.assertEqual(d3[0]["source_window_end_observation"], "2020-03-01")
        self.assertEqual(
            d3[0]["value_semantics"],
            "CAUSAL_TRAILING_MEAN_OF_FIRST_ALFRED_DIFFERENCES",
        )

        changed_future = [dict(row) for row in rows]
        changed_future[-1]["value_float"] = 150.0
        changed_d3 = c3.causal_rolling_mean_rows(changed_future, 3)
        # A future revision cannot change any earlier trailing-window output.
        self.assertEqual(
            [row["value_float"] for row in changed_d3[:-1]],
            [row["value_float"] for row in d3[:-1]],
        )
        self.assertNotEqual(changed_d3[-1]["value_float"], d3[-1]["value_float"])

    def test_v2_2_seed_namespace_is_independent_from_v2_1(self):
        old = c3.deterministic_seed("TAPE", "UNRATE", 2, "holdout", 7)
        new = c3.deterministic_seed(
            "TAPE", "UNRATE", 2, "holdout", 7, namespace="CHAOS:C3_V2_2"
        )
        self.assertNotEqual(old, new)
        self.assertEqual(
            new,
            c3.deterministic_seed(
                "TAPE", "UNRATE", 2, "holdout", 7, namespace="CHAOS:C3_V2_2"
            ),
        )


if __name__ == "__main__":
    unittest.main()

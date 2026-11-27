"""Governance tests for the isolated C3 v2.3 causal slope-shift candidate."""
import unittest
import numpy as np

from p1_4_validation.c3.causal_local_slope_shift import CausalLocalSlopeShiftDetector


class CausalLocalSlopeShiftTests(unittest.TestCase):
    def setUp(self):
        self.detector = CausalLocalSlopeShiftDetector(
            window=12, confirm_points=3, rearm_quiet_points=6
        )

    @staticmethod
    def series(direction=1):
        idx = np.arange(180, dtype=float)
        noise = 0.08 * np.sin(idx * 0.71) + 0.03 * np.cos(idx * 0.19)
        y = 0.04 * idx + noise
        onset = 92
        y[onset:] += direction * 0.55 * (idx[onset:] - onset)
        return y, onset

    def test_detects_positive_slope_change(self):
        values, onset = self.series(1)
        report = self.detector.detect(values, threshold=3.0)
        self.assertEqual(report["status"], "OK")
        self.assertTrue(any(hit["sign"] == 1 and hit["index"] >= onset for hit in report["hits"]))

    def test_detects_negative_slope_change(self):
        values, onset = self.series(-1)
        report = self.detector.detect(values, threshold=3.0)
        self.assertEqual(report["status"], "OK")
        self.assertTrue(any(hit["sign"] == -1 and hit["index"] >= onset for hit in report["hits"]))

    def test_one_point_level_shift_does_not_masquerade_as_slope_shift(self):
        values = np.zeros(120, dtype=float)
        values[60:] += 5.0
        report = self.detector.detect(values, threshold=3.0)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["hits"], [])

    def test_quantized_baseline_uses_nonzero_deviation_fallback(self):
        baseline = np.array([0.0] * 7 + [0.1, -0.1, 0.0, 0.1, 0.0])
        scale, source = self.detector._scale_from_window(baseline)
        self.assertGreater(scale, 0.0)
        self.assertEqual(source, "LOCAL_QUANTIZATION_FALLBACK")

    def test_single_local_quantization_step_uses_baseline_only(self):
        baseline = np.array([0.0] * 11 + [0.1])
        scale, source = self.detector._scale_from_window(baseline)
        self.assertGreater(scale, 0.0)
        self.assertEqual(source, "LOCAL_QUANTIZATION_FALLBACK")

    def test_degenerate_local_baseline_does_not_borrow_expanding_history(self):
        detector = CausalLocalSlopeShiftDetector(
            window=6, initial_quiet_points=40, confirm_points=3
        )
        scale, source = detector._scale_from_window(np.zeros(6, dtype=float))
        self.assertEqual(scale, 0.0)
        self.assertEqual(source, "ZERO_LOCAL_DISPERSION")

    def test_constant_series_fails_closed_without_false_alarm(self):
        report = self.detector.detect(np.zeros(120), threshold=3.0)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["hits"], [])
        self.assertGreater(report["zero_scale_points"], 0)

    def test_prefix_replay_reproduces_each_hit(self):
        values, _ = self.series(1)
        full = self.detector.detect(values, threshold=3.0)
        self.assertTrue(full["hits"])
        for hit in full["hits"]:
            prefix = self.detector.detect(values[:hit["index"] + 1], threshold=3.0)
            self.assertTrue(any(
                row["index"] == hit["index"] and row["sign"] == hit["sign"]
                for row in prefix["hits"]
            ))

    def test_threshold_alarm_matches_threshold_independent_statistic(self):
        values, _ = self.series(1)
        scored = self.detector.score_trace(values)
        for threshold in (2.0, 3.0, 4.0, 5.0, 6.0):
            detected = self.detector.detect(values, threshold=threshold)
            self.assertEqual(
                bool(detected["hits"]),
                scored["max_confirmed_score"] is not None
                and scored["max_confirmed_score"] >= threshold,
            )

    def test_rejects_invalid_data_and_threshold(self):
        with self.assertRaises(ValueError):
            self.detector.detect([1.0, float("nan")], threshold=3.0)
        with self.assertRaises(ValueError):
            self.detector.detect(np.arange(50), threshold=0.0)

    def test_short_history_is_not_eligible(self):
        report = self.detector.detect(np.arange(20, dtype=float), threshold=3.0)
        self.assertEqual(report["status"], "NOT_ELIGIBLE")


if __name__ == "__main__":
    unittest.main()

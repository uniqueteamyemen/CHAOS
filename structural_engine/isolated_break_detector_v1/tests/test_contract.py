import unittest

from structural_engine.isolated_break_detector_v1.break_detector_v1 import (
    BreakDetectorV1,
    _pair_consensus_events,
)


class BreakDetectorContractTests(unittest.TestCase):
    def test_supported_modes_are_explicit(self):
        self.assertEqual(
            BreakDetectorV1.MODES, ("fast", "markov_cusum", "consensus")
        )

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported_mode"):
            BreakDetectorV1(mode="auto_router")

    def test_invalid_threshold_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "markov_threshold"):
            BreakDetectorV1(markov_threshold=0)

    def test_short_series_is_rejected_before_engine_execution(self):
        detector = BreakDetectorV1(mode="fast")
        with self.assertRaisesRegex(ValueError, "min_length=52"):
            detector.analyze([float(i) for i in range(51)])

    def test_nonfinite_values_are_rejected(self):
        detector = BreakDetectorV1(mode="fast")
        values = [float(i) for i in range(52)]
        values[20] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            detector.analyze(values)

    def test_consensus_is_one_to_one_and_forward_only(self):
        provisional = [
            {"detection_time": 10, "direction": 1},
            {"detection_time": 15, "direction": 1},
            {"detection_time": 30, "direction": -1},
        ]
        markov = [
            {"detection_time": 20, "direction": 1},
            {"detection_time": 25, "direction": -1},
            {"detection_time": 5, "direction": 1},
        ]
        confirmed, pending = _pair_consensus_events(provisional, markov)
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(len(pending), 2)
        self.assertEqual(confirmed[0]["confirmation_delay"], 10)
        self.assertEqual(confirmed[0]["status"], "CONFIRMED")
        self.assertEqual(pending[0]["status"], "PROVISIONAL")
        self.assertEqual([event["detection_time"] for event in pending], [15, 30])


if __name__ == "__main__":
    unittest.main()

import unittest
import numpy as np

from experiments.identity_lab.exp_sequential_break.engine import ImprovedSequentialBreakEngine
from experiments.identity_lab.exp_sequential_break.benchmark import generate_series, score_sequential


class ImprovedSequentialBreakEngineTests(unittest.TestCase):
    def test_deterministic_on_same_series(self):
        series = np.r_[np.zeros(40), np.ones(100) * 3.0]
        engine = ImprovedSequentialBreakEngine()
        self.assertEqual(engine.analyze(series), engine.analyze(series))

    def test_parameters_are_the_submitted_defaults(self):
        engine = ImprovedSequentialBreakEngine()
        self.assertEqual(engine.quiet_end, 40)
        self.assertEqual(engine.anomaly_z_thresh, 3.2)
        self.assertEqual(engine.confirm_window, 12)
        self.assertEqual(engine.break_percent_thresh, 76.0)

    def test_reports_retrospective_onset_not_instantaneous_detection(self):
        event = {"onset_time": 65, "direction": 1, "break_percentage": 90.0}
        result = {"structural_breaks": [event], "transient_anomalies": []}
        score = score_sequential(result, scenario="pos_shift_3s", confirm_window=12)
        self.assertEqual(score["estimated_onset"], 65)
        self.assertEqual(score["evidence_available_at"], 76)
        self.assertEqual(score["operational_delay"], 11)

    def test_rejects_short_and_nonfinite_series(self):
        engine = ImprovedSequentialBreakEngine()
        with self.assertRaisesRegex(ValueError, "series_too_short"):
            engine.analyze(np.ones(50))
        with self.assertRaisesRegex(ValueError, "series_contains_nonfinite"):
            engine.analyze(np.r_[np.ones(40), np.nan, np.ones(99)])

    def test_generator_reproducible_and_scenario_effects_present(self):
        a = generate_series(np.random.default_rng(1234), "gauss_ar1")
        b = generate_series(np.random.default_rng(1234), "gauss_ar1")
        self.assertTrue(np.array_equal(a, b))
        jump = generate_series(np.random.default_rng(1234), "gauss_ar1_var_jump")
        self.assertTrue(np.array_equal(a[:65], jump[:65]))
        self.assertFalse(np.array_equal(a[65:], jump[65:]))
        pos = generate_series(np.random.default_rng(1234), "pos_shift_3s")
        self.assertTrue(np.allclose(pos[65:] - a[65:], 3.0))

    def test_null_scoring_counts_sequence_false_positive(self):
        result = {"structural_breaks": [{"onset_time": 50, "direction": 1}],
                  "transient_anomalies": []}
        score = score_sequential(result, scenario="gauss_ar1", confirm_window=12)
        self.assertTrue(score["false_alarm"])
        self.assertEqual(score["false_events"], 1)


if __name__ == "__main__":
    unittest.main()

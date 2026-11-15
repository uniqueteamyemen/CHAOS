import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break.b3_engine import (
    SequentialBreakEngineB3,
)
from experiments.identity_lab.exp_sequential_break.benchmark_b3 import (
    generate_series,
    wilson_interval,
)


class SequentialBreakEngineB3Tests(unittest.TestCase):
    def test_rejects_invalid_shapes_and_nonfinite_data(self):
        engine = SequentialBreakEngineB3()
        with self.assertRaisesRegex(ValueError, "one_dimensional"):
            engine.analyze(np.ones((2, 100)))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            engine.analyze(np.r_[np.ones(40), np.nan, np.ones(100)])

    def test_lag_one_rho_uses_adjacent_values_not_self_correlation(self):
        series = generate_series(
            np.random.default_rng(731),
            dist="gauss",
            rho=0.5,
            var_jump=False,
            shift_sigma=0.0,
        )
        result = SequentialBreakEngineB3().analyze(series)
        rho = result["diagnostics"]["rho_estimate"]
        self.assertGreaterEqual(rho, 0.0)
        self.assertLess(rho, 0.88)
        self.assertNotEqual(rho, 0.88)

    def test_detector_is_causal_to_detection_time(self):
        rng = np.random.default_rng(811)
        series = generate_series(
            rng,
            dist="gauss",
            rho=0.3,
            var_jump=False,
            shift_sigma=3.0,
        )
        engine = SequentialBreakEngineB3(break_percent_thresh=70.0)
        full = engine.analyze(series)["structural_breaks"]
        if not full:
            self.skipTest("fixed test realization did not trigger")
        cutoff = full[0]["detection_time"]
        prefix = engine.analyze(series[: cutoff + 1])["structural_breaks"]
        full_prefix = [b for b in full if b["detection_time"] <= cutoff]
        self.assertEqual(prefix, full_prefix)

    def test_onset_estimator_uses_historical_split(self):
        rng = np.random.default_rng(913)
        series = np.r_[
            rng.normal(0.0, 0.1, 65),
            rng.normal(3.0, 0.1, 50),
        ]
        estimated = SequentialBreakEngineB3()._estimate_onset(
            series, detection_t=90, lookback=35
        )
        self.assertLessEqual(abs(estimated - 65), 2)

    def test_generator_is_reproducible_and_applies_level_shift(self):
        a = generate_series(
            np.random.default_rng(1234),
            dist="t3",
            rho=0.7,
            var_jump=False,
            shift_sigma=0.0,
        )
        b = generate_series(
            np.random.default_rng(1234),
            dist="t3",
            rho=0.7,
            var_jump=False,
            shift_sigma=0.0,
        )
        shifted = generate_series(
            np.random.default_rng(1234),
            dist="t3",
            rho=0.7,
            var_jump=False,
            shift_sigma=2.5,
        )
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.array_equal(a[:65], shifted[:65]))
        self.assertTrue(np.allclose(shifted[65:] - a[65:], 2.5))

    def test_wilson_interval_contains_observed_rate(self):
        lo, hi = wilson_interval(25, 500)
        self.assertLessEqual(lo, 0.05)
        self.assertGreaterEqual(hi, 0.05)


if __name__ == "__main__":
    unittest.main()

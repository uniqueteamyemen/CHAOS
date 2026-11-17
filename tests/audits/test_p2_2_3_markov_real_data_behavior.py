import unittest
import numpy as np
from scripts.audits.p2_2_3_markov_real_data_behavior import (
    rolling_mad_volatility_normalize, summarize_records,
    run_bootstrap_jobs,
)


class MarkovRealDataBehaviorTests(unittest.TestCase):
    def test_rolling_mad_is_finite_and_preserves_length(self):
        values = np.random.default_rng(11).normal(0.0, 0.03, 160)
        result = rolling_mad_volatility_normalize(values)
        self.assertEqual(result.shape, values.shape)
        self.assertTrue(np.all(np.isfinite(result)))

    def test_scale_only_transform_preserves_level_shift(self):
        values = np.random.default_rng(12).normal(0.0, 0.02, 120)
        shifted = values.copy()
        shifted[80:] += 0.25
        base = rolling_mad_volatility_normalize(values)
        changed = rolling_mad_volatility_normalize(shifted)
        self.assertGreater(float(np.median(changed[90:])), float(np.median(base[90:])))

    def test_future_values_do_not_change_prior_normalized_values(self):
        values = np.random.default_rng(13).normal(0.0, 0.02, 140)
        changed = values.copy()
        changed[100:] *= 20.0
        np.testing.assert_allclose(
            rolling_mad_volatility_normalize(values)[:100],
            rolling_mad_volatility_normalize(changed)[:100],
            rtol=0.0, atol=0.0,
        )

    def test_rejects_short_or_nonfinite_input(self):
        with self.assertRaises(ValueError):
            rolling_mad_volatility_normalize(np.ones(20))
        values = np.ones(80)
        values[50] = np.nan
        with self.assertRaises(ValueError):
            rolling_mad_volatility_normalize(values)

    def test_summary_separates_cohort_length_and_transform(self):
        rows = [
            {"category":"energy","sample_length":100,"input_variant":"raw",
             "has_any_alarm":True,"alarm_count":1,"cusum_peak":8.8,
             "cusum_updates":49,"rho_cusum_used":0.2},
            {"category":"energy","sample_length":100,"input_variant":"raw",
             "has_any_alarm":False,"alarm_count":0,"cusum_peak":2.0,
             "cusum_updates":49,"rho_cusum_used":0.2},
            {"category":"energy","sample_length":100,"input_variant":"rolling_mad_scale_only",
             "has_any_alarm":False,"alarm_count":0,"cusum_peak":1.0,
             "cusum_updates":49,"rho_cusum_used":0.1},
            {"category":"metals","sample_length":539,"input_variant":"raw",
             "has_any_alarm":True,"alarm_count":2,"cusum_peak":10.0,
             "cusum_updates":488,"rho_cusum_used":0.3},
        ]
        summary = summarize_records(rows)
        self.assertEqual(summary["energy|n=100|raw"]["conditional_null_alarm_probability"], 0.5)
        self.assertEqual(summary["energy|n=100|rolling_mad_scale_only"]["conditional_null_alarm_probability"], 0.0)
        self.assertIn("metals|n=539|raw", summary)


    def test_vectorized_rolling_mad_is_bitwise_identical_to_reference_loop(self):
        def reference(values, quiet_end=40, window=40):
            values = np.asarray(values, dtype=float)
            quiet_scale = 1.4826 * float(np.median(np.abs(values[:quiet_end] - np.median(values[:quiet_end]))))
            floor = max(abs(quiet_scale) * 1e-4, 1e-12)
            out = np.empty_like(values)
            for index in range(values.size):
                history = values[:quiet_end] if index < quiet_end else values[max(0, index-window):index]
                scale = 1.4826 * float(np.median(np.abs(history - np.median(history))))
                out[index] = values[index] / max(scale, floor)
            return out

        rng = np.random.default_rng(20261117)
        for length, quiet_end, window in ((40, 40, 40), (100, 40, 40),
                                          (539, 40, 40), (150, 48, 40),
                                          (150, 30, 40)):
            values = rng.normal(0.0, 0.05, length)
            expected = reference(values, quiet_end, window)
            actual = rolling_mad_volatility_normalize(
                values, quiet_end=quiet_end, window=window
            )
            np.testing.assert_array_equal(actual, expected)

    def test_series_seeded_parallel_jobs_are_identical_to_serial_jobs(self):
        rng = np.random.default_rng(20261118)
        payloads = [
            ("fixture:energy_a", "energy", rng.normal(0.0, 0.02, 120).tolist(), 2),
            ("fixture:metal_b", "metals", rng.normal(0.0, 0.03, 140).tolist(), 2),
        ]
        sequential = run_bootstrap_jobs(payloads, workers=1)
        parallel = run_bootstrap_jobs(payloads, workers=2)
        self.assertEqual(sequential, parallel)


if __name__ == "__main__":
    unittest.main()

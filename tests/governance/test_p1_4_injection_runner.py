from __future__ import annotations

import unittest
from unittest.mock import patch
import numpy as np

from p1_4_validation.injection_runner import (
    NotEligibleError, break_is_unmonitored, build_injected_case,
    calibrate_threshold, deterministic_seed, evaluate_online_hits,
    fit_ar_candidate, focus_reset_rearm, generate_ar_null_trace, injection_grid,
    match_r_fpop_boundary, select_ar_model, wilson_upper,
)
from p2_b_benchmark.p2c_engine import (
    bocpd_detector, focus_detector, post_quiet_huber_detector,
)


def ar_fixture(n=180, seed=814):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    noise = rng.normal(size=n)
    for i in range(1, n):
        x[i] = 0.35 + 0.45 * x[i - 1] + noise[i]
    return x


class P14InjectionRunnerTests(unittest.TestCase):
    def test_seed_is_repeatable_and_phase_separated(self):
        seed = deterministic_seed("1.1.2", "gem:TEST:X", 0.5, 1, "development", 3)
        self.assertEqual(seed, deterministic_seed("1.1.2", "gem:TEST:X", 0.5, 1, "development", 3))
        self.assertNotEqual(seed, deterministic_seed("1.1.2", "gem:TEST:X", 0.5, 1, "holdout", 3))

    def test_ar_fit_and_stability_gate(self):
        x = ar_fixture()
        fitted = fit_ar_candidate(x[:120], 1)
        self.assertEqual(fitted["status"], "OK")
        selected = select_ar_model(x[:120])
        self.assertEqual(selected["status"], "OK")
        self.assertIn(selected["order"], (1, 2, 3))
        self.assertGreater(selected["residual_sigma"], 0)

    def test_null_trace_is_deterministic(self):
        x = ar_fixture()
        model = select_ar_model(x[:120])
        a = generate_ar_null_trace(model, x[:120], 180, 123456)
        b = generate_ar_null_trace(model, x[:120], 180, 123456)
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.all(np.isfinite(a)))
        with self.assertRaises(NotEligibleError):
            generate_ar_null_trace({"status": "NOT_ELIGIBLE"}, x, 180, 1)

    def test_injection_grid_retains_all_18_planned_cases(self):
        rows = injection_grid(ar_fixture(90))
        self.assertEqual(len(rows), 18)
        self.assertEqual(sum(row["status"] == "NOT_ELIGIBLE" for row in rows), 6)
        case = build_injected_case(ar_fixture(90), magnitude_sigma=1.0,
                                   position_fraction=0.7, direction=-1)
        self.assertEqual(case["status"], "OK")
        self.assertEqual(case["direction"], -1)

    def test_wilson_and_calibration_fail_closed(self):
        self.assertGreater(wilson_upper(0, 1000), 0)
        scores = [0.0] * 1000
        result = calibrate_threshold(scores, [1.0, 2.0])
        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["threshold"], 1.0)
        short = calibrate_threshold(scores[:900], [1.0])
        self.assertEqual(short["status"], "INCONCLUSIVE")

    def test_optional_statistic_trace_and_default_detector_outputs(self):
        x = ar_fixture(220)
        x[130:] += 3.0 * (1.4826 * np.median(np.abs(x[:40] - np.median(x[:40]))))
        focus_default = focus_detector(x, threshold=45.0)
        focus_trace = focus_detector(x, threshold=float("inf"), return_score_trace=True)
        self.assertTrue(focus_default["hits"])
        self.assertTrue(focus_trace["statistic_trace"])
        self.assertEqual(focus_trace["hits"], [])
        huber_default = post_quiet_huber_detector(x, scale_mode="mad", threshold=12.0)
        huber_trace = post_quiet_huber_detector(x, scale_mode="mad",
            threshold=float("inf"), return_score_trace=True)
        self.assertTrue(huber_default["hits"])
        self.assertTrue(huber_trace["statistic_trace"])
        self.assertEqual(huber_trace["hits"], [])

    def test_bocpd_exports_full_normalized_posterior_per_prefix(self):
        x = ar_fixture(90)
        result = bocpd_detector(x, export_posterior=True)
        trace = result["posterior_pmf_trace"]
        self.assertEqual(len(trace), x.size - 40)
        self.assertEqual(len(result["posterior_feature_trace"]), x.size - 40)
        self.assertTrue(result["metadata"]["posterior_pmf_trace_sha256"])
        for row in trace:
            self.assertAlmostEqual(sum(row["probabilities"]), 1.0, places=10)
            self.assertEqual(len(row["run_lengths"]), len(row["probabilities"]))

    def test_r_fpop_matching_is_one_to_one_and_extras_are_false(self):
        row = match_r_fpop_boundary([
            {"estimated_change_index": 20}, {"estimated_change_index": 51},
            {"estimated_change_index": 54}], true_break_index=52, series_length=100)
        self.assertEqual(row["matched_breakpoint_index"], 1)
        self.assertEqual(row["false_breakpoint_count"], 2)
        self.assertAlmostEqual(row["boundary_precision"], 1/3)

    def test_focus_reset_rearm_restarts_on_a_fresh_40_observation_window(self):
        values = np.arange(150, dtype=float)
        calls = []

        def fake_focus_detector(segment, *, quiet_points, threshold):
            calls.append(np.asarray(segment, dtype=float).copy())
            self.assertEqual(quiet_points, 40)
            self.assertEqual(threshold, 7.0)
            if len(calls) == 1:
                return {"status": "OK", "hits": [{
                    "detection_index": 50, "estimated_change_index": 47,
                    "sign": 1, "score": 8.0,
                }]}
            if len(calls) == 2:
                return {"status": "OK", "hits": [{
                    "detection_index": 45, "estimated_change_index": 42,
                    "sign": -1, "score": 9.0,
                }]}
            self.fail("unexpected third detector invocation")

        with patch("p2_b_benchmark.p2c_engine.focus_detector", side_effect=fake_focus_detector):
            result = focus_reset_rearm(values, threshold=7.0, quiet_points=40)

        self.assertEqual([row["detection_index"] for row in result["hits"]], [50, 136])
        self.assertEqual([row["estimated_change_index"] for row in result["hits"]], [47, 133])
        self.assertEqual(result["rearm_intervals"], [
            {"start_inclusive": 51, "end_exclusive": 91},
            {"start_inclusive": 137, "end_exclusive": 150},
        ])
        self.assertEqual(len(calls), 2)
        # The next detector invocation receives only the suffix after the
        # first hit; its first 40 observations are the new calibration window.
        self.assertTrue(np.array_equal(calls[1], values[91:]))
        self.assertTrue(np.array_equal(calls[1][:40], values[91:131]))

    def test_rearm_window_is_a_missed_exposure_not_a_removed_case(self):
        intervals = [{"start_inclusive": 101, "end_exclusive": 141}]
        self.assertTrue(break_is_unmonitored(120, intervals))
        self.assertFalse(break_is_unmonitored(141, intervals))
        out = evaluate_online_hits([], true_break_index=120, true_direction=1,
                                   rearm_intervals=intervals)
        self.assertEqual(out["status"], "UNMONITORED_REARM")
        self.assertTrue(out["missed"])
        self.assertTrue(out["uncovered_by_rearm"])

    def test_short_prebreak_is_not_eligible(self):
        self.assertEqual(select_ar_model(np.arange(30.0))["status"], "NOT_ELIGIBLE")


if __name__ == "__main__":
    unittest.main()

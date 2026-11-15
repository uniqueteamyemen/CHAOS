"""Unit tests for the isolated P parallel-detector and event-fusion experiment."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.engine import DOMAINS
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import (
    _variant_detection_hits,
    exact_mcnemar_pvalue,
)
from experiments.identity_lab.exp_p_engine.parallel_fusion import (
    fuse_events,
    run_candidates,
    validate_series,
    _two_sided_cusum,
)


def rows_from_residuals(values):
    balance = 2000.0
    c = DOMAINS["stock"]
    rows = []
    for month, residual in enumerate(values, start=1):
        expected = balance + 10.0 - 10.0 - 1.0
        closing = expected - residual
        rows.append({
            c["opening"]: balance, c["inflow"]: 10.0, c["outflow"]: 10.0,
            c["other"]: 1.0, c["closing"]: closing, "month": month,
        })
        balance = closing
    return rows


def make_rows(sign=0, magnitude=0.0, onset=65, noise=1.5, seed=7, months=150):
    rng = random.Random(seed)
    balance = 2000.0
    c = DOMAINS["stock"]
    rows = []
    for month in range(1, months + 1):
        expected = balance + 10.0 - 10.0 - 1.0
        shift = sign * magnitude if month >= onset else 0.0
        residual = shift + rng.gauss(0.0, noise)
        closing = expected - residual
        rows.append({
            c["opening"]: balance, c["inflow"]: 10.0, c["outflow"]: 10.0,
            c["other"]: 1.0, c["closing"]: closing, "month": month,
        })
        balance = closing
    return rows


class ParallelFusionTests(unittest.TestCase):
    def test_cusum_detects_positive_and_negative_breaks(self):
        positive = run_candidates(
            "stock", make_rows(sign=1, magnitude=9.0, seed=11),
            quiet_range=(1, 40),
        )
        negative = run_candidates(
            "stock", make_rows(sign=-1, magnitude=9.0, seed=11),
            quiet_range=(1, 40),
        )
        self.assertTrue(any(h["detector"] == "cusum_positive" for h in positive["C"]["raw_hits"]))
        self.assertTrue(any(h["detector"] == "cusum_negative" for h in negative["C"]["raw_hits"]))

    def test_A_is_the_production_engine_output(self):
        rows = make_rows(sign=1, magnitude=9.0)
        result = run_candidates("stock", rows, quiet_range=(1, 40))
        from experiments.identity_lab.exp_p_engine.engine import run as production_run
        expected = production_run("stock", rows, quiet_range=(1, 40))
        self.assertEqual(result["A"], expected)

    def test_snapshot_is_stable_for_identical_input_and_config(self):
        rows = make_rows(sign=1, magnitude=9.0)
        first = run_candidates("stock", rows, quiet_range=(1, 40))
        second = run_candidates("stock", rows, quiet_range=(1, 40))
        self.assertEqual(first["snapshot"]["snapshot_id"], second["snapshot"]["snapshot_id"])
        self.assertEqual(first["snapshot"]["input_sha256"], second["snapshot"]["input_sha256"])

    def test_candidates_preserve_directional_cusum_tracks(self):
        result = run_candidates(
            "stock", make_rows(sign=-1, magnitude=9.0, seed=21),
            quiet_range=(1, 40),
        )
        negative_hits = [h for h in result["C"]["raw_hits"]
                         if h["detector"] == "cusum_negative" and h["index"] >= 65]
        self.assertTrue(negative_hits, "negative CUSUM must detect a post-onset negative shift")

    def test_series_order_and_duplicates_fail_closed(self):
        validate_series([{"month": 1, "residual": 0.1}, {"month": 2, "residual": 0.2}])
        with self.assertRaisesRegex(ValueError, "series_timestamp_order_invalid"):
            validate_series([{"month": 2, "residual": 0.1}, {"month": 1, "residual": 0.2}])
        with self.assertRaisesRegex(ValueError, "series_duplicate_timestamp"):
            validate_series([{"month": 1, "residual": 0.1}, {"month": 1, "residual": 0.2}])

    def test_same_direction_without_calm_is_one_continuous_event(self):
        series = [{"month": i, "residual": 5.0} for i in range(1, 100)]
        hits = [
            {"index": 60, "time": 61, "detector": "sign_run", "priority": 1, "sign": 1},
            {"index": 90, "time": 91, "detector": "cusum_positive", "priority": 2, "sign": 1},
        ]
        events, _ = fuse_events(
            series, hits, bias=0.0, calm_sigmas=[1.0] * len(series),
            sigma_quiet=1.0, entity="E", calm_periods=6, cooldown=26,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence_count"], 2)

    def test_same_direction_after_confirmed_calm_opens_new_event(self):
        series = [{"month": i, "residual": 0.0} for i in range(1, 100)]
        hits = [
            {"index": 60, "time": 61, "detector": "cusum_positive", "priority": 2, "sign": 1},
            {"index": 80, "time": 81, "detector": "cusum_positive", "priority": 2, "sign": 1},
        ]
        events, _ = fuse_events(
            series, hits, bias=0.0, calm_sigmas=[1.0] * len(series),
            sigma_quiet=1.0, entity="E", calm_periods=6, cooldown=26,
        )
        self.assertEqual(len(events), 2)

    def test_direction_reversal_is_a_new_event_not_cooldown_suppression(self):
        series = [{"month": i, "residual": 0.0} for i in range(1, 100)]
        hits = [
            {"index": 60, "time": 61, "detector": "cusum_positive", "priority": 2, "sign": 1},
            {"index": 65, "time": 66, "detector": "cusum_negative", "priority": 2, "sign": -1},
        ]
        events, suppressed = fuse_events(
            series, hits, bias=0.0, calm_sigmas=[1.0] * len(series),
            sigma_quiet=1.0, entity="E", calm_periods=6, cooldown=26,
        )
        self.assertEqual(len(events), 2)
        self.assertEqual([event["sign"] for event in events], [1, -1])
        self.assertEqual(suppressed, [])

    def test_hold_policy_preserves_accumulator_through_variance_transition(self):
        series = [{"month": i + 1, "residual": value}
                  for i, value in enumerate([2.0, 2.0, 2.0, 2.0, 8.0])]
        sigmas = [1.0] * len(series)
        transitions = [False, True, True, True, False]
        hits = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="hold_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=8.5, transition_damping=0.35,
        )
        self.assertEqual([hit["time"] for hit in hits], [5])

    def test_bounded_cusum_scale_is_an_explicit_experimental_arm(self):
        series = [{"month": i + 1, "residual": 10.0} for i in range(10)]
        sigmas = [10.0] * len(series)
        transitions = [False] * len(series)
        unbounded = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="hold_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=8.5, transition_damping=0.35,
        )
        bounded = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="bounded_damped",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=8.5, transition_damping=0.35,
        )
        self.assertEqual(unbounded, [])
        self.assertTrue(bounded)

    def test_D_changes_only_P1_high_noise_handling_and_keeps_CUSUM_identical(self):
        rng = random.Random(991)
        residuals = [rng.gauss(0.0, 1.5) for _ in range(40)]
        # A variance-regime shift with alternating three-point directional runs:
        # C's capped 3σ/3-run P1 fires; D's 13-run high-noise P1 must remain quiet.
        for block in range(0, 110, 3):
            sign = 1 if (block // 3) % 2 == 0 else -1
            residuals.extend([sign * 20.0] * 3)
        rows = rows_from_residuals(residuals)
        result = run_candidates("stock", rows, quiet_range=(1, 40))
        c_p1 = [h for h in result["C"]["raw_hits"] if h["detector"] == "sign_run"]
        d_p1 = [h for h in result["D"]["raw_hits"] if h["detector"] == "sign_run"]
        c_cusum = [h for h in result["C"]["raw_hits"] if h["detector"].startswith("cusum_")]
        d_cusum = [h for h in result["D"]["raw_hits"] if h["detector"].startswith("cusum_")]
        self.assertGreater(len(c_p1), 0)
        self.assertEqual(d_p1, [])
        self.assertEqual(c_cusum, d_cusum)
        self.assertEqual(result["D"]["diagnostics"]["p1_mode"], "production_adaptive_13_run")
        self.assertGreater(result["D"]["diagnostics"]["p1_adaptive_high_noise_periods"], 0)

    def test_reset_policy_clears_both_accumulators_during_variance_transition(self):
        series = [
            {"month": 1, "residual": 2.0},
            {"month": 2, "residual": 2.0},
            {"month": 3, "residual": 2.0},
            {"month": 4, "residual": 2.0},
            {"month": 5, "residual": 2.0},
            {"month": 6, "residual": 8.0},
        ]
        sigmas = [1.0] * len(series)
        transitions = [False, False, False, True, True, False]
        held = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="hold_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=8.5, transition_damping=0.35,
        )
        reset = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="reset_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=8.5, transition_damping=0.35,
        )
        self.assertTrue(held)
        self.assertEqual(reset, [])

    def test_higher_reset_policy_thresholds_do_not_fire_earlier_on_same_stream(self):
        series = [{"month": i + 1, "residual": 3.0} for i in range(40)]
        sigmas = [1.0] * len(series)
        transitions = [False] * len(series)
        hits_85 = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="reset_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=8.5, transition_damping=0.35,
        )
        hits_105 = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="reset_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=10.5, transition_damping=0.35,
        )
        hits_125 = _two_sided_cusum(
            series, 0.0, sigmas, transitions, policy="reset_unbounded",
            sigma_cap=2.0, k_sigma=0.5, h_sigma=12.5, transition_damping=0.35,
        )
        self.assertLess(hits_85[0]["index"], hits_105[0]["index"])
        self.assertLess(hits_105[0]["index"], hits_125[0]["index"])

    def test_exact_mcnemar_pvalue_is_symmetric_and_detects_directional_difference(self):
        self.assertEqual(exact_mcnemar_pvalue(0, 0), 1.0)
        self.assertEqual(exact_mcnemar_pvalue(8, 0), exact_mcnemar_pvalue(0, 8))
        self.assertLess(exact_mcnemar_pvalue(8, 0), 0.01)
        self.assertEqual(exact_mcnemar_pvalue(5, 5), 1.0)

    def test_detection_scoring_uses_post_onset_evidence_not_event_start(self):
        residuals = [0.0] * 100
        result = {
            "A": {
                "alerts": [
                    {"time": 70, "detector": "sign_run"},
                    {"time": 72, "detector": "cusum"},
                ]
            },
            "H": {
                "events": [{
                    "time": 41,
                    "evidence": [
                        {"index": 40, "time": 41, "sign": -1, "detector": "sign_run"},
                        {"index": 69, "time": 70, "sign": -1, "detector": "cusum_negative"},
                    ],
                }]
            },
        }
        candidate_hits = _variant_detection_hits(result, "H", residuals)
        self.assertEqual(candidate_hits[-1]["time"], 70)
        self.assertEqual(candidate_hits[-1]["sign"], -1)
        production_hits = _variant_detection_hits(result, "A", residuals)
        self.assertEqual([hit["time"] for hit in production_hits], [70, 72])

    def test_J_and_K_fill_hold_threshold_grid_with_same_adaptive_P1(self):
        rows = make_rows(sign=-1, magnitude=9.0, seed=55)
        result = run_candidates("stock", rows, quiet_range=(1, 40))
        g_p1 = [
            hit for hit in result["G"]["raw_hits"]
            if hit["detector"] == "sign_run"
        ]
        for variant in ("H", "J", "K", "I"):
            p1 = [
                hit for hit in result[variant]["raw_hits"]
                if hit["detector"] == "sign_run"
            ]
            self.assertEqual(p1, g_p1)
            self.assertEqual(
                result[variant]["diagnostics"]["sigma_cusum_policy"],
                "unbounded_hold",
            )
            self.assertEqual(
                result[variant]["diagnostics"]["p1_mode"],
                "production_adaptive_13_run",
            )

    def test_H_and_I_keep_production_adaptive_P1_with_hold_policy(self):
        rows = make_rows(sign=-1, magnitude=9.0, seed=41)
        result = run_candidates("stock", rows, quiet_range=(1, 40))
        g_p1 = [
            hit for hit in result["G"]["raw_hits"]
            if hit["detector"] == "sign_run"
        ]
        for variant in ("H", "I"):
            p1 = [
                hit for hit in result[variant]["raw_hits"]
                if hit["detector"] == "sign_run"
            ]
            self.assertEqual(p1, g_p1)
            self.assertEqual(
                result[variant]["diagnostics"]["sigma_cusum_policy"],
                "unbounded_hold",
            )
            self.assertEqual(
                result[variant]["diagnostics"]["p1_mode"],
                "production_adaptive_13_run",
            )

    def test_same_event_cooldown_marks_but_retains_evidence(self):
        series = [{"month": i, "residual": 5.0} for i in range(1, 100)]
        hits = [
            {"index": 60, "time": 61, "detector": "cusum_positive", "priority": 2, "sign": 1},
            {"index": 70, "time": 71, "detector": "cusum_positive", "priority": 2, "sign": 1},
        ]
        events, suppressed = fuse_events(
            series, hits, bias=0.0, calm_sigmas=[1.0] * len(series),
            sigma_quiet=1.0, entity="E", calm_periods=6, cooldown=26,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence_count"], 2)
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(len(events[0]["evidence"]), 2)
        self.assertIn("notification_suppressed", events[0]["evidence"][1])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the isolated P parallel-detector and event-fusion experiment."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.engine import DOMAINS
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

    def test_E_resets_both_cusum_accumulators_at_transition_and_resumes_after(self):
        series = [
            {"month": month, "residual": residual}
            for month, residual in enumerate((2.0, 2.0, 0.0, 1.5, 1.5, 1.5), start=1)
        ]
        sigmas = [1.0] * len(series)
        transitions = [False, False, True, False, False, False]
        common = dict(
            series=series, bias=0.0, sigmas=sigmas, transitions=transitions,
            sigma_cap=1.0, k_sigma=0.5, h_sigma=4.0, transition_damping=0.35,
        )
        held = _two_sided_cusum(policy="hold_unbounded", **common)
        damped = _two_sided_cusum(policy="bounded_damped", **common)
        reset = _two_sided_cusum(policy="suspend_reset", **common)
        self.assertTrue(any(hit["time"] == 5 for hit in held))
        self.assertTrue(any(hit["time"] == 5 for hit in damped))
        self.assertEqual(reset, [])

    def test_E_is_same_as_C_for_P1(self):
        residuals = [value for _ in range(10) for value in (0.2, -0.2, 0.1, -0.1)] + [15.0, -15.0] * 30 + [2.0] * 40
        rows = rows_from_residuals(residuals)
        result = run_candidates("stock", rows, quiet_range=(1, 40))
        c_p1 = [hit for hit in result["C"]["raw_hits"] if hit["detector"] == "sign_run"]
        e_p1 = [hit for hit in result["E"]["raw_hits"] if hit["detector"] == "sign_run"]
        self.assertEqual(c_p1, e_p1)
        self.assertEqual(result["E"]["diagnostics"]["policy"], "suspend_reset")

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

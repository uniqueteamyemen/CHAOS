"""Unit tests for the isolated P parallel-detector and event-fusion experiment."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.parallel_fusion import (
    fuse_events,
    run_candidates,
    validate_series,
)


def make_rows(sign=0, magnitude=0.0, onset=65, noise=1.5, seed=7, months=150):
    rng = random.Random(seed)
    balance = 2000.0
    rows = []
    for month in range(1, months + 1):
        expected = balance + 10.0 - 10.0 - 1.0
        shift = sign * magnitude if month >= onset else 0.0
        residual = shift + rng.gauss(0.0, noise)
        closing = expected - residual
        rows.append({
            "opening": balance, "inflow": 10.0, "outflow": 10.0,
            "other": 1.0, "closing": closing, "month": month,
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
        self.assertGreater(result["C"]["diagnostics"]["cusum_negative_hits"], 0)
        self.assertEqual(result["C"]["diagnostics"]["cusum_positive_hits"], 0)

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

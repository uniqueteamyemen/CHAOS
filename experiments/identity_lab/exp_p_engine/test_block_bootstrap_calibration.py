"""Tests for dependence-preserving calibration across scale estimators."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.block_bootstrap_calibration import (
    contiguous_ready_segments,
    cusum_alarm_count,
    moving_block_resample,
    prepare_panel_from_series,
    sign_run_alarm_count,
)


def make_series(entity_id: str, *, seed: int, count: int = 40) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        rows.append({
            "entity_id": entity_id,
            "metric_id": "indicator",
            "event_time": str(1980 + index),
            "value": 15.0 + 0.25 * index + rng.gauss(0.0, 0.5),
            "observation_status": "observed",
            "unit": "index-points",
        })
    return rows


class BlockBootstrapCalibrationTests(unittest.TestCase):
    def test_moving_block_resample_is_reproducible_and_preserves_length(self):
        values = [float(index) for index in range(31)]
        first = moving_block_resample(
            values, block_length=4, rng=random.Random(2026)
        )
        second = moving_block_resample(
            values, block_length=4, rng=random.Random(2026)
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(values))
        self.assertTrue(all(0 <= value < len(values) for value in first))

    def test_panel_builder_emits_segments_for_both_supported_estimators(self):
        panel = {
            "entity-A": make_series("entity-A", seed=1),
            "entity-B": make_series("entity-B", seed=2),
        }
        first = prepare_panel_from_series(
            panel, scale_estimator="first_difference_mad"
        )
        second = prepare_panel_from_series(
            panel, scale_estimator="second_difference_mad"
        )
        self.assertEqual(set(first), {"entity-A", "entity-B"})
        self.assertEqual(set(second), {"entity-A", "entity-B"})
        for result in (first, second):
            for segments in result.values():
                self.assertTrue(segments)
                self.assertTrue(all(len(segment) >= 8 for segment in segments))

    def test_panel_builder_rejects_unknown_scale_estimator(self):
        panel = {"entity-A": make_series("entity-A", seed=3)}
        with self.assertRaisesRegex(ValueError, "scale_estimator_unsupported"):
            prepare_panel_from_series(panel, scale_estimator="rolling_guess")

    def test_segments_break_at_unresolved_or_missing_periods(self):
        rows = [
            {"event_time": str(2000 + index), "status": "ready", "z_score": float(index)}
            for index in range(5)
        ]
        rows.extend([
            {"event_time": "2005", "status": "gap_unresolved", "z_score": None},
            {"event_time": "2006", "status": "ready", "z_score": 1.0},
            {"event_time": "2007", "status": "ready", "z_score": 1.2},
        ])
        segments = contiguous_ready_segments(rows)
        self.assertEqual([len(segment) for segment in segments], [5, 2])

    def test_detector_alarm_functions_separate_directions_and_runs(self):
        self.assertEqual(cusum_alarm_count([2.0, 2.0, 2.0, -2.0], k=0.5, h=3.0), 1)
        self.assertEqual(sign_run_alarm_count([3.5, 3.5, 0.0, -3.5, -3.5], threshold=3.0, run_length=2), 2)


if __name__ == "__main__":
    unittest.main()

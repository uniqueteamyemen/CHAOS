import math
import unittest

from discovery_engine.behavioral_discovery_v1 import (
    BehavioralDiscoveryError,
    analyze_series,
    build_shared_year_patterns,
)


def make_series(values, years=None, entity="AAA", metric="wdi__GDP"):
    years = years or list(range(2000, 2000 + len(values)))
    return {
        "source_namespace": "world_bank_wdi",
        "dataset_id": "wdi_test",
        "domain": "economic",
        "entity_id": entity,
        "entity_name": entity,
        "metric_id": metric,
        "metric_name": metric,
        "unit": "%",
        "series_id": "series:test",
        "years": years,
        "values": [float(x) for x in values],
        "identities": [
            {
                "logical_record_id": f"logical-{i}",
                "canonical_record_id": f"canonical-{i}",
                "available_at": None,
            }
            for i in range(len(values))
        ],
    }


CONTRACT = {
    "minimum_segment_observations": 5,
    "point_reference_observations_each_side": 4,
    "point_anomaly_threshold": 3.5,
    "level_shift_effect_threshold": 1.5,
    "slope_shift_effect_threshold": 1.5,
    "shared_year_minimum_entities": 5,
    "shared_year_direction_concordance": 0.7,
}


class BehavioralDiscoveryTests(unittest.TestCase):
    def test_linear_trend_does_not_create_residual_level_shift(self):
        profile, candidates = analyze_series(
            make_series([2 * i + 5 for i in range(25)]), CONTRACT
        )
        self.assertAlmostEqual(profile["global_theil_sen_slope_per_year"], 2.0)
        level = [x for x in candidates if x["candidate_type"] == "level_shift"]
        point = [x for x in candidates if x["candidate_type"] == "isolated_point_anomaly"]
        self.assertEqual(level, [])
        self.assertEqual(point, [])

    def test_persistent_level_step_is_recorded_as_unvalidated_candidate(self):
        values = [float(i) for i in range(25)]
        for i in range(12, 25):
            values[i] += 20.0
        _, candidates = analyze_series(make_series(values), CONTRACT)
        level = [x for x in candidates if x["candidate_type"] == "level_shift"]
        self.assertEqual(len(level), 1)
        self.assertEqual(level[0]["candidate_status"], "DISCOVERY_CANDIDATE_UNVALIDATED")
        self.assertFalse(level[0]["causal_claim"])
        self.assertIsNone(level[0]["inferential_p_value"])
        self.assertIn(level[0]["candidate_year"], range(2005, 2021))

    def test_slope_change_is_separate_from_level_shift(self):
        values = [float(i) for i in range(25)]
        for i in range(12, 25):
            values[i] = 11.0 + 3.0 * (i - 11)
        _, candidates = analyze_series(make_series(values), CONTRACT)
        slopes = [x for x in candidates if x["candidate_type"] == "slope_change"]
        self.assertEqual(len(slopes), 1)
        self.assertEqual(slopes[0]["direction"], "SLOPE_INCREASE")
        self.assertEqual(slopes[0]["pre_change_trend_direction"], "INCREASING")
        self.assertEqual(slopes[0]["post_change_trend_direction"], "INCREASING")

    def test_isolated_spike_is_detected_without_calling_it_a_break(self):
        values = [float(i) for i in range(25)]
        values[12] += 40.0
        _, candidates = analyze_series(make_series(values), CONTRACT)
        points = [x for x in candidates if x["candidate_type"] == "isolated_point_anomaly"]
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["candidate_type"], "isolated_point_anomaly")
        self.assertEqual(points[0]["candidate_year"], 2012)

    def test_constant_series_produces_profile_but_no_candidates(self):
        profile, candidates = analyze_series(make_series([7.0] * 25), CONTRACT)
        self.assertTrue(profile["constant_series"])
        self.assertEqual(candidates, [])

    def test_step_with_zero_within_segment_variability_is_not_lost(self):
        values = [0.0] * 12 + [5.0] * 13
        _, candidates = analyze_series(make_series(values), CONTRACT)
        level = [x for x in candidates if x["candidate_type"] == "level_shift"]
        self.assertEqual(len(level), 1)
        self.assertIn(
            level[0]["effect_size_kind"],
            {
                "ZERO_WITHIN_SEGMENT_VARIABILITY",
                "ROBUST_STANDARDIZED_MEDIAN_SHIFT",
            },
        )
        self.assertTrue(
            level[0]["effect_size"] is None or level[0]["effect_size"] >= 1.5
        )

    def test_incomplete_or_nonfinite_series_fails_closed(self):
        invalid = make_series([1.0, 2.0, 3.0])
        with self.assertRaises(BehavioralDiscoveryError):
            analyze_series(invalid, CONTRACT)
        invalid = make_series([float(i) for i in range(25)])
        invalid["values"][10] = math.nan
        with self.assertRaisesRegex(BehavioralDiscoveryError, "non_finite"):
            analyze_series(invalid, CONTRACT)

    def test_shared_metric_year_pattern_requires_support_and_direction(self):
        candidates = []
        for i in range(6):
            candidates.append({
                "metric_id": "wdi__GDP", "candidate_type": "level_shift",
                "candidate_year": 2020, "entity_id": f"E{i}",
                "direction": "SLOPE_DECREASE",
                "pre_change_trend_direction": "INCREASING",
                "post_change_trend_direction": "INCREASING",
                "causal_claim": False,
            })
        candidates.append({
            "metric_id": "wdi__GDP", "candidate_type": "level_shift",
            "candidate_year": 2020, "entity_id": "E6",
            "direction": "DOWN", "causal_claim": False,
        })
        patterns = build_shared_year_patterns(candidates, CONTRACT)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["entity_support"], 7)
        self.assertAlmostEqual(patterns[0]["direction_concordance"], 6 / 7)
        self.assertEqual(patterns[0]["pre_change_trend_direction"], "INCREASING")
        self.assertEqual(patterns[0]["post_change_trend_direction"], "INCREASING")

    def test_shared_slope_patterns_do_not_mix_growth_slowdown_with_decline_acceleration(self):
        candidates = []
        for i in range(8):
            candidates.append({
                "metric_id": "wdi__SP.POP.TOTL",
                "candidate_type": "slope_change",
                "candidate_year": 2019,
                "entity_id": f"G{i}",
                "direction": "SLOPE_DECREASE",
                "pre_change_trend_direction": "INCREASING",
                "post_change_trend_direction": "INCREASING",
                "support_position": "INTERIOR",
            })
        for i in range(2):
            candidates.append({
                "metric_id": "wdi__SP.POP.TOTL",
                "candidate_type": "slope_change",
                "candidate_year": 2019,
                "entity_id": f"D{i}",
                "direction": "SLOPE_DECREASE",
                "pre_change_trend_direction": "DECREASING",
                "post_change_trend_direction": "DECREASING",
                "support_position": "INTERIOR",
            })
        patterns = build_shared_year_patterns(candidates, CONTRACT)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["entity_support"], 8)
        self.assertEqual(patterns[0]["pre_change_trend_direction"], "INCREASING")
        self.assertEqual(patterns[0]["post_change_trend_direction"], "INCREASING")


if __name__ == "__main__":
    unittest.main()

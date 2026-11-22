import random
import unittest

from discovery_engine.cross_series_relationship_discovery_v1 import (
    _first_differences,
    _metric_change_mode,
    discover_cross_series_relationships,
    scan_variance_shifts,
)


def cumulative_series(changes, start=100.0):
    values = {2000: float(start)}
    current = float(start)
    for index, change in enumerate(changes, 1):
        current += float(change)
        values[2000 + index] = current
    return values


class CrossSeriesRelationshipDiscoveryTests(unittest.TestCase):
    def _lagged_panel(self):
        rng = random.Random(20261122)
        panel = {"metric::source": {}, "metric::target": {}}
        for entity_index in range(16):
            source = [rng.uniform(-2, 2) for _ in range(20)]
            target = [rng.uniform(-1, 1)]
            target.extend(1.8 * source[index - 1] + rng.uniform(-0.12, 0.12) for index in range(1, 20))
            panel["metric::source"][f"E{entity_index:02d}"] = cumulative_series(source)
            panel["metric::target"][f"E{entity_index:02d}"] = cumulative_series(target)
        return panel

    def test_positive_lag_means_source_change_precedes_target_change(self):
        rows = discover_cross_series_relationships(
            self._lagged_panel(), minimum_entities=12, minimum_pairs_per_entity=8,
            maximum_lag_years=1, early_window=(2001, 2010), late_window=(2011, 2020),
            temporal_minimum_entities=10, temporal_minimum_pairs_per_entity=6,
        )
        row = next(item for item in rows
                   if item["source_metric"] == "metric::source"
                   and item["target_metric"] == "metric::target"
                   and item["lag_years"] == 1
                   and item["analysis_mode"] == "ENTITY_DEMEANED")
        self.assertTrue(row["candidate_screen_passed"])
        self.assertGreater(row["median_entity_correlation"], 0.8)
        self.assertEqual(row["relation_kind"], "SOURCE_LEADS_TARGET")
        self.assertFalse(row["causal_claim"])
        self.assertIsNone(row["inferential_p_value"])

    def test_independent_series_do_not_pass_descriptive_screen(self):
        rng = random.Random(11)
        panel = {"metric::a": {}, "metric::b": {}}
        for entity_index in range(18):
            panel["metric::a"][f"E{entity_index}"] = cumulative_series(
                [rng.uniform(-2, 2) for _ in range(20)]
            )
            panel["metric::b"][f"E{entity_index}"] = cumulative_series(
                [rng.uniform(-2, 2) for _ in range(20)]
            )
        rows = discover_cross_series_relationships(
            panel, minimum_entities=12, minimum_pairs_per_entity=8, maximum_lag_years=1,
            early_window=(2001, 2010), late_window=(2011, 2020),
            temporal_minimum_entities=10, temporal_minimum_pairs_per_entity=6,
        )
        self.assertFalse(any(item["candidate_screen_passed"] for item in rows))

    def test_missing_year_is_not_filled_or_bridged(self):
        differences = _first_differences(
            {"E1": {2000: 1.0, 2001: 3.0, 2003: 9.0, 2004: 10.0}}
        )
        self.assertEqual(differences["E1"], {2001: 2.0, 2004: 1.0})

    def test_positive_level_series_uses_log_difference(self):
        differences = _first_differences(
            {"E1": {2000: 100.0, 2001: 110.0, 2002: 121.0}},
            change_mode="LOG_DIFFERENCE",
        )
        self.assertAlmostEqual(differences["E1"][2001], differences["E1"][2002])
        self.assertAlmostEqual(differences["E1"][2001], 0.0953101798)

    def test_nonpositive_log_level_entity_is_excluded_without_fallback(self):
        differences, excluded = _first_differences(
            {"E1": {2000: 0.0, 2001: 2.0}, "E2": {2000: 3.0, 2001: 6.0}},
            change_mode="LOG_DIFFERENCE",
            return_excluded=True,
        )
        self.assertEqual(differences["E1"], {})
        self.assertEqual(excluded, ["E1"])
        self.assertAlmostEqual(differences["E2"][2001], 0.6931471806)

    def test_percentage_rate_metadata_uses_absolute_difference(self):
        mode = _metric_change_mode({
            "source_metric_id": "NY.GDP.MKTP.KD.ZG",
            "unit": "%",
        })
        self.assertEqual(mode, "ABSOLUTE_DIFFERENCE")

    def test_index_metadata_uses_log_difference(self):
        mode = _metric_change_mode({
            "source_metric_id": "PCPI",
            "unit": "Index",
        })
        self.assertEqual(mode, "LOG_DIFFERENCE")


class VarianceShiftDiscoveryTests(unittest.TestCase):
    def test_sustained_variance_expansion_is_detected(self):
        changes = [(-0.1 if index % 2 else 0.1) for index in range(14)]
        changes += [(-3.0 if index % 2 else 3.0) for index in range(14)]
        row = scan_variance_shifts(
            {"metric::x": {"AAA": cumulative_series(changes)}},
            minimum_segment_changes=8, minimum_variance_change_factor=3.0,
        )[0]
        self.assertTrue(row["candidate"])
        self.assertEqual(row["direction"], "VOLATILITY_EXPANSION")
        self.assertGreaterEqual(row["variance_change_factor"], 2.0)

    def test_sustained_variance_contraction_is_detected(self):
        changes = [(-3.0 if index % 2 else 3.0) for index in range(14)]
        changes += [(-0.1 if index % 2 else 0.1) for index in range(14)]
        row = scan_variance_shifts(
            {"metric::x": {"AAA": cumulative_series(changes)}},
            minimum_segment_changes=8, minimum_variance_change_factor=3.0,
        )[0]
        self.assertTrue(row["candidate"])
        self.assertEqual(row["direction"], "VOLATILITY_CONTRACTION")

    def test_stable_volatility_does_not_pass(self):
        pattern = [0.2, -0.2, 1.0, -1.0, 0.5, -0.5]
        changes = [pattern[index % len(pattern)] for index in range(30)]
        row = scan_variance_shifts(
            {"metric::x": {"AAA": cumulative_series(changes)}},
            minimum_segment_changes=8, minimum_variance_change_factor=3.0,
        )[0]
        self.assertFalse(row["candidate"])

    def test_transition_from_zero_robust_variance_is_retained(self):
        changes = [0.0] * 12 + [(-2.0 if index % 2 else 2.0) for index in range(14)]
        row = scan_variance_shifts(
            {"metric::x": {"AAA": cumulative_series(changes)}},
            minimum_segment_changes=8, minimum_variance_change_factor=3.0,
        )[0]
        self.assertTrue(row["candidate"])
        self.assertEqual(row["variance_ratio_kind"], "EMERGED_FROM_ZERO_BASELINE")
        self.assertIsNone(row["variance_ratio_post_over_pre"])

    def test_single_extreme_change_does_not_create_volatility_regime(self):
        changes = [0.2, -0.2, 0.5, -0.5] * 7
        changes[14] = 8.0
        row = scan_variance_shifts(
            {"metric::x": {"AAA": cumulative_series(changes)}},
            minimum_segment_changes=8, minimum_variance_change_factor=10.0,
        )[0]
        self.assertFalse(row["candidate"])

    def test_moderate_variance_increase_does_not_pass_conservative_gate(self):
        changes = [(-0.2 if index % 2 else 0.2) for index in range(14)]
        changes += [(-0.4 if index % 2 else 0.4) for index in range(14)]
        row = scan_variance_shifts(
            {"metric::x": {"AAA": cumulative_series(changes)}},
            minimum_segment_changes=8, minimum_variance_change_factor=10.0,
        )[0]
        self.assertFalse(row["candidate"])


if __name__ == "__main__":
    unittest.main()

"""Tests for the domain-neutral observation and detection layer."""
import json
import math
import random
import statistics
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from experiments.identity_lab.exp_p_engine.domain_neutral import (
    benjamini_hochberg,
    build_univariate_residuals,
    cohort_peer_residuals,
    detect_missingness_spikes,
    false_alerts_per_1000_entity_year,
    first_difference_mad_scale,
    first_evidence_at_or_after,
    missing_periods,
    normalize_observations,
    run_candidate_detectors,
)


def observations(values, *, start_year=2000, unit="years", entity="E", metric="m"):
    rows = []
    for index, value in enumerate(values):
        if unit == "years":
            event_time = str(start_year + index)
        else:
            event_time = (datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)).isoformat()
        rows.append({
            "entity_id": entity,
            "metric_id": metric,
            "event_time": event_time,
            "value": float(value),
            "observation_status": "observed",
        })
    return rows


def ar1_series(count, *, rho, stationary_sigma, seed=17):
    rng = random.Random(seed)
    innovation_sigma = stationary_sigma * math.sqrt(1.0 - rho * rho)
    value = rng.gauss(0.0, stationary_sigma)
    values = []
    for _ in range(count):
        value = rho * value + rng.gauss(0.0, innovation_sigma)
        values.append(value)
    return values


class ObservationContractTests(unittest.TestCase):
    def test_embedded_observation_schema_keeps_five_required_fields(self):
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "residual_event_v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        definition = schema["definitions"]["observation"]
        self.assertEqual(
            definition["required"],
            ["entity_id", "metric_id", "event_time", "value", "observation_status"],
        )
        self.assertIn("identity_version", schema["required"])
        self.assertIn("attributed_term", schema["required"])

    def test_five_required_fields_are_enough(self):
        result = normalize_observations(
            [{"staff": "e1", "metric": "tickets", "period": "2024", "count": "12"}],
            {
                "entity_id": "staff",
                "metric_id": "metric",
                "event_time": "period",
                "value": "count",
            },
        )
        self.assertEqual(result["accepted_rows"], 1)
        row = result["observations"][0]
        self.assertEqual(row["entity_id"], "e1")
        self.assertEqual(row["metric_id"], "tickets")
        self.assertEqual(row["event_time"], "2024")
        self.assertEqual(row["value"], 12.0)
        self.assertEqual(row["observation_status"], "observed")
        self.assertNotIn("unit", row)

    def test_blank_value_is_missing_not_zero(self):
        result = normalize_observations(
            [{"id": "e1", "metric": "m", "year": "2024", "value": ""}],
            {"entity_id": "id", "metric_id": "metric", "event_time": "year", "value": "value"},
        )
        row = result["observations"][0]
        self.assertIsNone(row["value"])
        self.assertEqual(row["observation_status"], "missing")

    def test_explicit_missing_status_does_not_forward_fill(self):
        result = normalize_observations(
            [
                {"id": "e1", "metric": "m", "year": "2020", "value": "10", "status": "observed"},
                {"id": "e1", "metric": "m", "year": "2021", "value": "", "status": "missing"},
                {"id": "e1", "metric": "m", "year": "2022", "value": "13", "status": "observed"},
            ],
            {
                "entity_id": "id", "metric_id": "metric", "event_time": "year",
                "value": "value", "observation_status": "status",
            },
        )
        self.assertEqual([x["value"] for x in result["observations"]], [10.0, None, 13.0])
        report = missing_periods(result["observations"], ["2020", "2021", "2022", "2023"])
        self.assertEqual(report["explicit_missing_or_invalid"], 1)
        self.assertEqual(report["absent_records"], 1)


    def test_missingness_spike_is_reported_as_data_quality_not_behavior(self):
        expected = [f"2024-{month:02d}" for month in range(1, 16)]
        rows = [
            {
                "entity_id": "branch-1",
                "metric_id": "daily_output",
                "event_time": expected[index],
                "value": float(100 + index),
                "observation_status": "observed",
            }
            for index in range(10)
        ]
        result = detect_missingness_spikes(
            rows, expected, window_size=5,
            minimum_recent_rate=0.8, minimum_increase=0.5,
        )
        self.assertEqual(result["signal_count"], 1)
        self.assertEqual(result["signals"][0]["signal_type"], "data_quality_missingness_spike")
        self.assertIn("not an entity behavior", result["signals"][0]["interpretation"])

    def test_pending_and_not_applicable_are_not_counted_as_missing(self):
        expected = [f"2024-{month:02d}" for month in range(1, 11)]
        rows = [
            {
                "entity_id": "e1", "metric_id": "m", "event_time": expected[index],
                "value": None, "observation_status": "not_applicable",
            }
            for index in range(5, 10)
        ]
        result = detect_missingness_spikes(
            rows, expected, window_size=5,
            minimum_recent_rate=0.5, minimum_increase=0.3,
        )
        self.assertEqual(result["signal_count"], 0)

    def test_duplicate_entity_metric_time_is_rejected(self):
        rows = [
            {"id": "e1", "metric": "m", "year": "2024", "value": "1"},
            {"id": "e1", "metric": "m", "year": "2024-01-01", "value": "2"},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate_observation_key"):
            normalize_observations(
                rows, {"entity_id": "id", "metric_id": "metric", "event_time": "year", "value": "value"}
            )


class ScaleEstimatorTests(unittest.TestCase):
    def test_iid_first_difference_scale_is_consistent(self):
        rng = random.Random(2026)
        values = [rng.gauss(0.0, 2.0) for _ in range(5000)]
        rows = observations(values, unit="days")
        result = first_difference_mad_scale(rows, time_unit="days")
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["value"], 1.75)
        self.assertLess(result["value"], 2.25)

    def test_ar1_correlation_adjustment_recovers_level_scale(self):
        rho, target_sigma = 0.65, 2.5
        values = ar1_series(5000, rho=rho, stationary_sigma=target_sigma)[500:]
        rows = observations(values, unit="days")
        result = first_difference_mad_scale(rows, time_unit="days", estimate_rho=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rho_source"], "estimated_from_unit_gaps")
        self.assertAlmostEqual(result["rho"], rho, delta=0.06)
        self.assertAlmostEqual(result["value"], target_sigma, delta=0.22)

    def test_irregular_gaps_are_adjusted_only_with_supported_ar1(self):
        rho, target_sigma = 0.55, 1.8
        values = ar1_series(4000, rho=rho, stationary_sigma=target_sigma, seed=29)
        rng = random.Random(30)
        keep = [i for i in range(len(values)) if rng.random() > 0.08]
        rows = []
        for i in keep:
            rows.append({
                "entity_id": "E", "metric_id": "m",
                "event_time": (datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)).isoformat(),
                "value": values[i], "observation_status": "observed",
            })
        result = first_difference_mad_scale(rows, time_unit="days", estimate_rho=True)
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["n_gap_adjusted"], 0)
        self.assertAlmostEqual(result["value"], target_sigma, delta=0.25)

    def test_short_25_point_series_with_gaps_is_supported(self):
        values = ar1_series(25, rho=0.45, stationary_sigma=1.3, seed=41)
        rows = observations(values, unit="days")
        rows = [row for index, row in enumerate(rows) if index not in {4, 10, 18}]
        result = first_difference_mad_scale(rows, time_unit="days", estimate_rho=True)
        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["n_differences"], 8)
        self.assertGreater(result["n_gap_adjusted"], 0)

    def test_sparse_nonunit_gaps_without_rho_do_not_invent_scale(self):
        rows = [
            {"entity_id": "E", "metric_id": "m", "event_time": str(2000 + 2 * i),
             "value": float(i * i), "observation_status": "observed"}
            for i in range(10)
        ]
        result = first_difference_mad_scale(rows, time_unit="years", estimate_rho=False)
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "insufficient_supported_differences")




class BaselineTests(unittest.TestCase):
    def test_theil_sen_baseline_tracks_a_smooth_trend_better_than_rolling_median(self):
        rng = random.Random(92)
        rows = observations(
            [5.0 * index + rng.gauss(0.0, 0.4) for index in range(36)],
            start_year=1980,
        )
        median_rows = build_univariate_residuals(
            rows, baseline_window=12, min_history=8, time_unit="years",
            baseline_method="rolling_median",
        )
        trend_rows = build_univariate_residuals(
            rows, baseline_window=12, min_history=8, time_unit="years",
            baseline_method="rolling_theil_sen",
        )
        median_scores = [abs(row["z_score"]) for row in median_rows if row["z_score"] is not None]
        trend_scores = [abs(row["z_score"]) for row in trend_rows if row["z_score"] is not None]
        self.assertGreater(len(median_scores), 10)
        self.assertGreater(len(trend_scores), 10)
        self.assertLess(statistics.median(trend_scores), statistics.median(median_scores) * 0.25)
        self.assertTrue(all(row["baseline_method"] == "prequential_rolling_theil_sen" for row in trend_rows))

class DetectorAndFleetTests(unittest.TestCase):
    def test_both_cusum_directions_are_retained(self):
        residuals = []
        for index, z in enumerate([0, 0, 3, 3, 3, 0, -3, -3, -3]):
            residuals.append({
                "event_time": str(2020 + index), "status": "ready", "z_score": float(z)
            })
        result = run_candidate_detectors(
            residuals, cusum_k=0.5, cusum_h=4.0, p1_threshold=2.0, p1_run_length=3
        )
        directions = {hit["direction"] for hit in result["raw_hits"]["cusum"]}
        self.assertEqual(directions, {"positive", "negative"})
        self.assertEqual(result["event_fusion"], "not_applied")
        self.assertEqual(result["alert_suppression"], "not_applied")

    def test_pre_onset_event_start_does_not_hide_post_onset_evidence(self):
        hits = [
            {"event_time": "2020-01-01", "detector": "cusum"},
            {"event_time": "2020-03-01", "detector": "cusum"},
        ]
        evidence = first_evidence_at_or_after(hits, "2020-02-01")
        self.assertEqual(evidence["event_time"], "2020-03-01")

    def test_temporal_fleet_rate_uses_entity_year_exposure(self):
        self.assertAlmostEqual(false_alerts_per_1000_entity_year(10, 2000), 5.0)
        with self.assertRaises(ValueError):
            false_alerts_per_1000_entity_year(1, 0)

    def test_bh_requires_valid_pvalues_and_controls_cross_section(self):
        rejected = benjamini_hochberg([0.001, 0.01, 0.03, 0.2], q=0.05)
        self.assertEqual(rejected, [True, True, True, False])
        with self.assertRaises(ValueError):
            benjamini_hochberg([0.01, float("nan")])


class CohortTests(unittest.TestCase):
    def test_peer_baseline_excludes_the_subject_and_requires_explicit_cohort(self):
        rows = []
        values = [100, 110, 120, 130, 140, 200]
        for index, value in enumerate(values):
            rows.append({
                "entity_id": "staff-" + str(index),
                "metric_id": "completed_cases",
                "event_time": "2025-01",
                "value": value,
                "observation_status": "observed",
                "cohort_id": "branch-A:role-X:season-1",
            })
        output = cohort_peer_residuals(rows, min_peers=5)
        outlier = next(row for row in output if row["entity_id"] == "staff-5")
        self.assertEqual(outlier["peer_expected"], 120.0)
        self.assertEqual(outlier["peer_residual"], 80.0)
        self.assertEqual(outlier["peer_count"], 5)


    def test_exposure_adjusted_peer_comparison_uses_rate_not_raw_count(self):
        values = [10, 20, 30, 40, 50, 90]
        exposures = [1, 2, 3, 4, 5, 3]
        rows = []
        for index, (value, exposure) in enumerate(zip(values, exposures)):
            rows.append({
                "entity_id": f"staff-{index}",
                "metric_id": "completed_cases",
                "event_time": "2025-01",
                "value": value,
                "exposure": exposure,
                "observation_status": "observed",
                "cohort_id": "branch-role-season",
            })
        result = cohort_peer_residuals(rows, min_peers=5, use_exposure=True)
        outlier = next(row for row in result if row["entity_id"] == "staff-5")
        self.assertEqual(outlier["value_basis"], "value_per_exposure")
        self.assertEqual(outlier["peer_expected"], 10.0)
        self.assertEqual(outlier["peer_residual"], 20.0)

    def test_missing_cohort_does_not_trigger_guessed_peer_group(self):
        rows = [{
            "entity_id": "e1", "metric_id": "m", "event_time": "2025-01",
            "value": 10, "observation_status": "observed",
        }]
        self.assertEqual(cohort_peer_residuals(rows), [])


if __name__ == "__main__":
    unittest.main()

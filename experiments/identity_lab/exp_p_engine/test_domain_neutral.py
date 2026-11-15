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
    build_partial_relation_residuals,
    build_univariate_residuals,
    cohort_peer_residuals,
    detect_missingness_spikes,
    false_alerts_per_1000_entity_year,
    first_difference_mad_scale,
    first_evidence_at_or_after,
    missing_periods,
    normalize_observations,
    run_candidate_detectors,
    validate_residual_contract,
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


def residual_row(entity, metric, time, z, *, baseline="test-baseline", status="ready"):
    return {
        "entity_id": entity,
        "metric_id": metric,
        "event_time": time,
        "observed_value": float(z),
        "expected_value": 0.0,
        "residual": float(z),
        "scale": 1.0,
        "z_score": float(z) if status == "ready" else None,
        "status": status,
        "baseline_id": baseline,
        "baseline_method": "unit-test",
        "support_count": 12,
    }


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
        self.assertIn("exposure", definition["properties"])
        self.assertIn("exposure_unit", definition["properties"])
        residual_definition = schema["definitions"]["residual"]
        self.assertEqual(
            residual_definition["required"],
            [
                "entity_id", "metric_id", "event_time", "observed_value",
                "expected_value", "residual", "status", "baseline_id",
                "baseline_method", "support_count",
            ],
        )
        residual_definition = schema["definitions"]["residual"]
        self.assertEqual(
            residual_definition["required"],
            [
                "entity_id", "metric_id", "event_time", "observed_value",
                "expected_value", "residual", "status", "baseline_id",
                "baseline_method", "support_count",
            ],
        )

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


    def test_optional_exposure_metadata_is_parsed_without_becoming_required(self):
        result = normalize_observations(
            [{"id": "e1", "metric": "output", "year": "2024", "value": "25",
              "hours": "10", "hours_unit": "hours"}],
            {
                "entity_id": "id", "metric_id": "metric", "event_time": "year",
                "value": "value", "exposure": "hours", "exposure_unit": "hours_unit",
            },
        )
        row = result["observations"][0]
        self.assertEqual(row["exposure"], 10.0)
        self.assertEqual(row["exposure_unit"], "hours")

    def test_invalid_exposure_is_marked_without_dropping_the_observation(self):
        result = normalize_observations(
            [{"id": "e1", "metric": "output", "year": "2024", "value": "25",
              "hours": "unknown"}],
            {
                "entity_id": "id", "metric_id": "metric", "event_time": "year",
                "value": "value", "exposure": "hours",
            },
        )
        self.assertEqual(result["accepted_rows"], 1)
        self.assertTrue(result["observations"][0]["quality_metadata"]["exposure_invalid"])

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


    def test_missing_periods_rejects_mixed_series(self):
        rows = [
            {"entity_id": "e1", "metric_id": "m", "event_time": "2024",
             "value": 1, "observation_status": "observed"},
            {"entity_id": "e2", "metric_id": "m", "event_time": "2024",
             "value": 2, "observation_status": "observed"},
        ]
        with self.assertRaisesRegex(ValueError, "one_entity_metric"):
            missing_periods(rows, ["2024"])

    def test_missingness_spike_is_reported_as_data_quality_not_behavior(self):
        expected = [f"{2024 + (month - 1) // 12}-{(month - 1) % 12 + 1:02d}" for month in range(1, 16)]
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

    def test_missingness_requires_series_identity_even_when_all_periods_absent(self):
        with self.assertRaisesRegex(ValueError, "one_entity_metric"):
            detect_missingness_spikes([], ["2024", "2025"])

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


    def test_missingness_spike_rejects_mixed_entity_or_metric_input(self):
        rows = [
            {"entity_id": "e1", "metric_id": "m", "event_time": "2024", "observation_status": "observed"},
            {"entity_id": "e2", "metric_id": "m", "event_time": "2025", "observation_status": "missing"},
        ]
        with self.assertRaisesRegex(ValueError, "one_entity_metric"):
            detect_missingness_spikes(rows, ["2024", "2025"])

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
        self.assertEqual(result["rho_source"], "estimated_from_first_difference_acf")
        self.assertAlmostEqual(result["rho"], rho, delta=0.06)
        self.assertAlmostEqual(result["value"], target_sigma, delta=0.35)

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

    def test_short_25_point_series_with_gaps_does_not_force_ar1(self):
        values = ar1_series(25, rho=0.45, stationary_sigma=1.3, seed=41)
        rows = observations(values, unit="days")
        rows = [row for index, row in enumerate(rows) if index not in {4, 10, 18}]
        ar1_result = first_difference_mad_scale(
            rows, time_unit="days", estimate_rho=True,
            min_adjacent_pairs_for_rho=1500,
        )
        self.assertIsNone(ar1_result["value"])
        self.assertEqual(ar1_result["status"], "rho_estimation_unavailable")
        self.assertEqual(ar1_result["rho_source"], "insufficient_consecutive_difference_pairs")
        iid_result = first_difference_mad_scale(
            rows, time_unit="days", estimate_rho=False,
        )
        self.assertEqual(iid_result["status"], "ok")
        self.assertGreater(iid_result["n_differences"], 8)
        self.assertGreater(iid_result["n_skipped_gaps"], 0)
        self.assertIsNone(iid_result["rho"])


    def test_ar1_first_difference_acf_is_invariant_to_linear_drift(self):
        rho, target_sigma = 0.55, 1.9
        noise = ar1_series(5000, rho=rho, stationary_sigma=target_sigma, seed=712)
        values = [25.0 + 0.035 * index + value for index, value in enumerate(noise)]
        rows = observations(values, unit="days")
        result = first_difference_mad_scale(
            rows, time_unit="days", estimate_rho=True,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rho_source"], "estimated_from_first_difference_acf")
        self.assertAlmostEqual(result["rho"], rho, delta=0.08)
        self.assertAlmostEqual(result["value"], target_sigma, delta=0.25)

    def test_univariate_builder_keeps_iid_and_ar1_scale_lanes_distinct(self):
        values = ar1_series(180, rho=0.4, stationary_sigma=1.7, seed=718)
        rows = observations(values, unit="days")
        iid = build_univariate_residuals(
            rows, baseline_window=12, min_history=8,
            time_unit="days", baseline_method="rolling_theil_sen",
            estimate_rho=False,
        )
        ar1 = build_univariate_residuals(
            rows, baseline_window=12, min_history=8,
            time_unit="days", baseline_method="rolling_theil_sen",
            estimate_rho=True, scale_window=64,
            min_adjacent_pairs_for_rho=40,
        )
        self.assertTrue(iid)
        self.assertTrue(ar1)
        self.assertTrue(all(row["scale_method"] in row["baseline_id"] for row in iid))
        self.assertTrue(all(row["scale_method"] in row["baseline_id"] for row in ar1))
        self.assertTrue(any("ar1_unavailable" in row["baseline_id"] for row in ar1))
        self.assertTrue(any("ar1_unit_gap" in row["baseline_id"] for row in ar1))
        self.assertTrue(all(row["scale_method"] in row["baseline_id"] for row in ar1))

    def test_ar1_mode_fails_closed_when_lagged_difference_support_is_insufficient(self):
        values = ar1_series(12, rho=0.65, stationary_sigma=2.0, seed=88)
        rows = observations(values, unit="days")
        result = first_difference_mad_scale(
            rows, time_unit="days", estimate_rho=True,
            min_adjacent_pairs_for_rho=1500,
        )
        self.assertIsNone(result["value"])
        self.assertEqual(result["status"], "rho_estimation_unavailable")
        self.assertEqual(result["method"], "first_difference_mad_ar1_unavailable")
        self.assertEqual(result["rho_source"], "unavailable")

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
    def test_first_observation_after_multi_period_gap_is_not_scored_as_break(self):
        rows = observations([float(i) for i in range(9)], start_year=2000)
        rows[-1]["event_time"] = "2012"
        result = build_univariate_residuals(
            rows, baseline_window=8, min_history=8, time_unit="years",
            baseline_method="rolling_theil_sen",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "gap_unresolved")
        self.assertIsNone(result[0]["z_score"])
        self.assertEqual(result[0]["observation_gap_units"], 5.0)

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



class PartialRelationTests(unittest.TestCase):
    def test_explicit_pairwise_relation_detects_a_new_y_break_prequentially(self):
        rng = random.Random(431)
        rows = []
        for index in range(26):
            x = 10.0 + index * 2.0 + rng.gauss(0.0, 0.1)
            y = 4.0 + 3.0 * x + rng.gauss(0.0, 0.35)
            if index == 25:
                y += 12.0
            for metric_id, value, unit in (
                ("hours", x, "hours"),
                ("completed_cases", y, "cases"),
            ):
                rows.append({
                    "entity_id": "team-1",
                    "metric_id": metric_id,
                    "event_time": str(2000 + index),
                    "value": value,
                    "unit": unit,
                    "observation_status": "observed",
                })
        results = build_partial_relation_residuals(
            rows,
            x_metric_id="hours",
            y_metric_id="completed_cases",
            relationship_id="cases-per-hour-v1",
            baseline_window=20,
            min_pairs=8,
        )
        last = results[-1]
        self.assertEqual(last["status"], "ready")
        self.assertEqual(last["relationship_id"], "cases-per-hour-v1")
        self.assertEqual(last["x_unit"], "hours")
        self.assertEqual(last["y_unit"], "cases")
        self.assertGreater(last["z_score"], 5.0)
        self.assertEqual(
            last["relationship_semantics"],
            "explicit_statistical_relation_not_causal_or_conservation_proof",
        )
        validate_residual_contract(results)
        result = run_candidate_detectors(results, cusum_k=0.5, cusum_h=4.0)
        self.assertTrue(
            any(hit["entity_id"] == "team-1" for hit in result["raw_hits"]["cusum"])
        )

    def test_unpaired_or_missing_observations_are_not_imputed(self):
        rows = []
        for index in range(12):
            rows.append({
                "entity_id": "team-1", "metric_id": "hours",
                "event_time": str(2010 + index), "value": 100 + index,
                "observation_status": "observed",
            })
            rows.append({
                "entity_id": "team-1", "metric_id": "completed_cases",
                "event_time": str(2010 + index),
                "value": None if index == 5 else 200 + 2 * index,
                "observation_status": "missing" if index == 5 else "observed",
            })
        results = build_partial_relation_residuals(
            rows, x_metric_id="hours", y_metric_id="completed_cases",
            relationship_id="work-output", min_pairs=8,
        )
        self.assertTrue(all(row["event_time"] != "2015-01-01T00:00:00+00:00" for row in results))
        self.assertEqual(len(results), 3)

    def test_partial_relation_does_not_score_first_pair_after_time_gap(self):
        rows = []
        event_years = list(range(2000, 2008)) + [2013, 2014]
        for index, year in enumerate(event_years):
            x = float(10 + index * 2)
            y = 5.0 + 4.0 * x + (0.1 if index % 2 else -0.1)
            for metric_id, value in (("hours", x), ("cases", y)):
                rows.append({
                    "entity_id": "team-1", "metric_id": metric_id,
                    "event_time": str(year), "value": value,
                    "observation_status": "observed",
                })
        results = build_partial_relation_residuals(
            rows, x_metric_id="hours", y_metric_id="cases",
            relationship_id="cases-hours", min_pairs=8,
        )
        self.assertEqual(results[0]["status"], "gap_unresolved")
        self.assertIsNone(results[0]["z_score"])
        self.assertEqual(results[0]["observation_gap_units"], 6.0)
        self.assertEqual(results[1]["status"], "ready")

    def test_relation_rejects_metric_unit_drift(self):
        rows = []
        for index in range(10):
            rows.append({
                "entity_id": "e1", "metric_id": "x", "event_time": str(2020 + index),
                "value": index + 1, "unit": "hours" if index < 8 else "minutes",
                "observation_status": "observed",
            })
            rows.append({
                "entity_id": "e1", "metric_id": "y", "event_time": str(2020 + index),
                "value": (index + 1) * 2, "unit": "cases",
                "observation_status": "observed",
            })
        with self.assertRaisesRegex(ValueError, "unit_changed"):
            build_partial_relation_residuals(
                rows, x_metric_id="x", y_metric_id="y",
                relationship_id="x-y", min_pairs=8,
            )

    def test_constant_x_makes_relation_unidentifiable(self):
        rows = []
        for index in range(10):
            rows.extend([
                {
                    "entity_id": "e1", "metric_id": "x", "event_time": str(2020 + index),
                    "value": 5, "observation_status": "observed",
                },
                {
                    "entity_id": "e1", "metric_id": "y", "event_time": str(2020 + index),
                    "value": 10 + index, "observation_status": "observed",
                },
            ])
        results = build_partial_relation_residuals(
            rows, x_metric_id="x", y_metric_id="y",
            relationship_id="flat-x", min_pairs=8,
        )
        self.assertEqual(results[-1]["status"], "relation_unidentifiable")


class DetectorAndFleetTests(unittest.TestCase):
    def test_both_cusum_directions_are_retained(self):
        residuals = [
            residual_row("entity-1", "metric-1", str(2020 + index), z)
            for index, z in enumerate([0, 0, 3, 3, 3, 0, -3, -3, -3])
        ]
        result = run_candidate_detectors(
            residuals, cusum_k=0.5, cusum_h=4.0, p1_threshold=2.0, p1_run_length=3
        )
        directions = {hit["direction"] for hit in result["raw_hits"]["cusum"]}
        self.assertEqual(directions, {"positive", "negative"})
        self.assertEqual(result["event_fusion"], "not_applied")
        self.assertEqual(result["alert_suppression"], "not_applied")

    def test_detector_state_never_accumulates_across_entities(self):
        residuals = [
            residual_row("A", "m", "2020", 3.0),
            residual_row("B", "m", "2020", 3.0),
            residual_row("C", "m", "2020", 3.0),
        ]
        result = run_candidate_detectors(
            residuals, cusum_k=0.5, cusum_h=5.0,
            p1_threshold=2.0, p1_run_length=3,
        )
        self.assertEqual(result["raw_hits"]["cusum"], [])
        self.assertEqual(result["raw_hits"]["sign_run"], [])

    def test_detector_state_isolated_by_baseline_and_metric(self):
        residuals = [
            residual_row("A", "m1", "2020", 3.0, baseline="baseline-1"),
            residual_row("A", "m2", "2020", 3.0, baseline="baseline-2"),
        ]
        result = run_candidate_detectors(
            residuals, cusum_k=0.5, cusum_h=5.0,
            p1_threshold=2.0, p1_run_length=3,
        )
        self.assertEqual(result["raw_hits"]["cusum"], [])
        self.assertEqual(result["raw_hits"]["sign_run"], [])

    def test_detector_rejects_noncanonical_residual_rows(self):
        with self.assertRaisesRegex(ValueError, "residual_contract_fields_missing"):
            run_candidate_detectors([{"event_time": "2024", "status": "ready", "z_score": 4.0}])

    def test_residual_contract_rejects_unknown_status_and_nonpositive_scale(self):
        invalid_status = residual_row("E", "m", "2024", 1.0, status="unknown")
        with self.assertRaisesRegex(ValueError, "residual_contract_status_invalid"):
            validate_residual_contract([invalid_status])
        invalid_scale = residual_row("E", "m", "2024", 1.0, status="gap_unresolved")
        invalid_scale["scale"] = 0.0
        with self.assertRaisesRegex(ValueError, "residual_contract_scale_not_positive"):
            validate_residual_contract([invalid_scale])

    def test_shared_contract_accepts_all_baseline_builder_outputs(self):
        univariate = build_univariate_residuals(
            observations([float(i * i) + (0.3 if i % 2 else -0.3) for i in range(18)]),
            baseline_window=8, min_history=8,
        )
        validate_residual_contract(univariate)

        peer_input = [{
            "entity_id": f"e{i}", "metric_id": "output", "event_time": "2024",
            "value": float(value), "unit": "cases", "observation_status": "observed",
            "cohort_id": "branch-role",
        } for i, value in enumerate([10, 12, 14, 16, 18, 40])]
        peer_rows = cohort_peer_residuals(peer_input, min_peers=5)
        validate_residual_contract(peer_rows)

        relation_input = []
        for i in range(12):
            relation_input.extend([
                {"entity_id": "team", "metric_id": "hours", "event_time": str(2000+i),
                 "value": float(i+1), "unit": "hours", "observation_status": "observed"},
                {"entity_id": "team", "metric_id": "cases", "event_time": str(2000+i),
                 "value": float(2*(i+1) + (0.1 if i%2 else -0.1)), "unit": "cases",
                 "observation_status": "observed"},
            ])
        relation_rows = build_partial_relation_residuals(
            relation_input, x_metric_id="hours", y_metric_id="cases",
            relationship_id="team-output-v1", min_pairs=8,
        )
        validate_residual_contract(relation_rows)

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
        validate_residual_contract(output)



    def test_peer_residuals_feed_detectors_without_cross_cohort_state(self):
        rows = []
        for period in range(4):
            event_time = str(2020 + period)
            values = [10, 11, 9, 10, 10, 11, 9, 10 if period < 2 else 20]
            for index, value in enumerate(values):
                rows.append({
                    "entity_id": f"staff-{index}",
                    "metric_id": "cases_per_period",
                    "event_time": event_time,
                    "value": float(value),
                    "unit": "cases",
                    "observation_status": "observed",
                    "cohort_id": "branch-A:role-B:season-C",
                })
        peer_rows = cohort_peer_residuals(rows, min_peers=5)
        validate_residual_contract(peer_rows)
        result = run_candidate_detectors(peer_rows, cusum_k=0.5, cusum_h=8.5)
        target_hits = [
            hit for hit in result["raw_hits"]["cusum"]
            if hit["entity_id"] == "staff-7"
        ]
        self.assertTrue(target_hits)
        self.assertEqual(target_hits[0]["direction"], "positive")

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
                "exposure_unit": "hours",
                "unit": "cases",
                "observation_status": "observed",
                "cohort_id": "branch-role-season",
            })
        result = cohort_peer_residuals(rows, min_peers=5, use_exposure=True)
        outlier = next(row for row in result if row["entity_id"] == "staff-5")
        self.assertEqual(outlier["value_basis"], "value_per_exposure")
        self.assertEqual(outlier["peer_expected"], 10.0)
        self.assertEqual(outlier["peer_residual"], 20.0)
        validate_residual_contract(result)


    def test_exposure_normalization_requires_a_declared_unit(self):
        rows = [{
            "entity_id": "e1", "metric_id": "output", "event_time": "2025-01",
            "value": 10, "exposure": 2, "observation_status": "observed",
            "cohort_id": "cohort-A",
        }]
        self.assertEqual(cohort_peer_residuals(rows, use_exposure=True), [])

    def test_duplicate_entity_period_is_rejected_in_peer_group(self):
        row = {
            "entity_id": "e1", "metric_id": "m", "event_time": "2025-01",
            "value": 10, "observation_status": "observed", "cohort_id": "c",
        }
        with self.assertRaisesRegex(ValueError, "duplicate_entity_metric_time"):
            cohort_peer_residuals([row, dict(row)])

    def test_missing_cohort_does_not_trigger_guessed_peer_group(self):
        rows = [{
            "entity_id": "e1", "metric_id": "m", "event_time": "2025-01",
            "value": 10, "observation_status": "observed",
        }]
        self.assertEqual(cohort_peer_residuals(rows), [])


if __name__ == "__main__":
    unittest.main()

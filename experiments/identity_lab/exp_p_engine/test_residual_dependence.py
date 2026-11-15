"""Tests for frozen residual-dependence estimation and innovation filtering."""
import math
import random
import unittest

from experiments.identity_lab.exp_p_engine.residual_dependence_experiment import (
    estimate_panel_residual_rho,
    lag1_summary,
    prewhiten_evaluation_rows,
    run_injection_experiment,
    summarize_detector_hits,
    calibrate_prewhitened_null,
    stationary_bootstrap_sample,
    compare_screened_injection_recall,
    fixed_injection_onset,
    _matched_evaluation_streams,
    _first_hit_summary,
)
from experiments.identity_lab.exp_p_engine.domain_neutral import (
    detect_two_sided_cusum,
    validate_residual_contract,
)


def make_ar1_rows(
    *,
    entities=80,
    training_count=24,
    evaluation_count=8,
    rho=0.60,
    seed=37,
    inject_shift=False,
    gap=False,
):
    rng = random.Random(seed)
    rows = []
    for entity in range(entities):
        state = rng.gauss(0.0, 1.0)
        values = []
        total = training_count + evaluation_count
        for index in range(total):
            state = rho * state + rng.gauss(0.0, math.sqrt(1.0 - rho * rho))
            value = state
            if inject_shift and index >= training_count + 2:
                value += 2.5
            values.append(value)
        center = sum(values[:training_count]) / training_count
        for index, value in enumerate(values):
            if gap and index == training_count + 3:
                continue
            year = 2000 + index
            z = value - center
            rows.append({
                "entity_id": f"entity-{entity}",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": value,
                "expected_value": center,
                "residual": z,
                "scale": 1.0,
                "z_score": z,
                "status": "ready",
                "baseline_id": "test-baseline",
                "baseline_method": "synthetic-ar1",
                "support_count": training_count,
                "unit": "unit",
            })
    return rows


class ResidualDependenceTests(unittest.TestCase):
    def test_panel_residual_rho_is_estimated_from_training_only(self):
        rows = make_ar1_rows(rho=0.60)
        calibration = estimate_panel_residual_rho(
            rows,
            training_end="2023",
            min_series=30,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=300,
        )
        self.assertEqual(calibration["status"], "ok")
        self.assertAlmostEqual(calibration["rho"], 0.60, delta=0.12)
        self.assertGreater(calibration["series_count"], 70)
        self.assertTrue(all(
            int(key.split("::")[0].split("-")[1]) >= 0
            for key in calibration["entity_centers"]
        ))

    def test_prewhitening_reduces_held_out_lag1_dependence(self):
        rows = make_ar1_rows(rho=0.65, seed=91)
        calibration = estimate_panel_residual_rho(
            rows,
            training_end="2023",
            min_series=30,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=300,
        )
        self.assertEqual(calibration["status"], "ok")
        raw_eval = [row for row in rows if int(row["event_time"]) >= 2024]
        whitened = prewhiten_evaluation_rows(
            rows, calibration, evaluation_start="2024"
        )
        # The transformed stream must remain contract-valid and consumable by
        # the existing detector API. Raw metric-space values remain auditable.
        validate_residual_contract(whitened)
        detect_two_sided_cusum(whitened, k=0.5, h=3.0)
        source_by_key = {
            (row["entity_id"], row["event_time"]): row for row in rows
        }
        for row in whitened:
            if row["status"] == "ready":
                self.assertAlmostEqual(row["observed_value"] - row["expected_value"], row["residual"])
                self.assertAlmostEqual(row["residual"] / row["scale"], row["z_score"])
                self.assertEqual(row["baseline_method"], "frozen_panel_ar1_residual_prewhitening")
                self.assertEqual(row["unit"], "standardized_innovation")
                source = source_by_key[(row["entity_id"], row["event_time"])]
                self.assertEqual(row["raw_residual"], source["residual"])
                self.assertEqual(row["raw_expected_value"], source["expected_value"])
            else:
                self.assertIn(row["status"], {
                    "innovation_gap_reset", "innovation_warmup_or_gap"
                })
                self.assertIsNone(row["residual"])
                self.assertIsNone(row["z_score"])
        raw_lag = lag1_summary(raw_eval)["median_entity_lag1"]
        white_lag = lag1_summary(whitened)["median_entity_lag1"]
        self.assertIsNotNone(raw_lag)
        self.assertIsNotNone(white_lag)
        self.assertLess(abs(white_lag), abs(raw_lag))

    def test_whitening_does_not_bridge_unobserved_gap(self):
        rows = make_ar1_rows(
            entities=50, training_count=24, evaluation_count=8,
            rho=0.5, seed=51, gap=True,
        )
        calibration = estimate_panel_residual_rho(
            rows,
            training_end="2023",
            min_series=20,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=200,
        )
        self.assertEqual(calibration["status"], "ok")
        whitened = prewhiten_evaluation_rows(
            rows, calibration, evaluation_start="2024"
        )
        by_entity = {}
        for row in whitened:
            by_entity.setdefault(row["entity_id"], {})[row["event_time"]] = row
        sample = next(iter(by_entity.values()))
        # 2027 is deliberately absent; 2028 is the first point after the gap.
        if "2028" in sample:
            self.assertEqual(sample["2028"]["status"], "innovation_warmup_or_gap")
            self.assertIsNone(sample["2028"]["z_score"])

    def test_invalid_panel_calibration_fails_closed(self):
        rows = make_ar1_rows(entities=8, training_count=12, evaluation_count=3)
        calibration = estimate_panel_residual_rho(
            rows,
            training_end="2011",
            min_series=30,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=200,
        )
        self.assertEqual(calibration["status"], "insufficient_panel_residual_support")
        with self.assertRaisesRegex(ValueError, "not_approved"):
            prewhiten_evaluation_rows(rows, calibration, evaluation_start="2012")

    def test_stationary_bootstrap_never_wraps_or_crosses_source_gaps(self):
        segments = [list(range(8)), list(range(20, 26))]
        blocks = stationary_bootstrap_sample(
            segments,
            target_length=80,
            restart_probability=0.01,
            rng=random.Random(19),
        )
        self.assertEqual(sum(len(block) for block in blocks), 80)
        for block in blocks:
            self.assertTrue(
                any(
                    block == segment[start:start + len(block)]
                    for segment in segments
                    for start in range(len(segment) - len(block) + 1)
                ),
                msg=f"block crossed a source boundary: {block}",
            )

    def test_stationary_bootstrap_start_sampling_is_length_weighted(self):
        short_segment = [0, 1]
        long_segment = list(range(10, 30))
        rng = random.Random(31)
        short_starts = 0
        long_starts = 0
        for _ in range(5000):
            block = stationary_bootstrap_sample(
                [short_segment, long_segment],
                target_length=1,
                restart_probability=1.0,
                rng=rng,
            )
            if block[0][0] < 10:
                short_starts += 1
            else:
                long_starts += 1
        self.assertGreater(long_starts, short_starts * 5)

    def test_stationary_bootstrap_calibration_reports_5pct_gate(self):
        rows = make_ar1_rows(
            entities=50, training_count=24, evaluation_count=8,
            rho=0.6, seed=115,
        )
        calibration = estimate_panel_residual_rho(
            rows,
            training_end="2023",
            min_series=30,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=100,
        )
        self.assertEqual(calibration["status"], "ok")
        whitened = prewhiten_evaluation_rows(
            rows, calibration, evaluation_start="2024"
        )
        report = calibrate_prewhitened_null(
            whitened,
            replicates=25,
            restart_probabilities=(0.25, 0.35),
            cusum_grid=({"k": 0.5, "h": 8.5},),
            p1_grid=({"threshold": 3.0, "run_length": 3},),
            min_segment_length=5,
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["restart_probabilities"], [0.25, 0.35])
        self.assertAlmostEqual(
            report["expected_geometric_block_lengths"]["0.25"], 4.0
        )
        self.assertAlmostEqual(
            report["expected_geometric_block_lengths"]["0.35"], 1.0 / 0.35
        )
        self.assertEqual(
            report["series_alarm_screen"]["maximum_upper95_series_alarm_rate"],
            0.05,
        )
        self.assertIn("0.25", report["detectors"]["cusum"][0]["by_probability"])
        self.assertIn("0.35", report["detectors"]["cusum"][0]["by_probability"])


    def test_stationary_sampler_observed_mean_length_tracks_geometric_mean(self):
        segments = [list(range(10000))]
        for probability, expected in ((0.25, 4.0), (0.35, 1.0 / 0.35)):
            blocks = stationary_bootstrap_sample(
                segments,
                target_length=30000,
                restart_probability=probability,
                rng=random.Random(101),
            )
            observed = sum(len(block) for block in blocks) / len(blocks)
            self.assertAlmostEqual(observed, expected, delta=0.20)

    def test_matched_streams_use_identical_entity_metric_year_support(self):
        def make_row(year, value, *, status="ready", baseline="base"):
            return {
                "entity_id": "entity-1",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": value if status == "ready" else None,
                "expected_value": 0.0 if status == "ready" else None,
                "residual": value if status == "ready" else None,
                "scale": 1.0 if status == "ready" else None,
                "z_score": value if status == "ready" else None,
                "status": status,
                "baseline_id": baseline,
                "baseline_method": "test",
                "support_count": 8,
            }

        raw = [
            make_row(2015, 0.1, baseline="raw"),
            make_row(2016, 0.2, baseline="raw"),
            make_row(2017, 0.3, baseline="raw"),
            make_row(2018, 0.4, baseline="raw"),
        ]
        white = [
            make_row(2015, 0.11, baseline="white"),
            make_row(2016, 0.21, baseline="white"),
            make_row(
                2017, None,
                status="innovation_warmup_or_gap",
                baseline="white",
            ),
            make_row(2018, 0.41, baseline="white"),
        ]
        (
            raw_aligned,
            white_aligned,
            matched_series,
            matched_ready_periods,
        ) = _matched_evaluation_streams(raw, white, min_segment_length=2)

        self.assertEqual(matched_series, 1)
        self.assertEqual(matched_ready_periods, 3)
        self.assertEqual(
            [row["event_time"] for row in raw_aligned],
            ["2015", "2016", "2017", "2018"],
        )
        self.assertEqual(
            [row["event_time"] for row in white_aligned],
            ["2015", "2016", "2017", "2018"],
        )
        self.assertEqual(raw_aligned[2]["status"], "gap_unresolved")
        self.assertEqual(white_aligned[2]["status"], "gap_unresolved")
        self.assertIsNone(raw_aligned[2]["z_score"])
        self.assertIsNone(white_aligned[2]["z_score"])

    def test_four_way_injection_alignment_uses_same_annual_periods(self):
        def make_row(year, value, *, status="ready", baseline="base"):
            return {
                "entity_id": "entity-1",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": value if status == "ready" else None,
                "expected_value": 0.0 if status == "ready" else None,
                "residual": value if status == "ready" else None,
                "scale": 1.0 if status == "ready" else None,
                "z_score": value if status == "ready" else None,
                "status": status,
                "baseline_id": baseline,
                "baseline_method": "test",
                "support_count": 8,
            }

        streams = [
            [make_row(year, 0.1, baseline=f"stream-{i}") for year in (2019, 2020, 2021, 2022)]
            for i in range(4)
        ]
        streams[2][1] = make_row(
            2020, None,
            status="innovation_warmup_or_gap",
            baseline="stream-2",
        )
        *aligned, matched_series, matched_periods = _matched_evaluation_streams(
            *streams,
            min_segment_length=2,
        )
        self.assertEqual(matched_series, 1)
        self.assertEqual(matched_periods, 3)
        timestamps = [
            [row["event_time"] for row in stream]
            for stream in aligned
        ]
        self.assertTrue(all(value == timestamps[0] for value in timestamps[1:]))
        statuses = [[row["status"] for row in stream] for stream in aligned]
        self.assertTrue(all(value[1] == "gap_unresolved" for value in statuses))

    def test_shared_missing_year_preserves_baseline_group_and_resets_cusum(self):
        def make_row(year, z, baseline):
            return {
                "entity_id": "entity-gap",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": z,
                "expected_value": 0.0,
                "residual": z,
                "scale": 1.0,
                "z_score": z,
                "status": "ready",
                "baseline_id": baseline,
                "baseline_method": "test",
                "support_count": 8,
            }

        raw = [
            make_row(2015, 2.8, "raw-baseline"),
            make_row(2017, 2.8, "raw-baseline"),
        ]
        white = [
            make_row(2015, 2.7, "white-baseline"),
            make_row(2017, 2.7, "white-baseline"),
        ]
        raw_aligned, white_aligned, matched_series, ready_periods = (
            _matched_evaluation_streams(raw, white, min_segment_length=2)
        )
        self.assertEqual(matched_series, 1)
        self.assertEqual(ready_periods, 2)
        self.assertEqual(raw_aligned[1]["event_time"], "2016")
        self.assertEqual(raw_aligned[1]["status"], "gap_unresolved")
        self.assertEqual(raw_aligned[1]["baseline_id"], "raw-baseline")
        self.assertEqual(white_aligned[1]["baseline_id"], "white-baseline")
        self.assertEqual(detect_two_sided_cusum(raw_aligned, k=0.5, h=4.0), [])

    def test_injection_onset_is_fixed_after_longer_null_window(self):
        self.assertEqual(fixed_injection_onset(list(range(2014, 2025))), 2021)
        self.assertIsNone(
            fixed_injection_onset(list(range(2014, 2024)))
        )

    def test_detection_horizon_marks_first_evidence_through_year_three(self):
        rows = []
        for year, z in ((2021, 0.2), (2022, 0.2), (2023, 0.2), (2024, 3.5), (2025, 0.1)):
            rows.append({
                "entity_id": "entity-horizon",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": z,
                "expected_value": 0.0,
                "residual": z,
                "scale": 1.0,
                "z_score": z,
                "status": "ready",
                "baseline_id": "horizon-baseline",
                "baseline_method": "test",
                "support_count": 8,
                "unit": "standardized",
            })
        within = _first_hit_summary(
            rows, onset="2021", detector="sign_run",
            parameters={"threshold": 3.0, "run_length": 1},
        )
        self.assertEqual(within["delay_years"], 3.0)
        self.assertTrue(within["detected_within_3_years"])

        late_rows = [dict(row) for row in rows]
        late_rows[-2]["z_score"] = 0.1
        late_rows[-2]["observed_value"] = 0.1
        late_rows[-2]["residual"] = 0.1
        late_rows[-1]["z_score"] = 3.5
        late_rows[-1]["observed_value"] = 3.5
        late_rows[-1]["residual"] = 3.5
        late = _first_hit_summary(
            late_rows, onset="2021", detector="sign_run",
            parameters={"threshold": 3.0, "run_length": 1},
        )
        self.assertEqual(late["delay_years"], 4.0)
        self.assertFalse(late["detected_within_3_years"])

    def test_paired_screened_recall_reports_entity_bootstrap_interval(self):
        null = {
            "status": "ok",
            "detectors": {
                "cusum": [{
                    "params": {"k": 1.0, "h": 64.0},
                    "passes_all_probabilities": True,
                }],
                "sign_run": [],
            },
        }
        responses = {
            "raw_residuals": [{
                "entity_id": "A",
                "scenario": "positive_3.0sigma",
                "cusum": [{
                    "k": 1.0, "h": 64.0,
                    "injected_detected": True,
                    "control_detected": False,
                    "injected_detected_within_3_years": True,
                    "control_detected_within_3_years": False,
                    "injected_direction": "positive",
                    "injected_delay_years": 1.0,
                }],
            }],
            "prewhitened_innovations": [{
                "entity_id": "A",
                "scenario": "positive_3.0sigma",
                "cusum": [{
                    "k": 1.0, "h": 64.0,
                    "injected_detected": False,
                    "control_detected": False,
                    "injected_detected_within_3_years": False,
                    "control_detected_within_3_years": False,
                    "injected_direction": None,
                    "injected_delay_years": None,
                }],
            }],
        }
        report = compare_screened_injection_recall(null, null, responses)
        comparison = report["scenario_comparisons"]["positive_3.0sigma"]["detectors"]["cusum"]
        self.assertEqual(comparison["paired_passing_setting_count"], 1)
        item = comparison["paired_settings"][0]
        self.assertEqual(item["tested_series"], 1)
        self.assertEqual(item["recall_difference_innovation_minus_raw"], -1.0)
        self.assertEqual(item["recall_difference_ci95"], [-1.0, -1.0])

    def test_comparison_excludes_settings_without_a_common_null_pass(self):
        raw = {
            "status": "ok",
            "detectors": {
                "cusum": [{
                    "params": {"k": 1.0, "h": 64.0},
                    "passes_all_probabilities": True,
                }],
            },
        }
        white = {
            "status": "ok",
            "detectors": {
                "cusum": [{
                    "params": {"k": 1.0, "h": 128.0},
                    "passes_all_probabilities": True,
                }],
            },
        }
        report = compare_screened_injection_recall(raw, white, {})
        self.assertEqual(report["common_passing_settings"]["cusum"], [])

    def test_injection_experiment_skips_entities_without_residual_history(self):
        short_series = make_ar1_rows(
            entities=1, training_count=6, evaluation_count=3, seed=7
        )
        short_series = [
            {**row, "entity_id": "short-entity"}
            for row in short_series
        ]
        result = run_injection_experiment(
            {"short-entity": short_series},
            {},
            {"status": "ok", "rho": 0.5, "entity_centers": {}},
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["eligible_entities"], 0)
        self.assertEqual(
            result["skipped_entities"].get("insufficient_baseline_history"), 1
        )
        self.assertEqual(result["responses"], {})

    def test_injected_detector_state_starts_at_labelled_onset(self):
        rows = []
        for year, z in ((2000, 2.8), (2001, 2.8), (2002, 1.0), (2003, 1.0)):
            rows.append({
                "entity_id": "entity-1",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": z,
                "expected_value": 0.0,
                "residual": z,
                "scale": 1.0,
                "z_score": z,
                "status": "ready",
                "baseline_id": "test-baseline",
                "baseline_method": "test",
                "support_count": 8,
                "unit": "standardized",
            })
        result = _first_hit_summary(
            rows,
            onset="2002",
            detector="cusum",
            parameters={"k": 0.5, "h": 5.0},
        )
        # Carrying the 2000-2001 accumulator would create an immediate false
        # post-onset hit at 2002; a fresh onset state must remain below h.
        self.assertFalse(result["detected"])

    def test_sign_run_does_not_carry_pre_onset_evidence(self):
        rows = []
        for year, z in ((2000, 3.0), (2001, 3.0), (2002, 1.0), (2003, 1.0)):
            rows.append({
                "entity_id": "entity-1",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": z,
                "expected_value": 0.0,
                "residual": z,
                "scale": 1.0,
                "z_score": z,
                "status": "ready",
                "baseline_id": "test-baseline",
                "baseline_method": "test",
                "support_count": 8,
                "unit": "standardized",
            })
        result = _first_hit_summary(
            rows,
            onset="2002",
            detector="sign_run",
            parameters={"threshold": 2.5, "run_length": 2},
        )
        self.assertFalse(result["detected"])

    def test_detector_summary_uses_stream_specific_parameter_grids(self):
        rows = []
        for year, z in ((2020, 0.2), (2021, 0.5), (2022, 0.1)):
            rows.append({
                "entity_id": "entity-1",
                "metric_id": "metric",
                "event_time": str(year),
                "observed_value": z,
                "expected_value": 0.0,
                "residual": z,
                "scale": 1.0,
                "z_score": z,
                "status": "ready",
                "baseline_id": "test-baseline",
                "baseline_method": "test",
                "support_count": 8,
                "unit": "standardized_innovation",
            })
        summary = summarize_detector_hits(
            rows,
            cusum_grid=({"k": 0.25, "h": 1.75},),
            p1_grid=({"threshold": 0.4, "run_length": 2},),
        )
        self.assertEqual(summary["cusum"][0]["k"], 0.25)
        self.assertEqual(summary["cusum"][0]["h"], 1.75)
        self.assertEqual(summary["sign_run"][0]["threshold"], 0.4)
        self.assertEqual(summary["sign_run"][0]["run_length"], 2)

    def test_evaluation_observations_do_not_change_frozen_rho(self):
        rows = make_ar1_rows(rho=0.55, seed=101)
        baseline = estimate_panel_residual_rho(
            rows,
            training_end="2023",
            min_series=30,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=300,
        )
        mutated = [dict(row) for row in rows]
        for row in mutated:
            if int(row["event_time"]) >= 2024:
                row["z_score"] = 1000.0 * row["z_score"]
        after = estimate_panel_residual_rho(
            mutated,
            training_end="2023",
            min_series=30,
            min_lag_pairs_per_series=8,
            bootstrap_replicates=300,
        )
        self.assertEqual(baseline["rho"], after["rho"])
        self.assertEqual(baseline["rho_ci95"], after["rho_ci95"])


if __name__ == "__main__":
    unittest.main()

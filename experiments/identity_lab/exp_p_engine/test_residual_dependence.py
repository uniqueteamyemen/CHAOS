"""Tests for frozen residual-dependence estimation and innovation filtering."""
import math
import random
import unittest

from experiments.identity_lab.exp_p_engine.residual_dependence_experiment import (
    estimate_panel_residual_rho,
    lag1_summary,
    prewhiten_evaluation_rows,
    run_injection_experiment,
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

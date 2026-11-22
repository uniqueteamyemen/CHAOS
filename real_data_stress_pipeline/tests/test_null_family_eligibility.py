import unittest
from unittest.mock import patch

import numpy as np

from real_data_stress_pipeline import run_pipeline as p2
from real_data_stress_pipeline.run_pipeline import (
    assess_null_family, bootstrap_null_sample, boot, g1, PIPELINE_CONFIG
)


class NullFamilyEligibilityTests(unittest.TestCase):
    def test_level_stationary_series_uses_level_null(self):
        values = np.random.default_rng(12).normal(0.0, 0.5, 540)
        result = assess_null_family(values, g1(values), "commodity")
        self.assertEqual(result["family"], "LEVEL_STATIONARY_BLOCK")

    def test_deterministic_trend_uses_residual_null_not_level_null(self):
        rng = np.random.default_rng(44)
        index = np.arange(600, dtype=float)
        values = 2.0 + 0.025 * index + rng.normal(0.0, 0.3, index.size)
        result = assess_null_family(values, g1(values), "macro")
        self.assertEqual(result["family"], "TREND_RESIDUAL_BLOCK", result)

    def test_integrated_series_uses_increment_null(self):
        rng = np.random.default_rng(55)
        values = np.cumsum(rng.normal(0.0, 1.0, 600))
        result = assess_null_family(values, g1(values), "macro")
        self.assertEqual(result["family"], "INTEGRATED_INCREMENT_BLOCK", result)

    def test_seismic_series_is_not_assigned_a_generic_null(self):
        values = np.random.default_rng(56).normal(size=540)
        result = assess_null_family(values, g1(values), "seismic")
        self.assertEqual(result["status"], "BLOCKED_DOMAIN_NULL_REQUIRED")
        self.assertIsNone(result["family"])

    def test_degenerate_series_remains_unresolved(self):
        result = assess_null_family(np.zeros(120), {"passed": False, "status": "DEGENERATE"})
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertIsNone(result["family"])

    def test_integrated_bootstrap_preserves_length_and_starting_value(self):
        values = np.cumsum(np.random.default_rng(57).normal(size=300))
        assessment = {"status": "ELIGIBLE", "family": "INTEGRATED_INCREMENT_BLOCK"}
        sampled = bootstrap_null_sample(values, np.random.default_rng(58), 12, assessment)
        self.assertEqual(sampled.size, values.size)
        self.assertEqual(sampled[0], values[0])
        self.assertTrue(np.all(np.isfinite(sampled)))


    def test_detector_runs_even_when_g1_fails(self):
        values = np.linspace(0.0, 10.0, 120)
        item = {
            "id": "nonstationary-test",
            "source": "world_bank",
            "name": "Synthetic nonstationary series",
            "cohort": "macro",
            "domain": "macro",
            "frequency": "monthly",
            "values": values,
            "axis": [f"2000-{(i % 12) + 1:02d}" for i in range(values.size)],
            "sha256": "a" * 64,
            "quality": {"status": "PASS"},
        }
        detector_output = {
            "markov_cusum": {"alarm_count": 1, "events": [], "shock_matches": []}
        }
        with (
            patch.object(p2, "run_modes", return_value=detector_output) as detector,
            patch.object(p2, "g1", return_value={"passed": False, "status": "SCREEN_FAIL"}),
            patch.object(p2, "assess_null_family", return_value={
                "status": "UNRESOLVED", "family": None
            }),
            patch.object(p2, "applicable_shock_series", return_value=False),
            patch.object(p2, "boot", return_value={
                "status": "SKIPPED_NO_VALIDATED_NULL", "replicates": 0,
                "null_family": None
            }),
        ):
            result = p2.eval_series(item, {"events": []})

        detector.assert_called_once_with(values)
        self.assertFalse(result["g1"]["passed"])
        self.assertEqual(result["detector"]["markov_cusum"]["alarm_count"], 1)
        self.assertEqual(result["bootstrap"]["status"], "SKIPPED_NO_VALIDATED_NULL")

    def test_pipeline_config_disables_stationarity_gate_on_detector(self):
        self.assertIs(
            PIPELINE_CONFIG["stationarity"]["detector_execution_requires_stationarity"],
            False,
        )
        self.assertIs(
            PIPELINE_CONFIG["bootstrap"]["seismic_generic_block_bootstrap_enabled"],
            False,
        )

    def test_detector_null_skip_is_explicitly_domain_scoped(self):
        result = boot(
            np.random.default_rng(59).normal(size=200),
            "seismic-test", 12,
            {"status": "BLOCKED_DOMAIN_NULL_REQUIRED", "family": None,
             "reason": "SEISMIC_POINT_PROCESS_NULL_REQUIRED"},
        )
        self.assertEqual(result["status"], "SKIPPED_DOMAIN_SPECIFIC_NULL_REQUIRED")
        self.assertEqual(result["replicates"], 0)


if __name__ == "__main__":
    unittest.main()

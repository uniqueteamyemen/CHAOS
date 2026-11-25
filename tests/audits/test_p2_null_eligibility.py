from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from real_data_stress_pipeline import run_pipeline as p2


class NullEligibilityTests(unittest.TestCase):
    def test_seismic_series_never_uses_generic_stationary_bootstrap(self):
        result = p2.boot(
            np.random.default_rng(11).normal(size=120),
            "seismic-null-test",
            25,
            {"passed": True, "status": "SCREEN_PASS"},
            "seismic",
        )
        self.assertEqual(result["status"], "SKIPPED_DOMAIN_NULL_REQUIRED")
        self.assertEqual(
            result["null_eligibility"],
            "DOMAIN_SPECIFIC_POINT_PROCESS_MODEL_REQUIRED",
        )
        self.assertEqual(result["replicates"], 0)
        self.assertTrue(all(mode["runs"] == 0 for mode in result["by_mode"].values()))

    def test_nonstationary_economic_levels_route_to_stationary_first_differences(self):
        values = np.cumsum(np.random.default_rng(12).normal(size=120))
        sampled_inputs = []

        def sample(series, rng, block):
            sampled_inputs.append(np.asarray(series, dtype=float).copy())
            return np.full(len(series), 0.25, dtype=float)

        with (
            patch.object(
                p2, "g1",
                return_value={"passed": True, "status": "SCREEN_PASS"},
            ),
            patch.object(p2, "REPS", 2),
            patch.object(p2, "stationary_sample", side_effect=sample),
            patch.object(
                p2.BreakDetectorV1,
                "analyze",
                return_value={"structural_breaks": []},
            ),
        ):
            result = p2.boot(
                values,
                "integrated-null-test",
                12,
                {"passed": False, "status": "SCREEN_FAIL"},
                "macro",
            )

        self.assertEqual(
            result["null_family"],
            "INTEGRATED_STATIONARY_BOOTSTRAP_OF_FIRST_DIFFERENCES",
        )
        self.assertEqual(result["status"], "ESTIMATED_CONDITIONAL_DIAGNOSTIC")
        self.assertEqual(result["replicates"], 2)
        self.assertEqual(len(sampled_inputs), 2)
        self.assertEqual(len(sampled_inputs[0]), len(values) - 1)
        self.assertEqual(
            result["alternative_null_status"],
            "ESTIMATED_CONDITIONALLY",
        )

    def test_already_differenced_returns_are_never_reintegrated(self):
        returns = np.random.default_rng(120).normal(scale=0.03, size=120)
        sampled_inputs = []

        def sample(series, rng, block):
            sampled_inputs.append(np.asarray(series, dtype=float).copy())
            return np.full(len(series), 0.25, dtype=float)

        with (
            patch.object(p2, "g1", return_value={"passed": False, "status": "SCREEN_FAIL"}),
            patch.object(p2, "REPS", 2),
            patch.object(p2, "stationary_sample", side_effect=sample),
        ):
            result = p2.boot(
                returns, "pink-sheet-returns", 12,
                {"passed": False, "status": "SCREEN_FAIL"},
                "commodity", series_representation="returns"
            )

        self.assertEqual(result["status"], "SKIPPED_G1_SCREEN_FAILED")
        self.assertEqual(result["replicates"], 0)
        self.assertEqual(result["series_representation"], "returns")
        self.assertEqual(
            result["null_eligibility"],
            "INCREMENT_SERIES_FAILED_ITS_OWN_NULL_SCREEN",
        )
        self.assertEqual(
            result["skip_reason"],
            "ALREADY_INCREMENT_SERIES_NOT_ELIGIBLE_FOR_REINTEGRATION",
        )
        self.assertEqual(sampled_inputs, [])

    def test_failed_level_and_increment_screens_do_not_create_a_fallback_null(self):
        with patch.object(
            p2, "g1",
            side_effect=[
                {"passed": False, "status": "SCREEN_FAIL"},
                {"passed": False, "status": "SCREEN_FAIL"},
            ],
        ):
            result = p2.boot(
                np.random.default_rng(13).normal(size=120),
                "no-null-test",
                12,
                {"passed": False, "status": "SCREEN_FAIL"},
                "commodity",
            )
        self.assertEqual(result["status"], "SKIPPED_NO_VALIDATED_NULL")
        self.assertEqual(result["replicates"], 0)
        self.assertEqual(result["alternative_null_status"], "NOT_ESTABLISHED")


    def test_pipeline_config_matches_null_routing_contract(self):
        self.assertIs(
            p2.PIPELINE_CONFIG["stationarity"]["detector_execution_requires_stationarity"],
            False,
        )
        self.assertFalse(
            p2.PIPELINE_CONFIG["bootstrap"]["seismic_generic_bootstrap_enabled"]
        )
        self.assertIn(
            "INTEGRATED_STATIONARY_BOOTSTRAP_OF_FIRST_DIFFERENCES",
            p2.PIPELINE_CONFIG["stationarity"]["integrated_null_family"],
        )
        self.assertEqual(
            p2.LEVEL_NULL_FAMILY,
            p2.PIPELINE_CONFIG["stationarity"]["level_null_family"],
        )
        self.assertEqual(
            p2.INTEGRATED_NULL_FAMILY,
            p2.PIPELINE_CONFIG["stationarity"]["integrated_null_family"],
        )
        self.assertEqual(
            p2.INTEGRATED_NULL_DOMAINS,
            frozenset(p2.PIPELINE_CONFIG["stationarity"]["integrated_null_domain_allowlist"]),
        )
        self.assertFalse(p2.BOOTSTRAP_CONFIG["operational_fpr_claim_permitted"])

    def test_g1_applies_explicit_configured_significance_thresholds(self):
        values = np.random.default_rng(15).normal(size=100)
        with (
            patch.object(p2, "adfuller", return_value=(0.0, 0.04, 1, 98, {})),
            patch.object(p2, "kpss", return_value=(0.0, 0.06, 1, {})),
        ):
            result = p2.g1(values, adf_significance=0.03, kpss_significance=0.08)

        self.assertFalse(result["passed"])
        self.assertEqual(result["adf_significance"], 0.03)
        self.assertEqual(result["kpss_significance"], 0.08)

    def test_detector_execution_is_independent_of_null_eligibility(self):
        item = {
            "id": "macro:test",
            "source": "gem",
            "name": "Test macro series",
            "cohort": "test",
            "domain": "seismic",
            "frequency": "monthly",
            "axis": [f"2000-{(i % 12) + 1:02d}" for i in range(100)],
            "values": np.random.default_rng(14).normal(size=100).tolist(),
            "sha256": "test-hash",
            "quality": {"passed": True},
        }
        with (
            patch.object(p2, "run_modes", return_value={}) as detector,
            patch.object(p2, "g1", return_value={
                "passed": False,
                "status": "SCREEN_FAIL",
            }),
        ):
            result = p2.eval_series(item, {"events": []})

        detector.assert_called_once()
        self.assertEqual(
            result["evaluation_policy"]["detector_execution"],
            "COMPLETED_BEFORE_NULL_SELECTION",
        )
        self.assertEqual(
            result["bootstrap"]["status"],
            "SKIPPED_DOMAIN_NULL_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()

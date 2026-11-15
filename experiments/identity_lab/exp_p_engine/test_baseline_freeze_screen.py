"""Unit tests for CUSUM-confirmed baseline-freeze screening metrics."""
import unittest

from experiments.identity_lab.exp_p_engine.baseline_freeze_screen import (
    _first_cusum_alarm,
    _paired_post_trigger_metrics,
    _synthetic_confirmation_controls,
    _assess_candidate_operational_eligibility,
)
from experiments.identity_lab.exp_p_engine.baseline_freeze_experiment import (
    build_policy_residuals,
)
from experiments.identity_lab.exp_p_engine.baseline_freeze_screen import (
    passing_confirmation_thresholds,
)
from experiments.identity_lab.exp_p_engine.domain_neutral import (
    detect_two_sided_cusum,
)


def make_series(*, count=36, shift_from=None, shift=0.0):
    rows = []
    pattern = (0.10, -0.10, 0.05, -0.05)
    for index in range(count):
        year = 2000 + index
        value = 20.0 + 0.2 * index + pattern[index % 4]
        if shift_from is not None and index >= shift_from:
            value += shift
        rows.append({
            "entity_id": "entity-confirm",
            "metric_id": "output",
            "event_time": str(year),
            "value": value,
            "observation_status": "observed",
            "unit": "units",
        })
    return rows


class ConfirmationFreezeScreenTests(unittest.TestCase):
    def test_threshold_extraction_reads_nested_calibration_params(self):
        calibration = {
            "detectors": {
                "cusum": [
                    {"params": {"k": 0.5, "h": 48.0}, "passes_all_probabilities": False},
                    {"params": {"k": 0.5, "h": 64.0}, "passes_all_probabilities": True},
                    {"params": {"k": 0.5, "h": 96.0}, "passes_all_probabilities": True},
                    {"params": {"k": 1.0, "h": 128.0}, "passes_all_probabilities": True},
                ]
            }
        }
        self.assertEqual(passing_confirmation_thresholds(calibration), [64.0, 96.0])

    def test_candidate_requires_minimum_triggered_injection_support(self):
        candidate = {
            "passes_5pct_series_alarm_screen": True,
            "injection_records": {
                "negative_6.0sigma": [{"raw_injected_alarm": True}] * 5,
                "positive_6.0sigma": [{"raw_injected_alarm": True}] * 5,
                "negative_3.0sigma": [],
                "positive_3.0sigma": [],
            },
            "injections": {
                "negative_6.0sigma": {
                    "injected_trigger_time_match_rate": 1.0,
                    "confirmation_freeze_control_trigger_rate": 0.0,
                    "injected_mean_abs_z_gain_ci95": [0.1, 1.0],
                },
                "positive_6.0sigma": {
                    "injected_trigger_time_match_rate": 1.0,
                    "confirmation_freeze_control_trigger_rate": 0.0,
                    "injected_mean_abs_z_gain_ci95": [0.2, 1.2],
                },
            },
            "synthetic_controls": {"gates": {"all_pass": True}},
        }
        assessment = _assess_candidate_operational_eligibility(candidate)
        self.assertFalse(assessment["adequate_injection_support"])
        self.assertFalse(assessment["eligible_for_further_operational_validation"])

    def test_candidate_passes_only_with_bilateral_sufficient_support(self):
        candidate = {
            "passes_5pct_series_alarm_screen": True,
            "injection_records": {
                "negative_6.0sigma": [{"raw_injected_alarm": True}] * 12,
                "positive_6.0sigma": [{"raw_injected_alarm": True}] * 11,
            },
            "injections": {
                "negative_6.0sigma": {
                    "injected_trigger_time_match_rate": 1.0,
                    "confirmation_freeze_control_trigger_rate": 0.0,
                    "injected_mean_abs_z_gain_ci95": [0.1, 1.0],
                },
                "positive_6.0sigma": {
                    "injected_trigger_time_match_rate": 1.0,
                    "confirmation_freeze_control_trigger_rate": 0.0,
                    "injected_mean_abs_z_gain_ci95": [0.2, 1.2],
                },
            },
            "synthetic_controls": {"gates": {"all_pass": True}},
        }
        assessment = _assess_candidate_operational_eligibility(candidate)
        self.assertTrue(assessment["eligible_for_further_operational_validation"])

    def test_synthetic_confirmation_controls_detect_transient_and_persistent_shifts(self):
        result = _synthetic_confirmation_controls(64.0)
        self.assertTrue(result["gates"]["no_freeze_on_stable_noise"])
        self.assertTrue(result["gates"]["no_mean_freeze_on_variance_only"])
        self.assertTrue(result["gates"]["transient_episode_released"])
        self.assertTrue(result["gates"]["persistent_episode_remains_frozen"])

    def test_freeze_trigger_time_equals_the_rolling_cusum_alarm(self):
        onset = "2024"
        source = make_series(shift_from=24, shift=2.0)
        rolling, _ = build_policy_residuals(
            source,
            policy="rolling_baseline_rolling_scale",
            time_unit="years",
        )
        confirmation, diagnostics = build_policy_residuals(
            source,
            policy="confirmation_freeze_baseline_rolling_scale",
            time_unit="years",
            freeze_trigger_after_time=onset,
            confirmation_k=0.5,
            confirmation_h=8.5,
        )
        rolling_alarm = _first_cusum_alarm(rolling, onset=onset, h=8.5)
        freeze_trigger_times = [
            row["event_time"] for row in confirmation if row.get("freeze_trigger")
        ]
        self.assertIsNotNone(rolling_alarm)
        self.assertEqual(freeze_trigger_times[0], rolling_alarm["event_time"])
        self.assertEqual(diagnostics["freeze_trigger_count"], len(freeze_trigger_times))
        trigger_index = next(
            index for index, row in enumerate(confirmation) if row.get("freeze_trigger")
        )
        self.assertFalse(confirmation[trigger_index]["freeze_active"])
        self.assertTrue(confirmation[trigger_index + 1]["freeze_active"])

    def test_no_freeze_can_begin_before_the_injection_gate(self):
        onset = "2024"
        source = make_series(shift_from=18, shift=2.0)
        rows, diagnostics = build_policy_residuals(
            source,
            policy="confirmation_freeze_baseline_rolling_scale",
            time_unit="years",
            freeze_trigger_after_time=onset,
            confirmation_k=0.5,
            confirmation_h=8.5,
        )
        pre_onset = [
            row for row in rows
            if int(row["event_time"]) < int(onset)
        ]
        self.assertTrue(pre_onset)
        self.assertFalse(any(row.get("freeze_trigger") for row in pre_onset))
        self.assertFalse(any(row.get("freeze_active") for row in pre_onset))
        self.assertGreaterEqual(diagnostics["freeze_trigger_count"], 0)

    def test_paired_post_trigger_metric_measures_persistence_not_detection(self):
        rolling = []
        frozen = []
        for year, raw_z, freeze_z, active in (
            (2022, 0.8, 2.5, True),
            (2023, 0.4, 2.2, True),
            (2024, 0.2, 1.8, True),
        ):
            for target, z, is_active in (
                (rolling, raw_z, False),
                (frozen, freeze_z, active),
            ):
                target.append({
                    "entity_id": "entity-confirm",
                    "metric_id": "output",
                    "event_time": str(year),
                    "z_score": z,
                    "status": "ready",
                    "freeze_active": is_active,
                    "freeze_released": False,
                })
        result = _paired_post_trigger_metrics(
            rolling,
            frozen,
            trigger_time="2021",
            direction=1,
        )
        self.assertEqual(result["post_trigger_periods"], 3)
        self.assertGreater(result["mean_abs_z_gain_frozen_minus_rolling"], 0.0)
        self.assertEqual(result["freeze_active_periods"], 3.0)
        self.assertFalse(result["freeze_released"])

    def test_gap_or_unready_periods_are_not_counted_as_persistence(self):
        rolling = [{
            "entity_id": "entity-confirm", "metric_id": "output",
            "event_time": str(year), "z_score": 0.2, "status": "ready",
        } for year in (2022, 2023, 2024)]
        frozen = [dict(row) for row in rolling]
        frozen[1]["status"] = "gap_unresolved"
        frozen[1]["z_score"] = None
        result = _paired_post_trigger_metrics(
            rolling, frozen, trigger_time="2021", direction=1
        )
        self.assertEqual(result["post_trigger_periods"], 2)


if __name__ == "__main__":
    unittest.main()

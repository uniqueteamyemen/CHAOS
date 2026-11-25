from __future__ import annotations

import json
import unittest

from chaos_governance_kernel.capability_envelope import (
    CAPABILITIES,
    CapabilityViolation,
    assess_capability,
    envelope_document,
    envelope_sha256,
    require_capability,
)


class CapabilityEnvelopeTests(unittest.TestCase):
    def test_envelope_is_deterministic_and_json_serializable(self):
        document = envelope_document()
        rendered = json.dumps(document, sort_keys=True, ensure_ascii=False)
        self.assertTrue(rendered)
        self.assertEqual(envelope_sha256(), envelope_sha256())
        self.assertEqual(document["schema_version"], "1.0.0")

    def test_focus_legacy_single_hit_implementation_is_blocked(self):
        result = assess_capability(
            "FOCuS",
            operation="online_detect",
            intended_role="online_detector",
            observations=200,
            prebreak_observations=80,
            online=True,
            context={"reset_rearm_implemented": False, "per_series_arl_calibrated": False},
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE")
        self.assertIn("RESET_REARM_REQUIRED", result["reason_codes"])
        self.assertIn("PER_SERIES_ARL_CALIBRATION_REQUIRED", result["reason_codes"])
        self.assertTrue(any(x.startswith("IMPLEMENTATION_NOT_READY:") for x in result["reason_codes"]))

    def test_focus_prebreak_minimum_is_enforced(self):
        result = assess_capability(
            "FOCuS",
            operation="online_detect",
            intended_role="online_detector",
            observations=100,
            prebreak_observations=24,
            online=True,
        )
        self.assertIn("PREBREAK_CALIBRATION_SAMPLE_TOO_SHORT", result["reason_codes"])

    def test_focus_cannot_be_called_as_an_offline_segmenter(self):
        result = assess_capability(
            "FOCuS",
            operation="retrospective_segment",
            intended_role="offline_segmenter",
            observations=200,
            prebreak_observations=80,
            online=False,
        )
        self.assertIn("ROLE_MISMATCH", result["reason_codes"])
        self.assertIn("OPERATION_OUTSIDE_ENVELOPE", result["reason_codes"])

    def test_rfpop_is_eligible_only_for_retrospective_segmentation(self):
        allowed = assess_capability(
            "R-FPOP",
            operation="retrospective_segment",
            intended_role="offline_segmenter",
            observations=200,
            online=False,
            context={"known_regimes_count": None},
        )
        self.assertEqual(allowed["status"], "ELIGIBLE")
        self.assertFalse(allowed["requires_known_regimes"])
        denied = assess_capability(
            "R-FPOP",
            operation="online_detect",
            intended_role="online_detector",
            observations=200,
            online=True,
        )
        self.assertEqual(denied["status"], "NOT_ELIGIBLE")
        self.assertIn("RETROSPECTIVE_TOOL_CANNOT_RUN_ONLINE", denied["reason_codes"])

    def test_bocpd_binary_detector_use_is_forbidden(self):
        result = assess_capability(
            "BOCPD",
            operation="online_detect",
            intended_role="online_detector",
            observations=200,
            online=True,
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE")
        self.assertIn("OPERATION_OUTSIDE_ENVELOPE", result["reason_codes"])
        self.assertTrue(result["not_binary"])
        self.assertIn("posterior_run_length_distribution", result["validation_history"][0]["note"] if False else CAPABILITIES["BOCPD"].output_contract)

    def test_bocpd_feature_use_waits_for_full_run_length_distribution_export(self):
        result = assess_capability(
            "BOCPD",
            operation="emit_run_length_features",
            intended_role="feature_generator",
            observations=200,
            online=True,
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE")
        self.assertTrue(any(x.startswith("IMPLEMENTATION_NOT_READY:") for x in result["reason_codes"]))

    def test_bartlett_cannot_be_used_as_a_standalone_detector(self):
        result = assess_capability(
            "Bartlett_LRV",
            operation="emit_alarm",
            intended_role="online_detector",
            observations=40,
            online=True,
            context={"standalone": True},
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE")
        self.assertIn("CALIBRATOR_CANNOT_EMIT_DETECTOR_EVENTS", result["reason_codes"])
        self.assertIn("CALIBRATOR_REQUIRES_PARENT_TOOL", result["reason_codes"])

    def test_bartlett_calibration_requires_an_allowed_parent(self):
        allowed = assess_capability(
            "Bartlett_LRV",
            operation="calibrate_scale",
            intended_role="calibrator",
            observations=40,
            parent_tool="FOCUS_RESET_ARL_PILOT",
            context={"standalone": False},
        )
        self.assertEqual(allowed["status"], "ELIGIBLE")
        denied = assess_capability(
            "Bartlett_LRV",
            operation="calibrate_scale",
            intended_role="calibrator",
            observations=40,
            parent_tool="BOCPD",
        )
        self.assertIn("PARENT_TOOL_NOT_ALLOWED", denied["reason_codes"])

    def test_known_failure_conditions_require_explicit_mitigation(self):
        denied = assess_capability(
            "R-FPOP",
            operation="retrospective_segment",
            intended_role="offline_segmenter",
            observations=100,
            online=False,
            active_failure_conditions=("penalty_misspecification",),
        )
        self.assertIn(
            "KNOWN_FAILURE_CONDITION_UNMITIGATED:penalty_misspecification",
            denied["reason_codes"],
        )
        allowed = assess_capability(
            "R-FPOP",
            operation="retrospective_segment",
            intended_role="offline_segmenter",
            observations=100,
            online=False,
            active_failure_conditions=("penalty_misspecification",),
            mitigated_failure_conditions=("penalty_misspecification",),
        )
        self.assertEqual(allowed["status"], "ELIGIBLE")

    def test_unknown_tool_fails_closed(self):
        result = assess_capability(
            "NEW_UNREGISTERED_TOOL",
            operation="online_detect",
            intended_role="online_detector",
            observations=100,
            online=True,
        )
        self.assertEqual(result["status"], "NOT_ELIGIBLE")
        self.assertEqual(result["reason_codes"], ["UNKNOWN_CAPABILITY"])

    def test_runtime_guard_raises_and_preserves_machine_readable_decision(self):
        with self.assertRaises(CapabilityViolation) as caught:
            require_capability(
                "FOCuS",
                operation="online_detect",
                intended_role="online_detector",
                observations=200,
                prebreak_observations=80,
                online=True,
            )
        self.assertEqual(caught.exception.decision["status"], "NOT_ELIGIBLE")


if __name__ == "__main__":
    unittest.main()

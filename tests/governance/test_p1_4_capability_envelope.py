from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from chaos_governance_kernel.capability_envelope import (
    CapabilityViolation, assess_capability, load_envelope, require_capability
)

ROOT = Path(__file__).resolve().parents[2]


class CapabilityEnvelopeTests(unittest.TestCase):
    def test_envelope_loads_against_json_schema_and_has_ten_contract_fields(self):
        doc = load_envelope()
        self.assertEqual(doc["decision_contract"]["default"], "fail_closed")
        self.assertFalse(doc["decision_contract"]["production_authorization"])
        required = {
            "name", "role", "time_semantics", "allowed_operations", "input_contract",
            "output_contract", "minimum_observations", "restricted_uses",
            "implementation_status", "validation_history"
        }
        for spec in doc["capabilities"].values():
            self.assertTrue(required.issubset(spec))

    def test_c1_manifest_and_cohort_counts_are_pinned(self):
        m = json.loads((ROOT / "p1_4_validation" / "cohort_manifest.json").read_text(encoding="utf-8"))
        c1, c2 = m["cohorts"]["C1"], m["cohorts"]["C2"]
        self.assertEqual((c1["original_count_claimed"], c1["verified_count"]), (147, 147))
        self.assertEqual(c1["criterion_breakdown"]["g1_fail_total"], 147)
        self.assertEqual(c1["discrepancy_severity"], "material")
        self.assertEqual((c2["original_count_claimed"], c2["verified_count"]), (50, 50))
        self.assertEqual(m["pilot_scope"]["series_count"], 40)
        self.assertEqual(m["pilot_scope"]["run_cases"], 760)

    def test_unknown_capability_fails_closed(self):
        d = assess_capability("UNREGISTERED", operation="online_detect", observations=100, online=True)
        self.assertEqual(d["status"], "NOT_ELIGIBLE")
        self.assertEqual(d["reason_codes"], ["UNKNOWN_CAPABILITY"])

    def test_focus_blocked_without_reset_rearm_and_per_series_p0(self):
        d = assess_capability("FOCuS", operation="online_detect", intended_role="online_detector",
                              observations=200, prebreak_observations=80, online=True)
        self.assertEqual(d["status"], "NOT_ELIGIBLE")
        self.assertIn("RESET_REARM_REQUIRED", d["reason_codes"])
        self.assertIn("PER_SERIES_NULL_CALIBRATION_REQUIRED", d["reason_codes"])

    def test_huber_mad_pilot_eligible_only_after_per_series_p0_gate(self):
        args = dict(operation="online_detect", intended_role="online_detector",
                    observations=120, prebreak_observations=40, online=True,
                    context={"per_series_null_calibrated": True,
                             "development_p0_wilson_upper": 0.09,
                             "valid_null_replicates": 1000})
        self.assertEqual(assess_capability("POST_QUIET_HUBER_MAD", **args)["status"], "PILOT_ELIGIBLE")
        args["context"]["development_p0_wilson_upper"] = 0.11
        self.assertIn("PER_SERIES_P0_UPPER_BOUND_EXCEEDS_TARGET",
                      assess_capability("POST_QUIET_HUBER_MAD", **args)["reason_codes"])

    def test_huber_bartlett_is_detector_variant_but_bartlett_is_not_standalone(self):
        args = dict(operation="online_detect", intended_role="online_detector",
                    observations=120, prebreak_observations=40, online=True,
                    context={"per_series_null_calibrated": True,
                             "development_p0_wilson_upper": 0.08,
                             "valid_null_replicates": 1000})
        self.assertEqual(assess_capability("POST_QUIET_HUBER_BARTLETT", **args)["status"], "PILOT_ELIGIBLE")
        d = assess_capability("Bartlett_LRV", operation="emit_alarm", intended_role="online_detector",
                              observations=40, online=True, context={"standalone": True})
        self.assertEqual(d["status"], "NOT_ELIGIBLE")
        self.assertIn("CALIBRATOR_CANNOT_EMIT_DETECTOR_EVENTS", d["reason_codes"])

    def test_bocpd_requires_complete_posterior_export(self):
        args = dict(operation="emit_run_length_features", intended_role="feature_generator",
                    observations=120, prebreak_observations=40, online=True)
        d = assess_capability("BOCPD", **args)
        self.assertIn("FULL_RUN_LENGTH_POSTERIOR_REQUIRED", d["reason_codes"])
        self.assertIn("IMPLEMENTATION_NOT_READY", " ".join(d["reason_codes"]))

    def test_rfpop_is_retrospective_and_requires_frozen_penalty(self):
        args = dict(operation="retrospective_segment", intended_role="offline_segmenter",
                    observations=120, online=False)
        d = assess_capability("R-FPOP", **args)
        self.assertIn("R_FPOP_PENALTY_MUST_BE_FROZEN_BEFORE_HOLDOUT", d["reason_codes"])
        args["context"] = {"penalty_frozen_before_holdout": True}
        d = assess_capability("R-FPOP", **args)
        self.assertEqual(d["status"], "PILOT_ELIGIBLE")
        args["online"] = True
        self.assertIn("RETROSPECTIVE_TOOL_CANNOT_RUN_ONLINE", assess_capability("R-FPOP", **args)["reason_codes"])

    def test_bartlett_requires_allowed_parent(self):
        d = assess_capability("Bartlett_LRV", operation="calibrate_scale",
                              intended_role="calibrator", observations=40,
                              parent_tool="BOCPD", context={"standalone": False})
        self.assertIn("PARENT_TOOL_NOT_ALLOWED", d["reason_codes"])

    def test_eligible_does_not_authorize_production(self):
        args = dict(operation="retrospective_segment", intended_role="offline_segmenter",
                    observations=120, online=False,
                    context={"penalty_frozen_before_holdout": True})
        d = assess_capability("R-FPOP", **args)
        self.assertEqual(d["status"], "PILOT_ELIGIBLE")
        self.assertFalse(d["authorizes_production"])
        self.assertEqual(d["scientific_validation_status"], "PENDING")

    def test_require_capability_raises_for_blocked_runner(self):
        with self.assertRaises(CapabilityViolation):
            require_capability("FOCuS", operation="online_detect", intended_role="online_detector",
                               observations=100, prebreak_observations=40, online=True)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "p1_4_validation" / "pilot_protocol.json"
SCHEMA = ROOT / "p1_4_validation" / "pilot_protocol.schema.json"
MANIFEST = ROOT / "p1_4_validation" / "cohort_manifest.json"


def validate_required(value, schema, path="$"):
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path}:const")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}:enum")
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path}:object")
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ValueError(f"{path}:missing:{sorted(missing)}")
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                validate_required(value[key], child_schema, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path}:array")
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int) or value < schema.get("minimum", 0):
            raise ValueError(f"{path}:integer")
    elif kind == "string" and not isinstance(value, str):
        raise ValueError(f"{path}:string")


def all_strings(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from all_strings(key)
            yield from all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_strings(child)
    elif isinstance(value, str):
        yield value


class P14PilotProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_protocol_version_and_p1_4_engine_lineage(self):
        validate_required(self.protocol, self.schema)
        self.assertEqual(self.protocol["protocol_version"], "1.1.9")
        self.assertEqual(self.protocol["status"], "FROZEN_BEFORE_EXECUTION")
        self.assertTrue(self.protocol["must_not_be_changed_after_pilot_start"])
        lineage = self.protocol["source_and_scope"]["project_lineage"]
        self.assertEqual(lineage["validation_workstream"], "P1.4")
        self.assertEqual(lineage["engine_under_test"], "P2-C")
        self.assertEqual(lineage["engine_reference_commit"], "86cb8e576dc0bd21044743dd2749f5bf1d8899ff")
        self.assertEqual(self.protocol["execution"]["pilot_scope_change"]["actual"], "NOT_STARTED")

    def test_40_series_760_cases_are_selection_only(self):
        manifest_scope = self.manifest["pilot_scope"]
        selected_frame = self.protocol["cohort_design"]["selected_cohort_frame"]
        self.assertEqual((manifest_scope["series_count"], manifest_scope["run_cases"]), (40, 760))
        self.assertEqual(selected_frame["selection_series_count"], 40)
        self.assertEqual(selected_frame["source_selection_case_count"], 760)
        self.assertEqual(selected_frame["status"], "VERIFIED_SELECTION_ARTIFACT_NOT_EXECUTED")
        self.assertEqual(self.protocol["execution"]["pilot_scope_change"]["original_selection_frame"],
                         "40_series_760_selection_cases_C1_C2")

    def test_selection_artifact_is_preserved_as_selection_evidence_only(self):
        artifact = self.manifest["selection_artifact"]
        binding = self.protocol["source_and_scope"]["cohort_selection_binding"]
        self.assertEqual(artifact["workflow_run_id"], binding["selection_workflow_run_id"])
        self.assertEqual(artifact["artifact_id"], binding["selection_artifact_id"])
        self.assertEqual(artifact["artifact_zip_sha256"], binding["selection_artifact_zip_sha256"])
        self.assertEqual(binding["status"], "PRESERVED_HISTORICAL_SELECTION_ARTIFACT")
        self.assertIn("does not prove calibration", binding["interpretation"])

    def test_pilot_scope_is_c1_artifact_eligible_with_no_numeric_cap(self):
        execution = self.protocol["execution"]
        track = execution["diagnostic_tracks"]["track_A"]
        self.assertEqual(track["candidate_series_count"], 20)
        self.assertEqual(track["candidate_strata"], {
            "ADF_PASS_KPSS_FAIL": 12,
            "ADF_FAIL_KPSS_FAIL": 6,
            "ADF_FAIL_KPSS_PASS": 2,
        })
        self.assertEqual(track["cases_per_series"], 19)
        self.assertIsNone(track["eligible_series_count"])
        self.assertIsNone(track["eligible_case_count"])
        self.assertIn("no fixed eligible-series count", track["series_count_policy"].lower())
        self.assertIsNone(track["executed_series_ids"])
        self.assertIsNone(track["executed_case_count"])
        self.assertNotIn("maximum_series_count", track)
        self.assertNotIn("maximum_cases", track)
        self.assertIn("all and only", track["rule"].lower())
        self.assertEqual(execution["pilot_scope_change"]["series_count_policy"], track["series_count_policy"])

    def test_threshold_90_is_unrun_and_threshold_200_is_one_time_stratum_106_only(self):
        extension = self.protocol["execution"]["pre_registered_grid_extension"]
        self.assertEqual(extension["execution_status"], "NOT_RUN")
        self.assertEqual(extension["threshold"], 200)
        self.assertEqual(extension["position_fraction"], 0.30)
        self.assertEqual(extension["threshold_90_baseline"]["status"], "NOT_RUN")
        self.assertEqual(extension["threshold_90_baseline"]["planned_candidate_count"], 20)
        self.assertIsNone(extension["threshold_90_baseline"]["actual_calibrated_count"])
        stratum = extension["stratum_106"]
        self.assertIsNone(stratum["selected_series_count"])
        self.assertIsNone(stratum["selected_series_ids"])
        threshold_200 = stratum["threshold_200_test"]
        self.assertEqual(threshold_200["status"], "NOT_RUN")
        self.assertTrue(threshold_200["planned_once"])
        self.assertEqual(threshold_200["threshold"], 200)
        self.assertIsNone(threshold_200["tested_series_count"])
        self.assertIn("exact position-0.30 development null max-statistics", stratum["max_statistics_reuse"])
        self.assertFalse(extension["allowed_to_repeat"])
        self.assertFalse(extension["threshold_500_tested"])
        self.assertNotIn("stratum_32", extension)
        self.assertNotIn("expected_series_count", stratum)
        self.assertNotIn("expected_series_count", threshold_200)

    def test_rearm_measurement_is_planned_but_not_measured(self):
        measurement = self.protocol["injection_design"]["rearm_overlap_guard"]["empirical_overlap_measurement"]
        self.assertEqual(measurement["status"], "NOT_RUN")
        self.assertEqual(measurement["traces_per_series_per_position"], 1000)
        self.assertEqual(measurement["phase"], "holdout")
        self.assertEqual(measurement["positions"], [0.3, 0.5, 0.7])
        self.assertIsNone(measurement["trace_count"])
        self.assertIsNone(measurement["overlap_trace_count"])
        self.assertIsNone(measurement["overlap_rate"])
        self.assertIsNone(measurement["run_id"])
        self.assertIsNone(measurement["artifact_sha256"])
        self.assertIn("not injected-break recall", measurement["interpretation"])

    def test_injection_and_rearm_contract_remain_40_20_and_min_n_150(self):
        injection = self.protocol["injection_design"]
        self.assertEqual(injection["baseline"]["calibration_observations"], 40)
        self.assertEqual(injection["rearm_quiet_points"], 20)
        self.assertEqual(injection["eligibility"]["min_n_for_focus"], 150)
        guard = injection["rearm_overlap_guard"]
        self.assertEqual(guard["rearm_calibration_observations"], 20)
        self.assertEqual(guard["overlap_outcome"], "INVALID_INJECTION")
        self.assertIn("exclude from recall", guard["recall_accounting"])

    def test_track_b_contains_only_artifact_derived_noncalibratable_c1_candidates(self):
        track = self.protocol["execution"]["track_b_protocol"]
        self.assertTrue(track["no_injections"])
        self.assertTrue(track["no_parameter_changes"])
        self.assertEqual(track["status"], "PRE_REGISTERED_DIAGNOSTIC_ONLY_NOT_RUN")
        self.assertIn("Exact IDs and counts come from the original threshold-calibration artifacts", track["targets"])
        self.assertIn("Artifact-derived calibration status only", track["selection_source"])
        names = {row["name"] for row in track["measurements"]}
        self.assertIn("GARCH(1,1)", names)
        self.assertIn("FOCuS null-statistic distribution", names)
        self.assertIn("Historical-break candidates", names)
        self.assertNotIn("Calibrated comparison", names)

    def test_c2_is_preserved_as_generalization_reference_not_executed_in_c1_scope(self):
        c2 = self.protocol["cohort_design"]["C2"]
        self.assertEqual(c2["sampling_frame_count"], 362)
        self.assertIn("No C2 performance conclusion", c2["scope_note"])
        self.assertIn("C2 remains a preserved generalization reference", self.protocol["execution"]["pilot_start_gate"])

    def test_protocol_has_no_revoked_scope_fields_or_comparison_residue(self):
        serialized = json.dumps(self.protocol, sort_keys=True).lower()
        for residue in (
            "maximum_series_count",
            "maximum_cases",
            "expected_series_count",
            "grid_extension_stratum_32",
            "pre_registered_grid_extension_stratum_32",
            "11 calibrated",
            "measured_calibrated_pilot_overlap",
            "calibrated comparison",
            "cptotsaxn:sur",
            "protocol 1.1.3",
        ):
            self.assertNotIn(residue, serialized)
        extension = self.protocol["execution"]["pre_registered_grid_extension"]
        self.assertEqual(set(extension), {
            "purpose", "execution_status", "threshold", "position_fraction",
            "pre_registered", "allowed_to_repeat", "threshold_500_tested",
            "threshold_90_baseline", "stratum_106", "decision_rule"
        })

    def test_c1_selected_sample_evidence_cannot_be_full_validation_or_rejection(self):
        decision = self.protocol["decision_rules"]["cohort_decisions"]["C1_SELECTED_SAMPLE_EVIDENCE"]
        serialized = " ".join(all_strings(decision)).lower()
        self.assertIn("must not be labeled validated or locked_rejected", serialized)
        self.assertIn("must not claim c2 validation", serialized)


if __name__ == "__main__":
    unittest.main()

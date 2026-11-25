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

    def test_protocol_matches_schema_and_is_unstarted(self):
        validate_required(self.protocol, self.schema)
        self.assertEqual(self.protocol["protocol_version"], "1.1.9")
        self.assertEqual(self.protocol["status"], "FROZEN_BEFORE_EXECUTION")
        self.assertTrue(self.protocol["must_not_be_changed_after_pilot_start"])
        self.assertEqual(self.protocol["execution"]["pilot_scope_change"]["actual"], "NOT_STARTED")

    def test_40_series_760_cases_are_selection_only_not_pilot_execution(self):
        manifest_scope = self.manifest["pilot_scope"]
        selected_frame = self.protocol["cohort_design"]["selected_cohort_frame"]
        self.assertEqual((manifest_scope["series_count"], manifest_scope["run_cases"]), (40, 760))
        self.assertEqual(selected_frame["selection_series_count"], 40)
        self.assertEqual(selected_frame["source_selection_case_count"], 760)
        self.assertEqual(selected_frame["status"], "VERIFIED_SELECTION_ARTIFACT_NOT_EXECUTED")
        track_a = self.protocol["execution"]["diagnostic_tracks"]["track_A"]
        self.assertEqual(track_a["maximum_series_count"], 15)
        self.assertEqual(track_a["maximum_cases"], 285)
        self.assertEqual(track_a["eligible_series_count"], None)

    def test_pilot_is_c1_only_and_never_exceeds_15_series(self):
        execution = self.protocol["execution"]
        track_a = execution["diagnostic_tracks"]["track_A"]
        self.assertEqual(track_a["candidate_series_count"], 20)
        self.assertEqual(track_a["candidate_strata"], {
            "ADF_PASS_KPSS_FAIL": 12,
            "ADF_FAIL_KPSS_FAIL": 6,
            "ADF_FAIL_KPSS_PASS": 2,
        })
        self.assertIn("C1-only", track_a["rule"])
        self.assertIn("No C2", execution["pilot_start_gate"])
        self.assertEqual(execution["implementation_time_budget"]["partial_fallback"]["status"], "NOT_RUN")

    def test_threshold_90_is_not_run_and_threshold_200_is_one_time_stratum_106_only(self):
        extension = self.protocol["execution"]["pre_registered_grid_extension"]
        self.assertEqual(extension["execution_status"], "NOT_RUN")
        self.assertEqual(extension["threshold"], 200)
        self.assertEqual(extension["position_fraction"], 0.30)
        self.assertEqual(extension["threshold_90_baseline"]["status"], "NOT_RUN")
        self.assertEqual(extension["threshold_90_baseline"]["planned_series_count"], 20)
        self.assertEqual(extension["stratum_106"]["expected_series_count"], 7)
        threshold_200 = extension["stratum_106"]["threshold_200_test"]
        self.assertEqual(threshold_200["status"], "NOT_RUN")
        self.assertIsNone(threshold_200["actual_series_count"])
        self.assertTrue(threshold_200["planned_once"])
        self.assertIn("Reuse the exact", extension["stratum_106"]["max_statistics_reuse"])
        self.assertFalse(extension["allowed_to_repeat"])
        self.assertFalse(extension["threshold_500_tested"])
        self.assertNotIn("stratum_32", extension)

    def test_rearm_measurement_has_no_unverified_rate(self):
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

    def test_track_b_contains_only_artifact_derived_noncalibratable_c1_series(self):
        track = self.protocol["execution"]["track_b_protocol"]
        self.assertTrue(track["no_injections"])
        self.assertTrue(track["no_parameter_changes"])
        self.assertEqual(track["status"], "PRE_REGISTERED_DIAGNOSTIC_ONLY_NOT_RUN")
        self.assertIn("Exact IDs and counts must be derived", track["targets"])
        self.assertIn("Artifact-derived calibration status only", track["selection_source"])
        names = {row["name"] for row in track["measurements"]}
        self.assertIn("GARCH(1,1)", names)
        self.assertIn("FOCuS null-statistic distribution", names)
        self.assertIn("Historical-break candidates", names)
        self.assertNotIn("Calibrated comparison", names)

    def test_c2_is_preserved_as_reference_not_used_in_partial_pilot(self):
        c2 = self.protocol["cohort_design"]["C2"]
        self.assertEqual(c2["sampling_frame_count"], 362)
        self.assertIn("No C2 performance conclusion", c2["scope_note"])
        track_a = self.protocol["execution"]["diagnostic_tracks"]["track_A"]
        self.assertIn("C1-only", track_a["rule"])

    def test_unverifiable_historical_numeric_claims_are_absent(self):
        text = " ".join(all_strings(self.protocol)).lower()
        forbidden = (
            "11 calibrated",
            "seven original stratum-106",
            "16_series_304_cases",
            "measured_calibrated_pilot_overlap",
            "gem:cptotsaxn:sur",
            "protocol 1.1.3",
            "stratum_32",
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, text)

    def test_partial_c1_evidence_cannot_be_full_validation_or_rejection(self):
        decision = self.protocol["decision_rules"]["cohort_decisions"]["C1_ONLY_PARTIAL"]
        text = " ".join(all_strings(decision)).lower()
        self.assertIn("must not be labeled validated", text)
        self.assertIn("must not be labeled locked_rejected", text)
        self.assertIn("must not claim c2 validation", text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "p1_4_validation" / "pilot_protocol.json"
SCHEMA = ROOT / "p1_4_validation" / "pilot_protocol.schema.json"


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


class P14PilotProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_protocol_matches_schema_and_is_frozen(self):
        validate_required(self.protocol, self.schema)
        self.assertEqual(self.protocol["status"], "FROZEN_BEFORE_EXECUTION")
        self.assertTrue(self.protocol["must_not_be_changed_after_pilot_start"])

    def test_exact_40_series_and_760_cases_are_bound_to_manifest(self):
        m = json.loads((ROOT / "p1_4_validation" / "cohort_manifest.json").read_text(encoding="utf-8"))
        pilot = m["pilot_scope"]
        self.assertEqual((pilot["series_count"], pilot["run_cases"]), (40, 760))
        self.assertEqual(self.protocol["cohort_design"]["pilot_scope"]["verified_series_count"], 40)
        self.assertEqual(self.protocol["cohort_design"]["pilot_scope"]["total_run_cases"], 760)

    def test_null_p0_and_arl0_are_separate(self):
        n = self.protocol["ar_null_and_calibration"]
        self.assertEqual(n["synthetic_null_fpr"]["target"], 0.10)
        self.assertEqual(n["traces_per_series_per_position"]["development"], 1000)
        self.assertEqual(n["traces_per_series_per_position"]["holdout"], 1000)
        self.assertEqual(n["arl0"]["reference_grid"], [500, 1000, 2000])
        self.assertIn("Never infer P0 from 1/ARL0", n["arl0"]["rule"])

    def test_all_injection_directions_positions_and_magnitudes_are_frozen(self):
        d = self.protocol["injection_design"]
        self.assertEqual(d["magnitudes_sigma"], [0.5, 1.0, 2.0])
        self.assertEqual(d["positions_fraction"], [0.3, 0.5, 0.7])
        self.assertEqual(d["directions"], [-1, 1])
        self.assertEqual(d["injected_case_count_per_series"], 18)
        self.assertEqual(d["total_run_count_per_series_including_original"], 19)

    def test_original_burden_and_null_fpr_are_independent_measures(self):
        m = self.protocol["measurements"]
        self.assertIn("Descriptive burden only", m["original_alarm_burden"]["interpretation"])
        self.assertIn("P0 per series", m["synthetic_null_fpr"])

    def test_cost_delay_is_explicitly_normalized(self):
        c = self.protocol["measurements"]["cost_weighted_diagnostic"]
        self.assertIn("divided by the exact series horizon n", c["normalized_mean_delay"])

    def test_r_fpop_one_to_one_and_penalty_freeze_are_explicit(self):
        r = self.protocol["tool_protocols"]["R-FPOP"]
        self.assertIn("One-to-one assignment", r["matching"]["rule"])
        self.assertIn("Freeze penalty per series before holdout", r["penalty_calibration"]["freeze"])

    def test_bocpd_three_comparison_arms_and_series_level_permutation(self):
        b = self.protocol["tool_protocols"]["BOCPD"]
        self.assertEqual(len(b["comparison_arms"]), 3)
        self.assertEqual(b["incremental_value_test"]["replicates"], 1000)
        self.assertIn("Cohen's dz", b["incremental_value_test"]["effect_size"])

    def test_c3_is_pending_and_never_silently_substituted(self):
        c3 = self.protocol["cohort_design"]["C3"]
        self.assertFalse(c3["included"])
        self.assertTrue(c3["no_substitute_cohort"])


if __name__ == "__main__":
    unittest.main()

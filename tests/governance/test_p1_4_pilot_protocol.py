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
        self.assertEqual(self.protocol["protocol_version"], "1.1.6")
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

    def test_calibration_grids_are_frozen_and_null_paths_are_paired(self):
        n = self.protocol["ar_null_and_calibration"]
        self.assertEqual(n["threshold_grids"]["FOCuS"], [15, 20, 25, 30, 35, 40, 45, 50, 60, 75, 90])
        self.assertEqual(n["threshold_grids"]["POST_QUIET_HUBER_MAD"], [4, 6, 8, 10, 12, 14, 16, 20, 24, 32])
        self.assertIn("MAD and Bartlett variants receive identical paths", n["null_seed_streams"])
        self.assertIn("identical", n["paired_paths_rule"])

    def test_bocpd_is_feature_generator_not_independent_p0_detector(self):
        scope = self.protocol["ar_null_and_calibration"]["traces_per_series_per_position"]["tool_scope"]
        self.assertIn("BOCPD", scope["feature_generator_excluded_from_independent_P0"])
        b = self.protocol["tool_protocols"]["BOCPD"]
        self.assertTrue(b["execution_scope"]["no_independent_detector_role"])
        self.assertIn("250 within-series shuffled controls", b["execution_scope"]["shuffle_diagnostic"])
        self.assertIn("same complete FOCuS null bank", b["execution_scope"]["fusion_null_check"])
        self.assertEqual(b["incremental_value_test"]["replicates"], 1000)

    def test_focus_rearm_overlap_is_invalid_not_false_negative(self):
        d = self.protocol["injection_design"]
        guard = d["rearm_overlap_guard"]
        self.assertEqual(guard["initial_calibration_observations"], 40)
        self.assertEqual(guard["rearm_calibration_observations"], 20)
        self.assertEqual(guard["overlap_outcome"], "INVALID_INJECTION")
        self.assertIn("exclude from recall", guard["recall_accounting"])
        policy = d["guard_window_policy"]
        self.assertEqual(policy["min_observations_between_last_rearm_and_injection"], 20)
        self.assertEqual(self.protocol["injection_design"]["rearm_overlap_guard"]["measured_calibrated_pilot_overlap"]["original_five_stratum_106"]["rate"], 0)
        self.assertEqual(self.protocol["injection_design"]["rearm_overlap_guard"]["measured_calibrated_pilot_overlap"]["extended_eleven_stratum_106"]["rate"], 0)
        self.assertEqual(self.protocol["injection_design"]["rearm_overlap_guard"]["measured_calibrated_pilot_overlap"]["all_fifteen_calibrated_c1"]["rate"], 0)

    def test_focus_minimum_n150_is_explicit(self):
        eligibility = self.protocol["injection_design"]["eligibility"]
        self.assertEqual(eligibility["min_n_for_focus"], 150)
        self.assertIn("NOT_ELIGIBLE", eligibility["below_minimum"])

    def test_c1_pilot_guarantees_all_three_failure_mechanisms(self):
        power = self.protocol["cohort_design"]["C1"]["pre_registered_power_analysis"]
        self.assertEqual(power["stratum_106"]["n_series"], 12)
        self.assertEqual(power["stratum_32"]["n_series"], 6)
        self.assertEqual(power["stratum_9"]["n_series"], 2)
        self.assertIn("anecdotal_must_not_drive_decision", power["stratum_9"]["findings"])
        minimums = self.protocol["cohort_design"]["C1"]["pilot_failure_class_minimums"]
        self.assertEqual(minimums, {
            "ADF_PASS_KPSS_FAIL": 6,
            "ADF_FAIL_KPSS_FAIL": 6,
            "ADF_FAIL_KPSS_PASS": 2,
        })

    def test_c2_report_requires_all_stratification_dimensions(self):
        c2 = self.protocol["cohort_design"]["C2"]
        required = {"source (Pink Sheet vs GEM)", "domain/sector",
                    "observation length band", "pre-injection AR(1) absolute band",
                    "monthly missingness pattern"}
        self.assertTrue(required.issubset(set(c2["stratification_dimensions"])))
        self.assertIn("20-series Pilot subset", c2["stratification_report"])
        frame = c2["sampling_frame_explanation"]
        self.assertEqual(frame["frame_count"], 362)
        self.assertEqual(frame["composition"], {"gem_g1_pass": 311, "pink_sheet": 51})
        self.assertIn("not the full 509-series universe", frame["frame"])

    def test_24_hour_budget_has_partial_pilot_fallback(self):
        budget = self.protocol["execution"]["implementation_time_budget"]
        self.assertEqual(budget["maximum_hours"], 24)
        fallback = budget["partial_fallback"]
        self.assertEqual((fallback["status"], fallback["series_count"],
                          fallback["cases_per_series"], fallback["total_cases"]),
                         ("PILOT_PARTIAL", 15, 19, 285))

    def test_stratum_32_threshold_200_extension_is_once_only_and_pre_registered(self):
        extension = self.protocol["cohort_design"]["C1"]["grid_extension_stratum_32"]
        self.assertTrue(extension["pre_registered"])
        self.assertEqual(extension["test_threshold"], 200)
        self.assertFalse(extension["allowed_to_repeat"])
        self.assertEqual(extension["series"], [
            "gem:CPTOTSAXN:DJI",
            "gem:CPTOTSAXN:ECU",
            "gem:CPTOTSAXN:HKG",
        ])
        self.assertIn("threshold 500", " ".join(extension["forbidden"]))

    def test_track_b_is_pre_registered_no_injection_diagnostic(self):
        track = self.protocol["execution"]["track_b_protocol"]
        self.assertTrue(track["no_injections"])
        names = {row["name"] for row in track["measurements"]}
        self.assertIn("GARCH(1,1)", names)
        self.assertIn("FOCuS null-statistic distribution", names)
        self.assertIn("Historical-break candidates", names)
        self.assertTrue(track["no_post_hoc_changes"])

    def test_pilot_scope_change_is_explicit(self):
        scope = self.protocol["execution"]["pilot_scope_change"]
        self.assertEqual(scope["original"], "40_series_760_cases")
        self.assertIn("not the original 40-series Pilot", scope["note"])

    def test_c3_is_pending_and_never_silently_substituted(self):
        c3 = self.protocol["cohort_design"]["C3"]
        self.assertFalse(c3["included"])
        self.assertTrue(c3["no_substitute_cohort"])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from p1_4_validation import run_arm_isolated_pilot as runner


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "p1_4_validation" / "c1_calibration_artifacts_run_45707752707.json"


class ArmIsolatedPilotTests(unittest.TestCase):
    def test_pinned_source_and_eligibility_cohorts_are_frozen(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_workflow_run_id"], 45707752707)
        self.assertEqual(manifest["source_commit"], "952fa3f2dc724dbeeaaeabfa6d5df620595e9178")
        self.assertEqual(len(manifest["calibration_artifacts"]), 20)
        self.assertEqual(len({x["artifact_id"] for x in manifest["calibration_artifacts"]}), 20)
        self.assertEqual(len({x["series_id"] for x in manifest["calibration_artifacts"]}), 20)
        self.assertEqual(len(manifest["expected_arm_eligibility"]["MAD"]), 8)
        self.assertEqual(len(manifest["expected_arm_eligibility"]["BARTLETT_LRV"]), 13)
        self.assertTrue(set(manifest["expected_arm_eligibility"]["MAD"]).issubset(
            set(manifest["expected_arm_eligibility"]["BARTLETT_LRV"])))
        self.assertFalse(manifest["recalibration_permitted"])
        self.assertFalse(manifest["new_null_trace_generation_permitted"])

    def test_arm_eligibility_is_scale_specific_and_all_positions_required(self):
        rows = {
            "a": {"series_length": 200, "positions": {}},
            "b": {"series_length": 200, "positions": {}},
        }
        for sid in rows:
            rows[sid]["positions"] = {
                key: {"arms": {
                    "POST_QUIET_HUBER_MAD": {"status": "CALIBRATED", "frozen_threshold": 8.0},
                    "POST_QUIET_HUBER_BARTLETT": {"status": "CALIBRATED", "frozen_threshold": 9.0},
                }} for key in ("0.30", "0.50", "0.70")
            }
        rows["b"]["positions"]["0.70"]["arms"]["POST_QUIET_HUBER_MAD"] = {
            "status": "NOT_CALIBRATABLE", "frozen_threshold": None}
        mad, rejected = runner.arm_eligibility(rows, ["a", "b"], "POST_QUIET_HUBER_MAD")
        bartlett, _ = runner.arm_eligibility(rows, ["a", "b"], "POST_QUIET_HUBER_BARTLETT")
        self.assertEqual(mad, ["a"])
        self.assertIn("b", rejected)
        self.assertEqual(bartlett, ["a", "b"])

    def test_holdout_summary_recomputes_wilson_upper_and_flags_cell_failure(self):
        rows = {"series-a": {"positions": {}}}
        for key, alarms in (("0.30", 42), ("0.50", 86), ("0.70", 30)):
            upper = runner.base.wilson_upper(alarms, 1000)
            rows["series-a"]["positions"][key] = {"arms": {
                "POST_QUIET_HUBER_BARTLETT": {
                    "status": "CALIBRATED", "frozen_threshold": 8.0,
                    "holdout": {"status": "ESTIMABLE", "alarm_traces": alarms,
                                "valid_replicates": 1000, "p0": alarms / 1000,
                                "wilson_upper_95_one_sided": upper},
                    "holdout_max_statistics": [9.0] * alarms + [7.0] * (1000 - alarms),
                }
            }}
        result = runner.holdout_p0_table(rows, ["series-a"], "POST_QUIET_HUBER_BARTLETT")
        self.assertEqual(result["cell_count"], 3)
        self.assertEqual(result["total_valid_replicates"], 3000)
        self.assertEqual(result["cells_upper_bound_fail"], 1)
        self.assertEqual(result["status"], "PARTIAL_HOLDOUT_GATE")

    def test_holdout_p0_rejects_mismatch_with_raw_statistics(self):
        alarms = 42
        rows = {"series-a": {"positions": {"0.30": {"arms": {
            "POST_QUIET_HUBER_BARTLETT": {
                "status": "CALIBRATED", "frozen_threshold": 8.0,
                "holdout": {"status": "ESTIMABLE", "alarm_traces": alarms + 1,
                            "valid_replicates": 1000, "p0": (alarms + 1) / 1000,
                            "wilson_upper_95_one_sided": runner.base.wilson_upper(alarms + 1, 1000)},
                "holdout_max_statistics": [9.0] * alarms + [7.0] * (1000 - alarms),
            }
        }}}}}
        with self.assertRaisesRegex(ValueError, "HOLDOUT_P0_RAW_SCORE_COUNT_MISMATCH"):
            runner.holdout_p0_table(rows, ["series-a"], "POST_QUIET_HUBER_BARTLETT")

    def test_bartlett_is_scale_variant_not_separate_detector(self):
        self.assertEqual(runner.SCALE_CONFIG["MAD"]["calibration_arm"], "POST_QUIET_HUBER_MAD")
        self.assertEqual(runner.SCALE_CONFIG["BARTLETT_LRV"]["calibration_arm"], "POST_QUIET_HUBER_BARTLETT")
        self.assertEqual(runner.SCALE_CONFIG["MAD"]["display_name"].split(" / ")[0],
                         runner.SCALE_CONFIG["BARTLETT_LRV"]["display_name"].split(" / ")[0])
        self.assertEqual(runner.SCALE_CONFIG["MAD"]["display_name"].split(" / ")[0],
                         "Post-Quiet Huber")

    def test_no_calibration_or_null_generation_in_arm_runner(self):
        source = (ROOT / "p1_4_validation" / "run_arm_isolated_pilot.py").read_text(encoding="utf-8")
        self.assertNotIn("generate_ar_null_trace(", source)
        self.assertNotIn("calibrate_threshold(", source)


if __name__ == "__main__":
    unittest.main()

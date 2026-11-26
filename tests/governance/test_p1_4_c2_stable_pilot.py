import json
import os
import tempfile
import unittest
from pathlib import Path

from p1_4_validation import run_c2_stable_pilot as runner

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "p1_4_validation" / "cohort_manifest.json"
EXPECTED_C2 = {
    "gem:CPTOTSAXN:DEU", "gem:CPTOTSAXN:IRL",
    "gem:DXGSRMRCHNSKD:BRA", "gem:DXGSRMRCHNSKD:DEV",
    "gem:DXGSRMRCHNSKD:GRC", "gem:DXGSRMRCHNSKD:HIY",
    "gem:DXGSRMRCHNSKD:LAP", "gem:DXGSRMRCHSAXD:AME",
    "gem:DXGSRMRCHSAXD:FIN", "gem:DXGSRMRCHSAXD:LAP",
    "gem:IPTOTSAKD:AZE", "gem:IPTOTSAKD:EST",
    "gem:IPTOTSAKD:IRQ", "gem:IPTOTSAKD:OMN",
    "gem:IPTOTSAKD:SVN", "gem:IPTOTSAKD:TUN",
    "gem:IPTOTSAKD:VNM", "pink:DAP", "pink:Fish_meal",
    "pink:Soybean_oil",
}


def _calibration_row(sid, fail_cell=None):
    positions = {}
    for pos in runner.POSITIONS:
        key = f"{pos:.2f}"
        positions[key] = {"arms": {}}
        for tool, (arm_name, _mode) in runner.TOOLS.items():
            raw = [0.0] * 1000
            if fail_cell == (tool, key):
                raw[:100] = [9.0] * 100
            else:
                raw[:50] = [9.0] * 50
            threshold = 8.0
            holdout = runner.base.p0_result(raw, threshold)
            positions[key]["arms"][arm_name] = {
                "status": "CALIBRATED",
                "frozen_threshold": threshold,
                "holdout": holdout,
                "holdout_max_statistics": raw,
            }
    return {
        "series_id": sid, "cohort": "C2", "calibration_status": "COMPLETE",
        "positions": positions,
    }


class C2StablePilotTests(unittest.TestCase):
    def test_exact_frozen_c2_pilot_ids_are_20_and_not_replaced(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        ids = set(manifest["cohorts"]["C2"]["pilot_series_ids"])
        self.assertEqual(ids, EXPECTED_C2)
        self.assertEqual(len(ids), 20)
        self.assertEqual(manifest["cohorts"]["C2"]["status"], "VERIFIED")
        self.assertEqual(manifest["cohorts"]["C2"]["focus_eligibility"]["not_eligible_ids"],
                         ["gem:IPTOTSAKD:AZE"])
        self.assertEqual(manifest["cohorts"]["C2"]["focus_eligibility"]["eligible_count"], 19)

    def test_frozen_protocol_and_engine_fingerprints_are_pinned(self):
        self.assertEqual(runner.EXPECTED_PROTOCOL_VERSION, "1.1.9")
        self.assertEqual(runner.EXPECTED_PROTOCOL_GIT_BLOB,
                         "2ad0db0654bd1d9dd42c87c5cdb531f9b2aa3a2d")
        self.assertEqual(runner.EXPECTED_COHORT_MANIFEST_GIT_BLOB,
                         "2a9ca14b501567f06840d047597d3a24398c31f2")
        self.assertEqual(runner.EXPECTED_BASE_PIPELINE_GIT_BLOB,
                         "9036a939a41ee4d4b43aa5ad4ae22461f8504aa2")
        self.assertEqual(runner.EXPECTED_INJECTION_RUNNER_GIT_BLOB,
                         "84144451b8fc26556a614dbc3e986987fd4ca236")
        self.assertEqual(runner.EXPECTED_P2C_ENGINE_GIT_BLOB,
                         "5efcf408822551e00cb87c24e39502dcf0ed595a")
        self.assertEqual(runner.EXPECTED_PROTOCOL_SHA256,
                         "d4ce2b84ade5d8662e22b4cdc020f0f39a88566aced3eff1bfefd478b75645e4")

    def test_mad_bartlett_and_focus_holdout_cells_recompute_wilson_gate(self):
        ids = sorted(EXPECTED_C2)
        rows = {
            sid: _calibration_row(
                sid,
                fail_cell=("POST_QUIET_HUBER_BARTLETT", "0.50") if sid == ids[0] else None,
            )
            for sid in ids
        }
        summary, cells = runner.calibration_and_holdout(rows)
        self.assertEqual(summary["POST_QUIET_HUBER_MAD"]["fully_calibrated_series"], 20)
        self.assertEqual(summary["POST_QUIET_HUBER_MAD"]["holdout_pass_cells"], 60)
        self.assertEqual(summary["POST_QUIET_HUBER_MAD"]["holdout_fail_cells"], 0)
        self.assertEqual(summary["POST_QUIET_HUBER_MAD"]["holdout_gate"], "PASS")
        self.assertEqual(summary["POST_QUIET_HUBER_BARTLETT"]["holdout_fail_cells"], 1)
        self.assertEqual(summary["POST_QUIET_HUBER_BARTLETT"]["holdout_gate"], "PARTIAL_OR_INCONCLUSIVE")
        failed = [row for row in cells if row["tool"] == "POST_QUIET_HUBER_BARTLETT" and row["gate"] == "FAIL"]
        self.assertEqual(len(failed), 1)
        self.assertGreater(failed[0]["wilson_upper_95_one_sided"], 0.10)

    def test_zero_valid_holdout_replicates_are_inconclusive_not_fatal(self):
        row = _calibration_row(sorted(EXPECTED_C2)[0])
        arm = row["positions"]["0.30"]["arms"]["POST_QUIET_HUBER_MAD"]
        arm["holdout_max_statistics"] = []
        arm["holdout"] = runner.base.p0_result([], arm["frozen_threshold"])
        summary, cells = runner.calibration_and_holdout({row["series_id"]: row})
        cell = next(x for x in cells if x["tool"] == "POST_QUIET_HUBER_MAD")
        self.assertEqual(cell["valid_replicates"], 0)
        self.assertIsNone(cell["p0"])
        self.assertIsNone(cell["wilson_upper_95_one_sided"])
        self.assertEqual(cell["gate"], "INCONCLUSIVE")

    def test_holdout_raw_statistics_mismatch_fails_closed(self):
        row = _calibration_row(sorted(EXPECTED_C2)[0])
        arm = row["positions"]["0.30"]["arms"]["POST_QUIET_HUBER_MAD"]
        arm["holdout"]["alarm_traces"] += 1
        with self.assertRaisesRegex(ValueError, "C2_HOLDOUT_RAW_COUNT_MISMATCH"):
            runner.calibration_and_holdout({row["series_id"]: row})

    def test_calibration_job_manifest_binds_series_file_sha256(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            ids = sorted(EXPECTED_C2)
            ctx = {
                "c2_ids": ids,
                "candidate_hashes": {sid: f"candidate-{i}" for i, sid in enumerate(ids)},
                "source_sha256": {"protocol": "frozen-protocol", "prepared_zip": "frozen-prepared"},
            }
            series_paths = {}
            for index, sid in enumerate(ids):
                row = {
                    "series_id": sid,
                    "cohort": "C2",
                    "candidate_sha256": ctx["candidate_hashes"][sid],
                    "protocol_sha256": ctx["source_sha256"]["protocol"],
                    "source_sha256": {"prepared_zip": ctx["source_sha256"]["prepared_zip"]},
                    "calibration_status": "COMPLETE",
                }
                series_path = folder / f"series-{runner.base.safe_id(sid)}.json"
                runner.base.write_json(series_path, row)
                series_paths[sid] = series_path
                job_dir = folder / f"job-{index}"
                job_dir.mkdir()
                # Each matrix artifact has its own directory and paired manifest.
                series_path.replace(job_dir / series_path.name)
                series_paths[sid] = job_dir / series_path.name
                runner.base.write_json(job_dir / "calibration_job_manifest.json", {
                    "artifact_type": "P1_4_C2_CALIBRATION_JOB",
                    "cohort": "C2",
                    "series_id": sid,
                    "candidate_sha256": ctx["candidate_hashes"][sid],
                    "status": "COMPLETE",
                    "artifact_sha256": runner.base.sha_file(series_paths[sid]),
                    "source_commit": os.environ.get("GITHUB_SHA"),
                    "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
                    "protocol_sha256": ctx["source_sha256"]["protocol"],
                    "runner_sha256": runner.base.sha_file(Path(runner.__file__)),
                })
            loaded = runner.load_calibrations(folder, ctx)
            self.assertEqual(len(loaded), 20)
            first = series_paths[ids[0]]
            first.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "C2_CALIBRATION_SERIES_SHA_MISMATCH"):
                runner.load_calibrations(folder, ctx)

    def test_directional_recall_pre_onset_and_invalid_cases_are_separated(self):
        def make_case(direction, status, pre_onset=0, wrong_direction=0):
            return {
                "direction": direction,
                "tool_outcomes": {
                    "FOCUS": {
                        "status": status,
                        "pre_onset_alert_count": pre_onset,
                        "wrong_direction_alert_count": wrong_direction,
                    },
                    "POST_QUIET_HUBER_MAD": {"status": "NOT_ELIGIBLE"},
                    "POST_QUIET_HUBER_BARTLETT": {"status": "NOT_ELIGIBLE"},
                },
            }

        cases = [
            make_case(1, "DETECTED", pre_onset=1),
            make_case(1, "MISSED"),
            make_case(-1, "DETECTED", wrong_direction=2),
            make_case(-1, "INVALID_INJECTION", pre_onset=1),
        ]
        pilot = {"series": {"stable-series": {
            "series_length": 200, "executed_injection_cases": cases,
        }}}
        metrics = runner.summarize_pilot(pilot)["FOCUS"]
        self.assertEqual(metrics["planned"], 4)
        self.assertEqual(metrics["tp"], 2)
        self.assertEqual(metrics["miss"], 1)
        self.assertEqual(metrics["invalid"], 1)
        self.assertAlmostEqual(metrics["positive_recall"], 0.5)
        self.assertAlmostEqual(metrics["negative_recall"], 1.0)
        self.assertAlmostEqual(metrics["recall"], 2 / 3)
        self.assertEqual(metrics["pre_onset_cases"], 2)
        self.assertEqual(metrics["pre_onset_events"], 2)
        self.assertAlmostEqual(metrics["pre_onset_rate"], 0.5)
        self.assertEqual(metrics["wrong_direction_events"], 2)

    def test_short_focus_series_is_not_counted_as_detector_miss(self):
        values = [float(x) for x in range(132)]
        result = runner.base.focus_reset_rearm(values, threshold=90.0)
        self.assertEqual(result["status"], "NOT_ELIGIBLE")
        self.assertEqual(result["reason"], "FOCUS_MIN_N_150_REQUIRED")


if __name__ == "__main__":
    unittest.main()

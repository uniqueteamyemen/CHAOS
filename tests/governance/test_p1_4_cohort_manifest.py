from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "cohorts" / "p1_4" / "cohort_manifest.json"
PROTOCOL_PATH = ROOT / "cohorts" / "p1_4" / "pilot_protocol.json"


class P14CohortManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        cls.c1 = cls.manifest["cohorts"]["C1"]
        cls.c2 = cls.manifest["cohorts"]["C2"]
        cls.c3 = cls.manifest["cohorts"]["C3"]
        cls.pilot = cls.manifest["pilot_scope"]
        cls.selection = cls.manifest["selection_artifact"]

    def test_c1_is_verified_against_g1_composite_rule(self):
        ids = self.c1["series_ids"]
        self.assertEqual(self.c1["status"], "VERIFIED")
        self.assertEqual(self.c1["original_count_claimed"], 147)
        self.assertEqual(self.c1["verified_count"], 147)
        self.assertEqual(len(ids), 147)
        self.assertEqual(len(set(ids)), 147)
        breakdown = self.c1["criterion_breakdown"]
        self.assertEqual(breakdown["g1_fail_total"], 147)
        self.assertEqual(breakdown["adf_pass_kpss_fail"], 106)
        self.assertEqual(breakdown["adf_fail_kpss_fail"], 32)
        self.assertEqual(breakdown["adf_fail_kpss_pass"], 9)

    def test_c1_pilot_is_20_members_and_preserves_failure_class_quotas(self):
        population = set(self.c1["series_ids"])
        pilot = self.c1["pilot_series_ids"]
        self.assertEqual(self.c1["pilot_sample_count"], 20)
        self.assertEqual(len(pilot), 20)
        self.assertEqual(len(set(pilot)), 20)
        self.assertTrue(set(pilot).issubset(population))
        self.assertEqual(self.c1["pilot_failure_class_counts"], {
            "ADF_PASS_KPSS_FAIL": 14,
            "ADF_FAIL_KPSS_FAIL": 4,
            "ADF_FAIL_KPSS_PASS": 2,
        })

    def test_c2_is_verified_50_series_from_exact_non_c1_complement_frame(self):
        ids = self.c2["series_ids"]
        self.assertEqual(self.c2["status"], "VERIFIED")
        self.assertEqual(self.c2["original_count_claimed"], 50)
        self.assertEqual(self.c2["verified_count"], 50)
        self.assertEqual(self.c2["sampling_frame_count"], 362)
        self.assertEqual(self.c2["sampling_frame_source_counts"], {"pink_sheet": 51, "gem": 311})
        self.assertEqual(self.c2["sample_source_counts"], {"pink_sheet": 7, "gem": 43})
        self.assertEqual(len(ids), 50)
        self.assertEqual(len(set(ids)), 50)
        self.assertTrue(set(ids).isdisjoint(set(self.c1["series_ids"])))

    def test_c2_pilot_is_20_members_and_subset_of_frozen_sample(self):
        sample = set(self.c2["series_ids"])
        pilot = self.c2["pilot_series_ids"]
        self.assertEqual(self.c2["pilot_sample_count"], 20)
        self.assertEqual(self.c2["pilot_source_counts"], {"pink_sheet": 3, "gem": 17})
        self.assertEqual(len(pilot), 20)
        self.assertEqual(len(set(pilot)), 20)
        self.assertTrue(set(pilot).issubset(sample))

    def test_pilot_union_is_exact_40_disjoint_series_and_760_cases(self):
        c1_pilot = set(self.c1["pilot_series_ids"])
        c2_pilot = set(self.c2["pilot_series_ids"])
        union = sorted(c1_pilot | c2_pilot)
        self.assertEqual(c1_pilot.intersection(c2_pilot), set())
        self.assertEqual(self.pilot["series_count"], 40)
        self.assertEqual(self.pilot["run_cases_per_series"], 19)
        self.assertEqual(self.pilot["run_cases"], 760)
        self.assertEqual(self.pilot["series_ids"], union)
        self.assertFalse(self.pilot["C3_included"])

    def test_selection_artifact_and_protocol_are_immutable_inputs(self):
        self.assertEqual(self.selection["status"], "VERIFIED")
        self.assertEqual(self.selection["workflow_run_id"], 45538866028)
        self.assertEqual(self.selection["artifact_id"], 14988741300)
        self.assertTrue(self.selection["selection_sidecar_verified"])
        protocol_sha = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
        self.assertEqual(self.selection["protocol_sha256"], protocol_sha)
        self.assertEqual(self.protocol["status"], "FROZEN_BEFORE_EXECUTION")
        self.assertEqual(self.protocol["injection_design"]["injected_case_count_per_series"], 18)
        self.assertEqual(self.protocol["injection_design"]["total_run_count_per_series_including_original"], 19)

    def test_c3_remains_pending_until_source_vintage_evidence_exists(self):
        self.assertEqual(self.c3["status"], "PENDING_EXTERNAL_EVIDENCE")
        self.assertEqual(self.pilot["C3_status"], "PENDING_EXTERNAL_EVIDENCE")


if __name__ == "__main__":
    unittest.main()

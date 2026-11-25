import json
import unittest
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "real_data_stress_pipeline"
    / "contracts"
    / "seismic_null_model_contract_v1.json"
)


class SeismicNullContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_is_design_only_not_validated(self):
        self.assertEqual(self.contract["status"], "design_contract_not_yet_validated")
        self.assertFalse(self.contract["scope"]["detector_changes_permitted"])

    def test_event_representations_remain_separate(self):
        cohorts = self.contract["analysis_cohorts"]
        self.assertIn("marked_point_process", cohorts)
        self.assertIn("monthly_counts", cohorts)
        self.assertIn("inter_event_intervals", cohorts)
        self.assertIn("No pooling", cohorts["pooling_policy"])

    def test_etas_requires_fit_diagnostics(self):
        etas = next(x for x in self.contract["null_model_families"] if x["id"] == "N2_HAWKES_ETAS")
        self.assertIn("time_rescaling", " ".join(etas["requirements"] + etas["reject_when"]))
        self.assertEqual(etas["status"], "primary_candidate_subject_to_fit_diagnostics")

    def test_per_replicate_outputs_are_mandatory(self):
        sim = self.contract["simulation"]
        self.assertTrue(sim["preserve_per_replicate_records"])
        self.assertIn("alarm_count", " ".join(sim["required_per_replicate_fields"]))
        self.assertIn("simulated_catalog_sha256", sim["required_per_replicate_fields"])

    def test_fpr_label_is_forbidden_without_ground_truth(self):
        self.assertEqual(
            self.contract["reporting"]["primary_metric_name"],
            "conditional_null_alarm_probability",
        )
        self.assertEqual(
            self.contract["reporting"]["forbidden_metric_name_without_ground_truth"],
            "FPR",
        )


if __name__ == "__main__":
    unittest.main()

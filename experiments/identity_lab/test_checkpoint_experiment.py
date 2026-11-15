"""Tests for durable package-level experiment checkpoints."""
import json, tempfile, unittest
from pathlib import Path
from experiments.identity_lab.checkpoint_experiment import (
    build_checkpoint_record, fingerprint_inputs, input_manifest, is_resumable,
)

class ExperimentCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "results").mkdir()
        (self.root / "src" / "experiment.py").write_text("VERSION = 1\n", encoding="utf-8")
        (self.root / "results" / "result.json").write_text(json.dumps({
            "experiment": "test-package",
            "result": {
                "source": "synthetic", "matched_series_count": 12, "matched_ready_periods": 30,
                "temporal_split": {"null_end": 2020},
                "stationary_bootstrap_null_calibration": {"raw_residuals": {
                    "status": "ok", "series_count": 12,
                    "detectors": {"cusum": [{"passes_all_probabilities": True}]}
                }}
            }
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_fingerprint_is_content_sensitive_and_order_independent(self):
        first = input_manifest(["src/experiment.py"], root=self.root)
        same = input_manifest(["src/experiment.py", "src/experiment.py"], root=self.root)
        self.assertEqual(fingerprint_inputs(first), fingerprint_inputs(same))
        (self.root / "src" / "experiment.py").write_text("VERSION = 2\n", encoding="utf-8")
        changed = input_manifest(["src/experiment.py"], root=self.root)
        self.assertNotEqual(fingerprint_inputs(first), fingerprint_inputs(changed))

    def test_completed_record_requires_tests_run_result_and_artifact(self):
        record = build_checkpoint_record(
            package_id="test-package-v1", inputs=["src/experiment.py"],
            tests_status="success", experiment_status="success",
            result_file="results/result.json", artifact_id="123",
            artifact_digest="sha256:abc", root=self.root
        )
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["result"]["summary"]["matched_series_count"], 12)
        self.assertEqual(len(record["result"]["sha256"]), 64)

    def test_failed_test_or_missing_artifact_stays_incomplete(self):
        record = build_checkpoint_record(
            package_id="test-package-v1", inputs=["src/experiment.py"],
            tests_status="failure", experiment_status="success",
            result_file="results/result.json", root=self.root
        )
        self.assertEqual(record["status"], "incomplete")
        self.assertIn("tests_not_success", record["status_reasons"])
        self.assertIn("artifact_not_uploaded_or_missing_digest", record["status_reasons"])

    def test_resume_requires_same_fingerprint_and_completed_status(self):
        manifest = input_manifest(["src/experiment.py"], root=self.root)
        fingerprint = fingerprint_inputs(manifest)
        path = self.root / "experiments/identity_lab/checkpoints/test-package-v1" / f"{fingerprint}.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 1, "package_id": "test-package-v1",
            "status": "completed", "input_fingerprint": fingerprint}), encoding="utf-8")
        self.assertTrue(is_resumable("test-package-v1", ["src/experiment.py"], root=self.root)[0])
        (self.root / "src" / "experiment.py").write_text("VERSION = 3\n", encoding="utf-8")
        self.assertFalse(is_resumable("test-package-v1", ["src/experiment.py"], root=self.root)[0])

    def test_incomplete_checkpoint_is_not_resumable(self):
        manifest = input_manifest(["src/experiment.py"], root=self.root)
        fingerprint = fingerprint_inputs(manifest)
        path = self.root / "experiments/identity_lab/checkpoints/test-package-v1" / f"{fingerprint}.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 1, "package_id": "test-package-v1",
            "status": "incomplete", "input_fingerprint": fingerprint}), encoding="utf-8")
        ok, reason, _ = is_resumable("test-package-v1", ["src/experiment.py"], root=self.root)
        self.assertFalse(ok)
        self.assertEqual(reason, "checkpoint_not_complete_or_mismatched")

    def test_path_traversal_and_missing_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside_repository"):
            input_manifest(["../escape"], root=self.root)
        with self.assertRaisesRegex(FileNotFoundError, "input_missing"):
            input_manifest(["src/missing.py"], root=self.root)

if __name__ == "__main__":
    unittest.main()

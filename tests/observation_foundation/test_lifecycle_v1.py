import unittest

from observation_foundation.lifecycle_v1 import (
    create_triggered_hypothesis_version,
    transition_hypothesis,
    validate_input_disposition,
)


class HypothesisLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.hypothesis = {
            "hypothesis_id": "PATTERN-017",
            "hypothesis_version": 3,
            "status": "LOCKED_REJECTED",
            "contract_sha256": "a" * 64,
            "epoch_id": "epoch-2026-11",
            "evidence_refs": ["ledger://evidence/17"],
        }

    def test_quarantine_is_not_a_hypothesis_status(self):
        with self.assertRaisesRegex(ValueError, "hypothesis_status_invalid"):
            transition_hypothesis(self.hypothesis, "QUARANTINE")

    def test_locked_rejected_is_immutable_within_its_version(self):
        with self.assertRaisesRegex(ValueError, "hypothesis_transition_forbidden"):
            transition_hypothesis(self.hypothesis, "UNDER_TEST")

    def test_threshold_only_change_cannot_reopen_rejected_hypothesis(self):
        trigger = {
            "kind": "threshold_change",
            "observed_at": "2026-11-19T10:00:00Z",
            "evidence_ref": "ledger://change/threshold-1",
            "description": "only changed threshold from 4.0 to 3.8",
        }
        with self.assertRaisesRegex(ValueError, "threshold_only_change"):
            create_triggered_hypothesis_version(self.hypothesis, trigger)

    def test_documented_source_shift_creates_new_version_and_keeps_old(self):
        trigger = {
            "kind": "source_vintage_changed",
            "observed_at": "2026-11-19T10:00:00Z",
            "evidence_ref": "sha256:source-vintage-2",
            "description": "new source vintage adds backfilled observations and changes completeness window",
        }
        old_copy = dict(self.hypothesis)
        new = create_triggered_hypothesis_version(self.hypothesis, trigger)
        self.assertEqual(new["hypothesis_version"], 4)
        self.assertEqual(new["status"], "CANDIDATE")
        self.assertEqual(new["supersedes"]["previous_status"], "LOCKED_REJECTED")
        self.assertEqual(self.hypothesis, old_copy)

    def test_rejected_can_only_be_locked_not_reopened_in_place(self):
        rejected = dict(self.hypothesis, status="REJECTED")
        locked = transition_hypothesis(rejected, "LOCKED_REJECTED")
        self.assertEqual(locked["status"], "LOCKED_REJECTED")
        with self.assertRaises(ValueError):
            transition_hypothesis(rejected, "CANDIDATE")

    def test_input_quarantine_is_valid_and_independent(self):
        result = validate_input_disposition("input://row/88", "QUARANTINE", "unknown source revision")
        self.assertEqual(result["status"], "QUARANTINE")
        with self.assertRaisesRegex(ValueError, "input_disposition_invalid"):
            validate_input_disposition("input://row/88", "LOCKED_REJECTED", "invalid cross-domain state")


if __name__ == "__main__":
    unittest.main()

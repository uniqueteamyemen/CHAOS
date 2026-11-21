import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from observation_foundation.lifecycle_v1 import (
    append_lifecycle_decision,
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


    def test_threshold_change_cannot_be_disguised_with_data_wording(self):
        trigger = {
            "kind": "threshold_change",
            "observed_at": "2026-11-19T10:00:00Z",
            "evidence_ref": "ledger://change/threshold-2",
            "description": "threshold changed after reviewing new data and source regime",
        }
        with self.assertRaisesRegex(ValueError, "threshold_only_change"):
            create_triggered_hypothesis_version(self.hypothesis, trigger)

    def test_unknown_trigger_kind_is_rejected(self):
        trigger = {
            "kind": "analyst_judgment",
            "observed_at": "2026-11-19T10:00:00Z",
            "evidence_ref": "ledger://change/manual",
            "description": "Analyst believes the hypothesis should be reopened",
        }
        with self.assertRaisesRegex(ValueError, "trigger_shift_kind_invalid"):
            create_triggered_hypothesis_version(self.hypothesis, trigger)

    def test_trigger_timestamp_is_normalized_to_utc(self):
        trigger = {
            "kind": "source_vintage_changed",
            "observed_at": "2026-11-19T13:00:00+03:00",
            "evidence_ref": "sha256:source-vintage-3",
            "description": "provider published a new immutable source vintage",
        }
        new = create_triggered_hypothesis_version(self.hypothesis, trigger)
        self.assertEqual(new["trigger_shift"]["observed_at"], "2026-11-19T10:00:00Z")

    def test_input_and_hypothesis_are_appended_to_one_idempotent_research_ledger(self):
        before = dict(self.hypothesis, status="UNDER_TEST")
        after = transition_hypothesis(before, "DISCOVERED")
        arguments = {
            "input_disposition": {
                "input_ref": "source://wdi/snapshot-2026",
                "status": "ACCEPT",
                "reason": "source vintage and coverage contract verified",
            },
            "hypothesis_before": before,
            "hypothesis_after": after,
            "decision_at_utc": "2026-11-20T10:00:00Z",
            "source_refs": ["source://wdi/snapshot-2026"],
            "input_hashes": {"source://wdi/snapshot-2026": "a" * 64},
            "output_refs": ["pattern://PATTERN-017/v3"],
            "notes": "Discovery candidate entered validation.",
        }
        with TemporaryDirectory() as directory:
            ledger = Path(directory) / "RESEARCH_LEDGER_V1.jsonl"
            first = append_lifecycle_decision(**arguments, ledger_path=ledger)
            second = append_lifecycle_decision(**arguments, ledger_path=ledger)
            records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(first["status"], "appended")
        self.assertEqual(second["status"], "already_recorded")
        self.assertEqual(len(records), 1)
        context = records[0]["decision_context"]
        self.assertEqual(context["input_disposition"]["status"], "ACCEPT")
        self.assertEqual(context["hypothesis_transition"]["status_before"], "UNDER_TEST")
        self.assertEqual(context["hypothesis_transition"]["status_after"], "DISCOVERED")
        self.assertEqual(records[0]["record_type"], "pattern_decision")

    def test_ledger_records_triggered_version_without_reopening_locked_record(self):
        before = dict(self.hypothesis)
        trigger = {
            "kind": "source_vintage_changed",
            "observed_at": "2026-11-20T09:00:00Z",
            "evidence_ref": "sha256:source-vintage-4",
            "description": "Provider published a separately versioned historical vintage.",
        }
        after = create_triggered_hypothesis_version(before, trigger)
        with TemporaryDirectory() as directory:
            ledger = Path(directory) / "RESEARCH_LEDGER_V1.jsonl"
            result = append_lifecycle_decision(
                input_disposition={
                    "input_ref": "source://wdi/vintage-4",
                    "status": "QUARANTINE",
                    "reason": "new vintage requires independent review",
                },
                hypothesis_before=before,
                hypothesis_after=after,
                decision_at_utc="2026-11-20T09:00:00Z",
                source_refs=["source://wdi/vintage-4"],
                input_hashes={"source://wdi/vintage-4": "b" * 64},
                output_refs=[],
                notes="New version opened by documented source-vintage shift.",
                ledger_path=ledger,
            )
            record = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(result["status"], "appended")
        self.assertEqual(record["decision_context"]["input_disposition"]["status"], "QUARANTINE")
        self.assertEqual(record["decision_context"]["hypothesis_transition"]["status_before"], "LOCKED_REJECTED")
        self.assertEqual(record["decision_context"]["hypothesis_transition"]["status_after"], "CANDIDATE")
        self.assertEqual(record["decision_context"]["hypothesis_transition"]["version_after"], 4)
        self.assertIn("supersedes", record["decision_context"]["hypothesis_transition"])

    def test_unknown_trigger_fields_are_rejected(self):
        trigger = {
            "kind": "source_vintage_changed",
            "observed_at": "2026-11-19T10:00:00Z",
            "evidence_ref": "sha256:source-vintage-3",
            "description": "provider published a new immutable source vintage",
            "arrival_order": 3,
        }
        with self.assertRaisesRegex(ValueError, "trigger_shift_fields_invalid"):
            create_triggered_hypothesis_version(self.hypothesis, trigger)


if __name__ == "__main__":
    unittest.main()

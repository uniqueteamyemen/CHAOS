from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from chaos_governance_kernel.domain_state import (
    audit_domain_state_file,
    build_domain_state_integrity_report,
    domain_state_identity,
    validate_domain_state,
)

REQUIRED = [
    "pattern_id", "domain", "entity_id", "entity_name", "timestamp",
    "native_frequency", "state_label", "state_probability", "source_observations",
    "lead_profile", "uncertainty", "failure_cases", "edge_status", "evidence_refs",
]


def state(**changes):
    record = {
        "pattern_id": "TRADE_IMPORT_TOTAL_V1",
        "domain": "trade",
        "entity_id": "124",
        "entity_name": "Canada",
        "timestamp": 2020,
        "native_frequency": "annual",
        "state_label": "trade_import_reported_total_partner",
        "state_probability": None,
        "source_observations": {"primaryValue_raw": 123.0},
        "lead_profile": {},
        "uncertainty": ["bounded preview"],
        "failure_cases": ["no disruption inferred"],
        "edge_status": "not_testable",
        "evidence_refs": ["source://comtrade/124/2020"],
    }
    record.update(changes)
    return record


class DomainStateIntegrityTests(unittest.TestCase):
    def test_valid_state_allows_null_probability_and_preserves_source_metadata(self):
        self.assertEqual(validate_domain_state(state(), REQUIRED, "annual"), [])

    def test_probability_outside_unit_interval_is_rejected(self):
        self.assertIn(
            "state_probability_must_be_null_or_finite_0_to_1",
            validate_domain_state(state(state_probability=1.2), REQUIRED, "annual"),
        )

    def test_boolean_is_not_accepted_as_probability_or_timestamp(self):
        errors = validate_domain_state(state(timestamp=True, state_probability=True), REQUIRED, "annual")
        self.assertIn("timestamp_must_be_native_string_or_integer", errors)
        self.assertIn("state_probability_must_be_null_or_finite_0_to_1", errors)

    def test_native_frequency_must_match_registry(self):
        errors = validate_domain_state(state(native_frequency="monthly"), REQUIRED, "annual")
        self.assertTrue(any(item.startswith("native_frequency_mismatch") for item in errors))

    def test_required_structure_is_enforced(self):
        record = state()
        del record["evidence_refs"]
        record["source_observations"] = []
        errors = validate_domain_state(record, REQUIRED, "annual")
        self.assertTrue(any(item.startswith("required_fields_missing") for item in errors))
        self.assertIn("source_observations_must_be_object", errors)

    def test_identity_ignores_observed_value_but_keys_the_state_slot(self):
        first = state()
        revised = state(source_observations={"primaryValue_raw": 999.0})
        self.assertEqual(domain_state_identity(first), domain_state_identity(revised))

    def test_file_audit_reports_duplicate_slots_without_deduplicating(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "states.jsonl"
            path.write_text(
                json.dumps(state()) + "\n" + json.dumps(state(source_observations={"primaryValue_raw": 999.0})) + "\n",
                encoding="utf-8",
            )
            report = audit_domain_state_file(root, "states.jsonl", REQUIRED, "annual")
        self.assertEqual(report["records"], 2)
        self.assertEqual(report["valid_records"], 2)
        self.assertEqual(report["duplicate_state_slots"], 1)
        self.assertEqual(report["status"], "pass")

    def test_registry_reports_missing_files_as_blocked_not_pass(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "registry.json"
            output_path = root / "report.json"
            existing = root / "present.jsonl"
            existing.write_text(json.dumps(state()) + "\n", encoding="utf-8")
            registry_path.write_text(json.dumps({
                "required_fields": REQUIRED,
                "files": [
                    {"path": "present.jsonl", "native_frequency": "annual"},
                    {"path": "missing.jsonl", "native_frequency": "annual"},
                ],
            }), encoding="utf-8")
            report = build_domain_state_integrity_report(root, registry_path, output_path)
        self.assertEqual(report["readiness"], "BLOCKED_INCOMPLETE_ASSET_SET")
        self.assertEqual(report["records_seen"], 1)
        self.assertIn("missing.jsonl", report["missing_references"])
        self.assertTrue(output_path.exists())

    def test_invalid_jsonl_record_is_a_hard_failure(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "bad.jsonl"
            path.write_text("{not-json}\n", encoding="utf-8")
            report = audit_domain_state_file(root, "bad.jsonl", REQUIRED, "annual")
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["invalid_records"], 1)


if __name__ == "__main__":
    unittest.main()

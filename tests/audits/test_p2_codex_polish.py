import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from real_data_stress_pipeline import run_pipeline as p2
from scripts.audits import p2_2_3_domain_null_and_declustering as audit


class P2CodexPolishTests(unittest.TestCase):
    def test_keep_raw_supports_snapshot_root_outside_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            repository_root = temporary_root / "repo"
            external_raw_root = temporary_root / "external" / "raw"

            with (
                patch.object(p2, "ROOT", repository_root),
                patch.object(p2, "RAW", external_raw_root),
            ):
                record = p2.keep_raw(
                    "source_snapshots/catalog.json",
                    b'{"features":[]}',
                    "USGS ComCat",
                    "https://example.test/catalog",
                )

            expected_path = (external_raw_root / "source_snapshots/catalog.json").resolve()
            self.assertEqual(record["path"], str(expected_path))
            self.assertEqual(expected_path.read_bytes(), b'{"features":[]}')

    def test_seismic_bootstrap_skip_preserves_series_representation(self):
        result = p2.boot(
            np.asarray([1.0, 2.0, 3.0]),
            "seismic-representation-test",
            12,
            {"passed": False, "status": "SCREEN_NOT_APPLICABLE"},
            domain="seismic",
            series_representation="returns",
        )
        self.assertEqual(result["status"], "SKIPPED_DOMAIN_NULL_REQUIRED")
        self.assertEqual(result["series_representation"], "returns")

    def _run_audit_with_stubbed_usgs(self, output_dir, *, events):
        belt = {"id": "codex_polish_test_belt", "name": "Codex polish test belt"}

        def ingest_stub(source_meta):
            source_meta["belts"].append({
                "id": belt["id"],
                "events_received": len(events),
                "events_accepted": len(events),
                "events_quarantined": 0,
                "duplicate_features_deduplicated": 0,
            })
            catalog = p2.DERIVED / f"{belt['id']}_events.csv"
            catalog.parent.mkdir(parents=True, exist_ok=True)
            catalog.write_text("id\n", encoding="utf-8")
            return []

        audit_belt_result = {
            "belt_id": belt["id"],
            "status": "COMPLETED",
            "source_events": len(events),
            "catalog_integrity": {
                "status": "PASS",
                "post_ingest_validation_status": "PASS",
                "accounting_reconciled": True,
            },
        }
        return [
            patch.object(p2, "BELTS", [belt]),
            patch.object(p2, "seismic", side_effect=ingest_stub),
            patch.object(audit, "read_usgs_csv", return_value=events),
            patch.object(audit, "audit_belt", return_value=audit_belt_result),
        ]

    def test_world_bank_failure_does_not_abort_usgs_audit_or_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "audit-output"
            events = [{"id": "event-1", "epoch_ms": 946684800000}]
            patches = self._run_audit_with_stubbed_usgs(output_dir, events=events)
            patches.extend([
                patch.object(
                    audit,
                    "fetch_world_bank_gem",
                    side_effect=RuntimeError("simulated World Bank outage"),
                ),
                patch.object(audit, "fetch_fred", return_value={"status": "SKIPPED_SECRET_MISSING"}),
                patch.object(audit, "fetch_eia", return_value={"status": "SKIPPED_SECRET_MISSING"}),
            ])
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
                result = audit.run_audit(output_dir, poisson_replicates=1)

            summary_path = output_dir / "summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(result["world_bank_gem"]["status"], "ERROR")
            self.assertIn("simulated World Bank outage", result["world_bank_gem"]["error"])
            self.assertEqual(result["seismic_belts"][0]["status"], "COMPLETED")
            self.assertTrue(result["required_source_gate"]["usgs_comcat"])
            self.assertEqual(summary["world_bank_gem"]["status"], "ERROR")

    def test_bounded_pr_gate_rejects_empty_but_integrity_reconciled_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "bounded-audit"
            patches = self._run_audit_with_stubbed_usgs(output_dir, events=[])
            with patches[0], patches[1], patches[2], patches[3]:
                result = audit.run_audit(
                    output_dir,
                    poisson_replicates=1,
                    isolated_usgs_only=True,
                    max_belts=1,
                )

            self.assertEqual(result["seismic_belts"][0]["status"], "COMPLETED")
            self.assertEqual(result["seismic_belts"][0]["source_events"], 0)
            self.assertFalse(result["required_source_gate"]["passed"])
            self.assertTrue((output_dir / "summary.json").exists())

    def test_workflow_dispatch_secrets_are_scoped_to_main_phase2(self):
        repository_root = Path(__file__).resolve().parents[2]
        workflow = (repository_root / ".github" / "workflows" / "real-data-stress.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "github.event_name != 'workflow_dispatch' || github.ref == 'refs/heads/main-phase2'",
            workflow,
        )
        self.assertIn(
            "FRED_API_KEY: ${{ github.ref == 'refs/heads/main-phase2' && secrets.FRED_API_KEY || '' }}",
            workflow,
        )
        self.assertIn(
            "EIA_API_KEY: ${{ github.ref == 'refs/heads/main-phase2' && secrets.EIA_API_KEY || '' }}",
            workflow,
        )

import tempfile
import unittest
from pathlib import Path

from experiments.identity_lab.exp_j_erp.run_public_ledger_shadow_probe import (
    build_public_ledger_bundle,
)
from experiments.identity_lab.exp_j_erp.shadow_mode import run_shadow, write_run


class PublicLedgerShadowProbeTests(unittest.TestCase):
    def test_source_rows_are_pseudonymized_and_links_are_not_invented(self):
        bundle, stats = build_public_ledger_bundle()
        self.assertEqual(stats["source_rows"], 600)
        self.assertEqual(stats["shipments_scored"], 68)
        self.assertEqual(stats["unlinked_inbound_candidate_rows"], 34)
        self.assertTrue(all(x["product_id"].startswith("SKU-") for x in bundle["moves"]))
        self.assertTrue(all("source_picking_id" not in x for x in bundle["receipts"]))
        self.assertTrue(all("recorded_at" not in x for x in bundle["receipts"]))
        self.assertTrue(all("location_id" not in x for x in bundle["moves"]))
        self.assertTrue(all("supplier_id" not in row for row in bundle["moves"]))
        self.assertTrue(all("supplier_id" not in row for row in bundle["receipts"]))
        self.assertFalse(bundle["export_metadata"]["is_odoo_export"])
        self.assertFalse(bundle["export_metadata"]["independent_counterparty_evidence"])

    def test_engines_never_confirm_or_claim_loss_without_independent_receipts(self):
        bundle, _ = build_public_ledger_bundle()
        report = run_shadow(bundle)
        self.assertEqual(report["snapshot"]["moves"], 68)
        self.assertEqual(report["snapshot"]["receipts"], 34)
        for engine in ("A", "B", "C"):
            self.assertEqual(report["engine_summaries"][engine]["confirmed"], 0, engine)
            self.assertEqual(report["engine_summaries"][engine]["loss_claims"], 0, engine)

    def test_report_does_not_label_unverified_candidate_rows_as_independent_receipts(self):
        bundle, _ = build_public_ledger_bundle()
        report = run_shadow(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_run(report, Path(tmp))
            comparison = (folder / "comparison.md").read_text(encoding="utf-8")
        self.assertIn("Source classification: downloaded_public_single_ledger (not an Odoo export)", comparison)
        self.assertIn("Receipt/candidate rows (independence unverified): 34", comparison)
        self.assertNotIn("Independent receipt records: 34", comparison)


if __name__ == "__main__":
    unittest.main()

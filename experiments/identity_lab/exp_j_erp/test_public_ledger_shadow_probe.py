import unittest

from experiments.identity_lab.exp_j_erp.run_public_ledger_shadow_probe import (
    build_public_ledger_bundle,
)
from experiments.identity_lab.exp_j_erp.shadow_mode import run_shadow


class PublicLedgerShadowProbeTests(unittest.TestCase):
    def test_source_rows_are_pseudonymized_and_links_are_not_invented(self):
        bundle, stats = build_public_ledger_bundle()
        self.assertEqual(stats["source_rows"], 600)
        self.assertEqual(stats["shipments_scored"], 68)
        self.assertEqual(stats["unlinked_inbound_candidate_rows"], 34)
        self.assertEqual(bundle["snapshot"] if "snapshot" in bundle else None, None)
        self.assertTrue(all(x["product_id"].startswith("SKU-") for x in bundle["moves"]))
        self.assertTrue(all("source_picking_id" not in x for x in bundle["receipts"]))
        self.assertTrue(all("recorded_at" not in x for x in bundle["receipts"]))
        self.assertTrue(all("location_id" not in x for x in bundle["moves"]))
        self.assertNotIn("supplier_id", str(bundle))
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


if __name__ == "__main__":
    unittest.main()

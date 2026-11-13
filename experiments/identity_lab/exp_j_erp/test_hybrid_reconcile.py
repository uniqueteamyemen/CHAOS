"""Regression tests for the hybrid evidence-gated reconciliation engine."""
import unittest
from decimal import Decimal

from experiments.identity_lab.exp_j_erp.hybrid_reconcile import match_hybrid

UOMS = {
    "unit": {"id": "unit", "category_id": "count", "factor": "1", "uom_type": "reference"},
    "dozen": {"id": "dozen", "category_id": "count", "factor": "0.0833333333333333333333333333", "uom_type": "bigger"},
    "kg": {"id": "kg", "category_id": "weight", "factor": "1", "uom_type": "reference"},
    "g": {"id": "g", "category_id": "weight", "factor": "1000", "uom_type": "smaller"},
}

def shipment(sid="S1", qty="24", product="P1", location="DEST", sender="SRC"):
    return {"picking_id": sid, "product_id": product, "location_id": sender,
            "location_dest_id": location, "from_entity": sender,
            "reference_uom_id": "unit", "product_uom_category_id": "count",
            "quantity": qty, "dates": ["2025-09-01"]}

def receipt(rid="R1", source="S1", qty="2", uom="dozen", product="P1",
            location="DEST", sender="SRC", day="2025-09-02"):
    return {"source_picking_id": source, "counterpart_picking_id": rid,
            "product_id": product, "location_id": location, "from_entity": sender,
            "counterpart_qty": qty, "counterpart_uom_id": uom,
            "product_uom_category_id": "count", "counterpart_date": day,
            "counterpart_system": "receiver", "counterpart_source": "receipt",
            "recorded_at": day + "T10:00:00"}

class HybridReconcileTests(unittest.TestCase):
    def run_match(self, shipments, receipts):
        return match_hybrid(shipments, receipts, UOMS)

    def test_exact_unit_dozen_conversion_and_loss(self):
        row = self.run_match([shipment(qty="30")], [receipt()])[0]
        self.assertEqual(row["state"], "confirmed_exact")
        self.assertTrue(row["qty_received"].startswith("24."))
        self.assertEqual(row["issues"], ["loss"])

    def test_weight_units_kg_and_grams_normalize_to_reference(self):
        s = shipment(qty="1")
        s["reference_uom_id"] = "kg"
        s["product_uom_category_id"] = "weight"
        r = receipt(qty="400", uom="g")
        r["product_uom_category_id"] = "weight"
        row = self.run_match([s], [r])[0]
        self.assertEqual(row["state"], "confirmed_exact")
        self.assertEqual(Decimal(row["qty_received"]), Decimal("0.4"))
        self.assertEqual(row["issues"], ["loss"])

    def test_subthreshold_variance_is_not_a_loss_claim(self):
        row = self.run_match([shipment(qty="24")], [receipt(qty="1.98")])[0]
        self.assertEqual(row["state"], "confirmed_exact")
        self.assertEqual(row["issues"], ["partial_delivery"])

    def test_multiple_explicit_partial_receipts_are_summed(self):
        row = self.run_match([shipment()], [receipt("R1", qty="1"), receipt("R2", qty="1")])[0]
        self.assertEqual(row["state"], "confirmed_exact")
        self.assertEqual(row["receipt_count"], 2)
        self.assertEqual(row["issues"], [])

    def test_approximate_unique_never_confirms_or_claims_loss(self):
        row = self.run_match([shipment()], [receipt(source=None)])[0]
        self.assertEqual(row["state"], "candidate_approximate")
        self.assertFalse(row["confirmed"])
        self.assertFalse(row["loss_claim"])
        self.assertEqual(row["issues"], [])

    def test_multiple_approximate_candidates_are_ambiguous(self):
        row = self.run_match([shipment()], [receipt("R1", source=None), receipt("R2", source=None)])[0]
        self.assertEqual(row["state"], "ambiguous")

    def test_one_approximate_receipt_shared_by_two_shipments_is_ambiguous(self):
        rows = self.run_match(
            [shipment("S1", sender="SRC1"), shipment("S2", sender="SRC2")],
            [receipt(source=None, sender=None)],
        )
        self.assertEqual([row["state"] for row in rows], ["ambiguous", "ambiguous"])
        self.assertTrue(all(row["reason"] == "receipt_candidate_shared_across_shipments"
                            for row in rows))

    def test_receipt_linked_outside_batch_is_not_reassigned(self):
        row = self.run_match([shipment("S1")], [receipt(source="S-OTHER")])[0]
        self.assertEqual(row["state"], "unmatched")
        self.assertEqual(row["candidate_receipt_ids"], [])

    def test_negative_threshold_is_rejected(self):
        with self.assertRaises(ValueError):
            match_hybrid([shipment()], [receipt()], UOMS,
                         loss_classification_threshold=Decimal("-0.1"))

    def test_sender_mismatch_excludes_candidate(self):
        row = self.run_match([shipment()], [receipt(source=None, sender="OTHER")])[0]
        self.assertEqual(row["state"], "unmatched")

    def test_explicit_product_conflict_blocks_confirmation(self):
        row = self.run_match([shipment()], [receipt(product="P2")])[0]
        self.assertEqual(row["state"], "ambiguous")
        self.assertEqual(row["reason"], "explicit_link_conflict_or_receipt_reuse")

    def test_explicit_sender_conflict_blocks_confirmation(self):
        row = self.run_match([shipment()], [receipt(sender="OTHER")])[0]
        self.assertEqual(row["state"], "ambiguous")
        self.assertEqual(row["reason"], "explicit_link_conflict_or_receipt_reuse")

    def test_invalid_shipment_quantity_is_ambiguous_not_a_crash(self):
        row = self.run_match([shipment(qty="-4")], [receipt()])[0]
        self.assertEqual(row["state"], "ambiguous")
        self.assertEqual(row["reason"], "shipment_quantity_invalid")

    def test_incomplete_provenance_blocks_confirmation(self):
        r = receipt()
        r["counterpart_source"] = None
        row = self.run_match([shipment()], [r])[0]
        self.assertEqual(row["state"], "ambiguous")
        self.assertEqual(row["reason"], "receipt_provenance_incomplete")

    def test_duplicate_receipt_id_blocks_confirmation(self):
        row = self.run_match([shipment()], [receipt(), receipt()])[0]
        self.assertEqual(row["state"], "ambiguous")

    def test_one_receipt_cannot_be_reused_by_two_shipments(self):
        rows = self.run_match([shipment("S1"), shipment("S2")], [receipt(source="S1")])
        self.assertEqual(rows[0]["state"], "confirmed_exact")
        self.assertEqual(rows[1]["state"], "unmatched")
        self.assertFalse(rows[1]["confirmed"])
        self.assertNotIn("R1", rows[1]["candidate_receipt_ids"])

    def test_cross_category_uom_is_rejected(self):
        r = receipt()
        r["counterpart_uom_id"] = "kg"
        r["product_uom_category_id"] = "weight"
        row = self.run_match([shipment()], [r])[0]
        self.assertEqual(row["state"], "ambiguous")

    def test_invalid_and_negative_quantity_is_rejected(self):
        r = receipt()
        r["counterpart_qty"] = "-1"
        row = self.run_match([shipment()], [r])[0]
        self.assertEqual(row["state"], "ambiguous")

if __name__ == "__main__":
    unittest.main()

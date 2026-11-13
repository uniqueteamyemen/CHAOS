import unittest
from experiments.identity_lab.exp_j_erp.odoo_reader import reconcile_export, reconcile_export_hybrid

UOMS = [
    {"id":"unit","name":"Units","category_id":"count","factor":"1","uom_type":"reference"},
    {"id":"dozen","name":"Dozen","category_id":"count","factor":"0.0833333333333333333333333333","uom_type":"bigger"},
]

def move(qty="10"):
    return {"id":1,"picking_id":"OUT-1","product_id":"P1","quantity":qty,
        "product_uom_qty":"10","product_uom":"unit","product_uom_category_id":"count",
        "state":"done","location_id":"WH","location_dest_id":"SHOP",
        "reference":"OUT-1","date":"2025-01-01"}

def receipt(rid, source="OUT-1", qty="10"):
    return {"source_picking_id":source,"counterpart_picking_id":rid,"product_id":"P1",
        "location_id":"SHOP","from_entity":"WH","counterpart_qty":qty,
        "counterpart_uom_id":"unit","product_uom_category_id":"count",
        "counterpart_date":"2025-01-02","counterpart_system":"receiver",
        "counterpart_source":"signed-receipt","recorded_at":"2025-01-02T10:00:00"}

class HybridOdooIntegrationTests(unittest.TestCase):
    def test_raw_odoo_export_reaches_hybrid_exact_confirmation(self):
        result = reconcile_export_hybrid([move()], UOMS, [receipt("IN-1")])
        self.assertEqual(result["engine"], "hybrid")
        self.assertEqual(result["receipt_matches"][0]["state"], "confirmed_exact")
        self.assertTrue(result["receipt_matches"][0]["evidence_complete"])

    def test_raw_odoo_export_keeps_approximate_as_candidate(self):
        result = reconcile_export_hybrid([move()], UOMS, [receipt("IN-2", source=None, qty="9")])
        row = result["receipt_matches"][0]
        self.assertEqual(row["state"], "candidate_approximate")
        self.assertFalse(row["confirmed"])
        self.assertFalse(row["loss_claim"])

    def test_hybrid_integration_aggregates_linked_partial_receipts(self):
        result = reconcile_export_hybrid(
            [move()], UOMS, [receipt("IN-1", qty="4"), receipt("IN-2", qty="6")]
        )
        row = result["receipt_matches"][0]
        self.assertEqual(row["state"], "confirmed_exact")
        self.assertEqual(row["receipt_count"], 2)
        self.assertEqual(row["qty_received"], "10")

    def test_existing_default_reader_path_is_unchanged(self):
        legacy = reconcile_export([move()], UOMS, [receipt("IN-1")])
        hybrid = reconcile_export_hybrid([move()], UOMS, [receipt("IN-1")])
        self.assertEqual(legacy["receipt_matches"][0]["state"], "exact")
        self.assertEqual(hybrid["receipt_matches"][0]["state"], "confirmed_exact")
        self.assertTrue(hybrid["default_reconcile_export_unchanged"])

    def test_missing_executed_quantity_is_rejected_in_hybrid_adapter(self):
        bad = move()
        del bad["quantity"]
        result = reconcile_export_hybrid([bad], UOMS, [receipt("IN-1")])
        self.assertEqual(result["movement_stats"]["rejected_rows"], 1)
        self.assertEqual(result["movements"], [])
        self.assertEqual(result["receipt_matches"], [])

if __name__ == "__main__":
    unittest.main()

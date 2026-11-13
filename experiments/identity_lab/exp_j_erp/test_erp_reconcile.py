from decimal import Decimal
import unittest

try:
    from .reconcile import aggregate_moves, match_counterpart_receipts
    from .uom import UomNormalizationError, normalize_quantity, normalize_to_reference
except ImportError:
    from reconcile import aggregate_moves, match_counterpart_receipts
    from uom import UomNormalizationError, normalize_quantity, normalize_to_reference


UOMS = {
    "uom_unit": {"id": "uom_unit", "name": "Units", "category_id": "unit", "factor": "1", "uom_type": "reference"},
    "uom_kg": {"id": "uom_kg", "name": "kg", "category_id": "weight", "factor": "1", "uom_type": "reference"},
    "uom_g": {"id": "uom_g", "name": "g", "category_id": "weight", "factor": "1000", "uom_type": "smaller"},
}


class UomTests(unittest.TestCase):
    def test_factor_direction_grams_to_kg(self):
        self.assertEqual(
            normalize_quantity("2500", UOMS["uom_g"], UOMS["uom_kg"]),
            Decimal("2.5"),
        )

    def test_factor_direction_kg_to_grams(self):
        self.assertEqual(
            normalize_quantity("2.5", UOMS["uom_kg"], UOMS["uom_g"]),
            Decimal("2500.0"),
        )

    def test_units_to_kg_is_rejected(self):
        with self.assertRaises(UomNormalizationError) as caught:
            normalize_quantity("3", UOMS["uom_unit"], UOMS["uom_kg"])
        self.assertEqual(caught.exception.code, "uom_category_mismatch")

    def test_odoo_many2one_category_shape_is_supported(self):
        from_uom = {"category_id": [9, "Weight"], "factor": "1000"}
        to_uom = {"category_id": [9, "Weight"], "factor": "1"}
        self.assertEqual(normalize_quantity("2500", from_uom, to_uom), Decimal("2.5"))

    def test_product_category_is_enforced(self):
        with self.assertRaises(UomNormalizationError) as caught:
            normalize_to_reference("3", UOMS["uom_kg"], UOMS, "unit")
        self.assertEqual(caught.exception.code, "product_uom_category_mismatch")


class AggregationTests(unittest.TestCase):
    def test_normalizes_before_aggregation_and_preserves_references(self):
        moves = [
            {"id": 1, "picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
             "location_dest_id": "B", "product_uom": "uom_g", "product_uom_category_id": "weight",
             "quantity": "500", "product_uom_qty": "500", "state": "done",
             "reference": "REF-A", "date": "2025-01-01"},
            {"id": 2, "picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
             "location_dest_id": "B", "product_uom": "uom_kg", "product_uom_category_id": "weight",
             "quantity": "0.5", "product_uom_qty": "0.5", "state": "done",
             "reference": "REF-A", "date": "2025-01-01"},
        ]
        rows, stats = aggregate_moves(moves, UOMS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quantity"], "1.0")
        self.assertEqual(rows[0]["references"], ["REF-A"])
        self.assertEqual(rows[0]["move_count"], 2)
        self.assertEqual(stats["rejected_rows"], 0)

    def test_reference_variants_are_not_collapsed(self):
        moves = [
            {"picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
             "location_dest_id": "B", "product_uom": "uom_unit",
             "product_uom_category_id": "unit", "quantity": "2", "state": "done",
             "reference": "REF-A"},
            {"picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
             "location_dest_id": "B", "product_uom": "uom_unit",
             "product_uom_category_id": "unit", "quantity": "3", "state": "done",
             "reference": "REF-B"},
        ]
        rows, _ = aggregate_moves(moves, UOMS)
        self.assertEqual(len(rows), 2)
        self.assertEqual({tuple(row["references"]) for row in rows}, {("REF-A",), ("REF-B",)})

    def test_location_variants_are_not_collapsed(self):
        moves = [
            {"picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
             "location_dest_id": "B", "product_uom": "uom_unit",
             "product_uom_category_id": "unit", "quantity": "2", "state": "done"},
            {"picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
             "location_dest_id": "C", "product_uom": "uom_unit",
             "product_uom_category_id": "unit", "quantity": "3", "state": "done"},
        ]
        rows, _ = aggregate_moves(moves, UOMS)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["heterogeneous_locations"] for row in rows))

    def test_missing_executed_quantity_is_rejected_not_replaced_by_demand(self):
        moves = [{"picking_id": "OUT-1", "product_id": "P1", "location_id": "A",
                  "location_dest_id": "B", "product_uom": "uom_unit",
                  "product_uom_category_id": "unit", "product_uom_qty": "99", "state": "done"}]
        rows, stats = aggregate_moves(moves, UOMS)
        self.assertEqual(rows, [])
        self.assertEqual(stats["rejected"][0]["reason"], "missing_executed_quantity")


class CounterpartTests(unittest.TestCase):
    def setUp(self):
        self.shipment = [{
            "picking_id": "OUT-7", "product_id": "P1", "location_dest_id": "B",
            "reference_uom_id": "uom_unit", "quantity": "30", "dates": ["2025-01-01"],
        }]

    def test_exact_independent_receipt_can_produce_loss(self):
        receipts = [{
            "source_picking_id": "OUT-7", "counterpart_picking_id": "IN-91",
            "product_id": "P1", "counterpart_qty": "24", "counterpart_uom_id": "uom_unit",
            "product_uom_category_id": "unit", "counterpart_date": "2025-01-02",
            "counterpart_system": "receiving_wms", "counterpart_source": "signed_receipt.pdf", "recorded_at": "2025-01-02T10:00:00",
            "location_id": "B",
        }]
        result = match_counterpart_receipts(self.shipment, receipts, UOMS)[0]
        self.assertEqual(result["state"], "exact")
        self.assertTrue(result["confirmed"])
        self.assertIn("loss", result["issues"])

    def test_approximate_unique_is_never_confirmed_or_loss(self):
        receipts = [{
            "counterpart_picking_id": "IN-91", "product_id": "P1",
            "counterpart_qty": "30", "counterpart_uom_id": "uom_unit",
            "product_uom_category_id": "unit", "counterpart_date": "2025-01-02",
            "counterpart_system": "receiving_wms", "counterpart_source": "receipt_scan", "recorded_at": "2025-01-02T10:00:00",
            "location_id": "B",
        }]
        result = match_counterpart_receipts(self.shipment, receipts, UOMS)[0]
        self.assertEqual(result["state"], "approximate_unique")
        self.assertFalse(result["confirmed"])
        self.assertNotIn("loss", result.get("issues", []))

    def test_multiple_approximate_candidates_are_ambiguous(self):
        receipts = []
        for receipt_id in ("IN-91", "IN-92"):
            receipts.append({
                "counterpart_picking_id": receipt_id, "product_id": "P1",
                "counterpart_qty": "30", "counterpart_uom_id": "uom_unit",
                "product_uom_category_id": "unit", "counterpart_date": "2025-01-02",
                "counterpart_system": "receiving_wms", "counterpart_source": "receipt_scan", "recorded_at": "2025-01-02T10:00:00",
                "location_id": "B",
            })
        result = match_counterpart_receipts(self.shipment, receipts, UOMS)[0]
        self.assertEqual(result["state"], "ambiguous")
        self.assertFalse(result["confirmed"])

    def test_explicit_link_with_conflicting_destination_is_ambiguous(self):
        receipts = [{
            "source_picking_id": "OUT-7", "counterpart_picking_id": "IN-91",
            "product_id": "P1", "counterpart_qty": "30", "counterpart_uom_id": "uom_unit",
            "product_uom_category_id": "unit", "counterpart_date": "2025-01-02",
            "counterpart_system": "receiving_wms", "counterpart_source": "receipt_scan",
            "recorded_at": "2025-01-02T10:00:00", "location_id": "OTHER",
        }]
        result = match_counterpart_receipts(self.shipment, receipts, UOMS)[0]
        self.assertEqual(result["state"], "ambiguous")
        self.assertEqual(result["reason"], "explicit_link_conflict")
        self.assertFalse(result["confirmed"])

    def test_missing_provenance_cannot_be_confirmed(self):
        receipts = [{
            "source_picking_id": "OUT-7", "counterpart_picking_id": "IN-91",
            "product_id": "P1", "counterpart_qty": "24", "counterpart_uom_id": "uom_unit",
            "product_uom_category_id": "unit", "counterpart_date": "2025-01-02",
            "location_id": "B",
        }]
        result = match_counterpart_receipts(self.shipment, receipts, UOMS)[0]
        self.assertEqual(result["state"], "ambiguous")
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["reason"], "receipt_provenance_incomplete")

    def test_receiver_document_id_is_not_mistaken_for_source_key(self):
        receipts = [{
            "counterpart_picking_id": "OUT-7", "product_id": "P1",
            "counterpart_qty": "30", "counterpart_uom_id": "uom_unit",
            "product_uom_category_id": "unit", "counterpart_date": "2025-01-02",
            "counterpart_system": "receiving_wms", "counterpart_source": "receipt_scan", "recorded_at": "2025-01-02T10:00:00",
            "location_id": "B",
        }]
        result = match_counterpart_receipts(self.shipment, receipts, UOMS)[0]
        self.assertEqual(result["state"], "approximate_unique")
        self.assertFalse(result["confirmed"])


if __name__ == "__main__":
    unittest.main()

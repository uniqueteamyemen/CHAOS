import unittest

from experiments.identity_lab.exp_j_erp.reconcile import aggregate_moves
from experiments.identity_lab.exp_j_erp.shadow_mode import run_shadow
from experiments.identity_lab.exp_j_erp.uom import index_uoms
from experiments.identity_lab.exp_j_erp.run_odoo17_demo_shadow import (
    completed_test_bundle, load_inputs,
)


class Odoo17DemoShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.completion, cls.receipt_overlay = load_inputs()

    def test_source_rows_preserve_pre_completion_status(self):
        self.assertEqual(len(self.bundle["moves"]), 4)
        self.assertEqual(len({m["picking_id"] for m in self.bundle["moves"]}), 4)
        self.assertTrue(all(m["state"] == "assigned" for m in self.bundle["moves"]))
        self.assertTrue(all(m["picked"] is False for m in self.bundle["moves"]))
        self.assertTrue(all(m.get("quantity") is not None for m in self.bundle["moves"]))
        self.assertTrue(all(m.get("product_uom_qty") is not None for m in self.bundle["moves"]))
        self.assertEqual(self.bundle["export_metadata"]["source_classification"],
                         "official_odoo17_demo_xml_seed")
        self.assertEqual(
            self.bundle["export_metadata"]["source_counts"]["completed_stock_moves_proven_by_seed"], 0
        )
        self.assertFalse(self.bundle["export_metadata"]["is_odoo_database_export"])

    def test_source_pre_completion_rows_are_not_scored_as_done(self):
        report = run_shadow(self.bundle)
        for engine in ("A", "B", "C"):
            self.assertEqual(report["engine_summaries"][engine]["shipments_scored"], 0)
            self.assertEqual(report["engine_summaries"][engine]["confirmed"], 0)
            self.assertEqual(report["engine_summaries"][engine]["loss_claims"], 0)

    def test_test_completion_overlay_is_explicit_and_separate(self):
        self.assertTrue(self.completion["not_source_data"])
        completed = completed_test_bundle(self.bundle, self.completion)
        self.assertTrue(all(m["state"] == "done" and m["picked"] is True for m in completed["moves"]))
        self.assertEqual(completed["export_metadata"]["test_completion_overlay_is_source_data"], False)

    def test_odoo_field_adapter_aggregates_four_partial_and_full_quantities(self):
        completed = completed_test_bundle(self.bundle, self.completion)
        uoms = index_uoms(completed["uom_rows"])
        aggregated, stats = aggregate_moves(completed["moves"], uoms)
        self.assertEqual(stats["moves_total"], 4)
        self.assertEqual(stats["moves_done"], 4)
        self.assertEqual(stats["aggregated_movements"], 4)
        self.assertEqual(stats["rejected_rows"], 0)
        self.assertEqual(stats["partial_movements"], 3)
        values = {row["picking_id"]: (row["quantity"], row["demand_quantity"], row["partial"])
                  for row in aggregated}
        self.assertEqual(values["stock.outgoing_shipment_main_warehouse1"], ("100", "180", True))
        self.assertEqual(values["stock.outgoing_shipment_main_warehouse5"], ("32", "40", True))
        self.assertEqual(values["stock.outgoing_shipment_main_warehouse6"], ("50", "50", False))
        self.assertEqual(values["stock.outgoing_chicago_warehouse1"], ("100", "180", True))

    def test_completed_test_baseline_without_receipts_fails_closed(self):
        completed = completed_test_bundle(self.bundle, self.completion)
        report = run_shadow(completed)
        for engine in ("A", "B", "C"):
            summary = report["engine_summaries"][engine]
            self.assertEqual(summary["shipments_scored"], 4)
            self.assertEqual(summary["unmatched"], 4)
            self.assertEqual(summary["confirmed"], 0)
            self.assertEqual(summary["loss_claims"], 0)
        self.assertEqual(report["pairwise_state_disagreements"],
                         {"A_vs_B": 0, "A_vs_C": 0, "B_vs_C": 0})

    def test_receipt_overlay_is_explicitly_synthetic_and_complete(self):
        self.assertTrue(self.receipt_overlay["not_source_data"])
        self.assertEqual(len(self.receipt_overlay["receipts"]), 4)
        required = (
            "source_picking_id", "counterpart_picking_id", "product_id", "location_id",
            "counterpart_qty", "counterpart_uom_id", "counterpart_date",
            "counterpart_system", "counterpart_source", "recorded_at",
        )
        self.assertTrue(all(all(r.get(k) not in (None, "") for k in required)
                            for r in self.receipt_overlay["receipts"]))

    def test_controlled_abc_comparison_exposes_b_threshold_coupling(self):
        completed = completed_test_bundle(self.bundle, self.completion)
        scenario = {
            **completed,
            "receipts": self.receipt_overlay["receipts"],
        }
        report = run_shadow(scenario)
        expected_losses = {"A": 2, "B": 0, "C": 2}
        for engine, expected in expected_losses.items():
            self.assertEqual(report["engine_summaries"][engine]["confirmed"], 4)
            self.assertEqual(report["engine_summaries"][engine]["loss_claims"], expected)
        self.assertEqual(report["pairwise_state_disagreements"],
                         {"A_vs_B": 0, "A_vs_C": 0, "B_vs_C": 0})
        self.assertEqual(report["disagreement_count"], 2)
        self.assertEqual(report["pairwise_raw_state_label_differences"]["A_vs_B"], 4)

    def test_source_receipt_overlays_are_not_mislabelled_as_observed_data(self):
        completed = completed_test_bundle(self.bundle, self.completion)
        self.assertFalse(completed["export_metadata"]["test_completion_overlay_is_source_data"])
        self.assertTrue(self.receipt_overlay["not_source_data"])


if __name__ == "__main__":
    unittest.main()

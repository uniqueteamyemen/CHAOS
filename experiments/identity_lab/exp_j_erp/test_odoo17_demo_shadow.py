import json
import tempfile
import unittest
from pathlib import Path

from experiments.identity_lab.exp_j_erp.reconcile import aggregate_moves
from experiments.identity_lab.exp_j_erp.shadow_mode import run_shadow
from experiments.identity_lab.exp_j_erp.uom import index_uoms
from experiments.identity_lab.exp_j_erp.run_odoo17_demo_shadow import load_inputs

HERE = Path(__file__).resolve().parent


class Odoo17DemoShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.overlay = load_inputs()

    def test_source_contains_six_completed_movement_rows(self):
        self.assertEqual(len(self.bundle["moves"]), 6)
        self.assertEqual(len({m["picking_id"] for m in self.bundle["moves"]}), 6)
        self.assertTrue(all(m["state"] == "done" for m in self.bundle["moves"]))
        self.assertTrue(all(m.get("quantity") is not None for m in self.bundle["moves"]))
        self.assertTrue(all(m.get("product_uom_qty") is not None for m in self.bundle["moves"]))
        self.assertEqual(self.bundle["export_metadata"]["source_classification"],
                         "official_odoo17_demo_xml_seed")
        self.assertFalse(self.bundle["export_metadata"]["is_odoo_database_export"])

    def test_odoo_field_adapter_aggregates_executed_quantities(self):
        uoms = index_uoms(self.bundle["uom_rows"])
        aggregated, stats = aggregate_moves(self.bundle["moves"], uoms)
        self.assertEqual(stats["moves_total"], 6)
        self.assertEqual(stats["moves_done"], 6)
        self.assertEqual(stats["aggregated_movements"], 6)
        self.assertEqual(stats["rejected_rows"], 0)
        self.assertEqual(stats["partial_movements"], 4)
        values = {row["picking_id"]: (row["quantity"], row["demand_quantity"], row["partial"])
                  for row in aggregated}
        self.assertEqual(values["stock.outgoing_shipment_main_warehouse1"], ("100", "180", True))
        self.assertEqual(values["stock.outgoing_shipment_main_warehouse5"], ("32", "40", True))
        self.assertEqual(values["stock.outgoing_shipment_main_warehouse6"], ("50", "50", False))

    def test_baseline_without_receipts_fails_closed_for_all_engines(self):
        report = run_shadow(self.bundle)
        for engine in ("A", "B", "C"):
            summary = report["engine_summaries"][engine]
            self.assertEqual(summary["shipments_scored"], 6)
            self.assertEqual(summary["unmatched"], 6)
            self.assertEqual(summary["confirmed"], 0)
            self.assertEqual(summary["loss_claims"], 0)
        self.assertEqual(report["pairwise_state_disagreements"],
                         {"A_vs_B": 0, "A_vs_C": 0, "B_vs_C": 0})

    def test_overlay_is_explicitly_synthetic_and_complete(self):
        self.assertTrue(self.overlay["not_source_data"])
        self.assertEqual(len(self.overlay["receipts"]), 6)
        required = (
            "source_picking_id", "counterpart_picking_id", "product_id", "location_id",
            "counterpart_qty", "counterpart_uom_id", "counterpart_date",
            "counterpart_system", "counterpart_source", "recorded_at",
        )
        self.assertTrue(all(all(r.get(k) not in (None, "") for k in required)
                            for r in self.overlay["receipts"]))

    def test_controlled_ab_comparison_exposes_b_threshold_coupling(self):
        scenario = {
            **self.bundle,
            "export_metadata": {**self.bundle["export_metadata"],
                                "test_overlay_is_source_data": False},
            "receipts": self.overlay["receipts"],
        }
        report = run_shadow(scenario)
        expected_losses = {"A": 3, "B": 1, "C": 3}
        for engine, expected in expected_losses.items():
            self.assertEqual(report["engine_summaries"][engine]["confirmed"], 6)
            self.assertEqual(report["engine_summaries"][engine]["loss_claims"], expected)
        self.assertEqual(report["pairwise_state_disagreements"],
                         {"A_vs_B": 0, "A_vs_C": 0, "B_vs_C": 0})
        self.assertEqual(report["disagreement_count"], 2)

    def test_output_label_normalization_is_not_counted_as_engine_disagreement(self):
        scenario = {
            **self.bundle,
            "receipts": self.overlay["receipts"],
        }
        report = run_shadow(scenario)
        self.assertEqual(report["pairwise_state_disagreements"]["A_vs_B"], 0)
        self.assertEqual(report["pairwise_raw_state_label_differences"]["A_vs_B"], 6)


if __name__ == "__main__":
    unittest.main()

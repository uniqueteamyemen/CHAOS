"""Run A/B/C on the existing public one-sided stock ledger as a candidate-only probe.

This is not an Odoo export and not ground-truth validation. The source has 68
transfer_out rows and 34 transfer_in rows but no locations, shared document key,
or independent receiving provenance. Transfer-in rows are therefore exposed only
as unlinked candidate proxies; the evidence gates must prevent confirmation/loss.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .shadow_mode import run_shadow, write_run

LAB_ROOT = Path(__file__).resolve().parents[1]
SOURCE = LAB_ROOT / "exp_h_public" / "data" / "stock_movements.csv"


def _positive_decimal(raw: str, field: str) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid_{field}:{raw!r}") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"non_positive_{field}:{raw!r}")
    return value


def build_public_ledger_bundle() -> tuple[dict, dict]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"public_ledger_source_missing:{SOURCE}")

    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    outbound = [r for r in rows if r.get("movement_type") == "transfer_out"]
    inbound = [r for r in rows if r.get("movement_type") == "transfer_in"]
    if not outbound or not inbound:
        raise ValueError("transfer_out_and_transfer_in_rows_required")

    product_values = sorted({str(r["product_id"]) for r in outbound + inbound})
    product_alias = {value: f"SKU-{i:03d}" for i, value in enumerate(product_values, 1)}
    outbound = sorted(outbound, key=lambda r: int(r["id"]))
    inbound = sorted(inbound, key=lambda r: int(r["id"]))

    moves = []
    for i, row in enumerate(outbound, 1):
        quantity = _positive_decimal(row.get("units_out", ""), "units_out")
        moves.append({
            "id": f"MOVE-{i:04d}",
            "picking_id": f"SHIP-{i:04d}",
            "product_id": product_alias[str(row["product_id"])],
            "quantity": str(quantity),
            "product_uom": "public-count-unit",
            "product_uom_category_id": "count",
            "state": "done",
            "date": str(row["moved_at"]),
            # Locations and source references are absent in the source dataset.
        })

    candidate_receipts = []
    for i, row in enumerate(inbound, 1):
        quantity = _positive_decimal(row.get("units_in", ""), "units_in")
        candidate_receipts.append({
            "counterpart_picking_id": f"IN-{i:04d}",
            "product_id": product_alias[str(row["product_id"])],
            "counterpart_qty": str(quantity),
            "counterpart_uom_id": "public-count-unit",
            "product_uom_category_id": "count",
            "counterpart_date": str(row["moved_at"]),
            "counterpart_system": "same_single_ledger_unverified",
            "counterpart_source": (
                "exp_h_public/data/stock_movements.csv:transfer_in row; "
                "not verified as an independent counterparty receipt"
            ),
            # Deliberately no source_picking_id, location_id, or recorded_at:
            # none exists in the source, and none may be manufactured.
        })

    bundle = {
        "schema_version": "1.0",
        "export_metadata": {
            "source": "experiments/identity_lab/exp_h_public/data/stock_movements.csv",
            "source_classification": "downloaded_public_single_ledger",
            "is_odoo_export": False,
            "is_ground_truth": False,
            "candidate_only_probe": True,
            "transfer_out_rows": len(moves),
            "transfer_in_candidate_rows": len(candidate_receipts),
            "independent_counterparty_evidence": False,
            "shared_source_document_key_available": False,
            "location_pair_available": False,
            "recorded_at_available": False,
            "uom_adapter": "units_out/units_in mapped to one count reference unit; not exported Odoo uom.uom metadata",
            "pseudonymization": "source product and row IDs replaced with deterministic sequential aliases; supplier_id discarded",
        },
        "moves": moves,
        "uom_rows": [{
            "id": "public-count-unit",
            "name": "Public sample count unit (adapter)",
            "category_id": "count",
            "factor": "1",
            "uom_type": "reference",
        }],
        "receipts": candidate_receipts,
    }
    stats = {
        "source_rows": len(rows),
        "movement_types": {
            name: sum(1 for r in rows if r.get("movement_type") == name)
            for name in sorted({str(r.get("movement_type")) for r in rows})
        },
        "shipments_scored": len(moves),
        "unlinked_inbound_candidate_rows": len(candidate_receipts),
        "unique_products_pseudonymized": len(product_alias),
    }
    return bundle, stats


def run_public_ledger_probe(output_root: Path | None = None) -> tuple[dict, dict, Path]:
    bundle, source_stats = build_public_ledger_bundle()
    report = run_shadow(bundle)

    for engine, summary in report["engine_summaries"].items():
        if summary["confirmed"] != 0 or summary["loss_claims"] != 0:
            raise AssertionError(
                f"{engine}_promoted_unlinked_candidate_to_confirmation_or_loss"
            )

    if output_root is None:
        output_root = Path(
            os.environ.get("RUNNER_TEMP", tempfile.gettempdir())
        ) / "erp-public-ledger-shadow-probe"
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = write_run(report, output_root)

    metadata = {
        "classification": "public-ledger candidate-only negative control; not Odoo validation",
        "source_stats": source_stats,
        "engine_summaries": report["engine_summaries"],
        "pairwise_state_disagreements": report["pairwise_state_disagreements"],
        "disagreement_count": report["disagreement_count"],
        "assertions": {
            "no_engine_confirmed_unlinked_inbound_rows": True,
            "no_engine_claimed_loss_without_independent_receipt_evidence": True,
            "source_ids_and_product_ids_pseudonymized": True,
            "source_supplier_ids_discarded": True,
        },
        "input_sha256": report["snapshot"]["sha256"],
        "run_directory": str(run_dir),
    }
    (run_dir / "public_ledger_probe_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report, metadata, run_dir


def main() -> None:
    report, metadata, run_dir = run_public_ledger_probe()
    print(json.dumps({
        "status": "completed",
        "classification": metadata["classification"],
        "run_directory": str(run_dir),
        "source_stats": metadata["source_stats"],
        "engine_summaries": metadata["engine_summaries"],
        "pairwise_state_disagreements": metadata["pairwise_state_disagreements"],
        "disagreement_count": metadata["disagreement_count"],
        "input_sha256": report["snapshot"]["sha256"],
        "no_confirmation_or_loss_assertions": "PASS",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

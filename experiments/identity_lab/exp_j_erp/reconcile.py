"""Movement aggregation and independent counterpart-receipt reconciliation.

A stock.move is one movement record, not a sender row plus a receiver row.
Counterparty receipts are a separate evidence stream. Approximate matches are never
promoted to confirmed matches and never generate loss claims.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

try:
    from .uom import UomNormalizationError, normalize_to_reference, relation_id
except ImportError:  # direct script execution from this directory
    from uom import UomNormalizationError, normalize_to_reference, relation_id


def _executed(move: Mapping) -> Decimal:
    raw = move.get("quantity")
    if raw in (None, ""):
        raw = move.get("quantity_done")  # legacy exports only
    if raw in (None, ""):
        raise UomNormalizationError("missing_executed_quantity")
    try:
        value = Decimal(str(raw))
    except Exception as exc:
        raise UomNormalizationError("quantity_invalid", str(raw)) from exc
    if not value.is_finite() or value < 0:
        raise UomNormalizationError("quantity_invalid", str(raw))
    return value


def _date(value: object) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def aggregate_moves(
    moves: list[Mapping],
    uoms_by_id: Mapping[str, Mapping],
) -> tuple[list[dict], dict]:
    """Aggregate completed moves only after conversion to a common reference UoM.

    Main identity is (picking_id, product_id). Different locations, reference units,
    or source documents remain distinct subgroups and are never silently merged.
    """
    groups: dict[tuple, dict] = {}
    rejected: list[dict] = []
    done_count = 0
    pickings: set[str] = set()
    product_categories: dict[tuple[str, str], set[str]] = {}

    for index, move in enumerate(moves):
        if str(move.get("state", "")).lower() != "done":
            continue
        done_count += 1
        picking = relation_id(move.get("picking_id"))
        product = relation_id(move.get("product_id"))
        if not picking or not product:
            rejected.append({"row": index, "reason": "movement_identity_missing"})
            continue
        pickings.add(picking)

        uom_id = move.get("product_uom") or move.get("product_uom_id")
        source_uom = uoms_by_id.get(relation_id(uom_id))
        if source_uom is None:
            rejected.append({"row": index, "picking_id": picking, "product_id": product,
                             "reason": "uom_unresolved"})
            continue
        try:
            executed = _executed(move)
            normalized, ref_uom_id = normalize_to_reference(
                executed, source_uom, uoms_by_id, move.get("product_uom_category_id")
            )
            demand_raw = move.get("product_uom_qty")
            demand_normalized = None
            if demand_raw not in (None, ""):
                demand_normalized, _ = normalize_to_reference(
                    demand_raw, source_uom, uoms_by_id, move.get("product_uom_category_id")
                )
        except UomNormalizationError as exc:
            rejected.append({"row": index, "picking_id": picking, "product_id": product,
                             "reason": exc.code, "detail": exc.detail})
            continue

        category = relation_id(source_uom.get("category_id"))
        product_categories.setdefault((picking, product), set()).add(category)
        source = relation_id(move.get("location_id"))
        destination = relation_id(move.get("location_dest_id"))
        # Location pair and reference UoM are part of the subgroup key. They are
        # intentionally not collapsed even when picking and product are identical.
        source_reference = str(move.get("reference") or move.get("name") or move.get("origin") or "")
        key = (picking, product, source, destination, ref_uom_id, source_reference)
        row = groups.setdefault(key, {
            "picking_id": picking,
            "product_id": product,
            "location_id": source,
            "location_dest_id": destination,
            "reference_uom_id": ref_uom_id,
            "uom_category_id": category,
            "quantity": Decimal("0"),
            "demand_quantity": Decimal("0"),
            "has_demand": True,
            "partial": False,
            "move_ids": [],
            "references": set(),
            "dates": [],
        })
        row["quantity"] += normalized
        if demand_normalized is None:
            row["has_demand"] = False
        else:
            row["demand_quantity"] += demand_normalized
            if normalized < demand_normalized:
                row["partial"] = True
        move_id = move.get("id")
        if move_id not in (None, ""):
            row["move_ids"].append(str(move_id))
        for ref in (move.get("reference"), move.get("name"), move.get("origin")):
            if ref not in (None, ""):
                row["references"].add(str(ref))
        if move.get("date"):
            row["dates"].append(str(move.get("date")))

    aggregated = []
    for row in groups.values():
        row["quantity"] = str(row["quantity"])
        row["demand_quantity"] = str(row["demand_quantity"]) if row["has_demand"] else None
        row["references"] = sorted(row["references"])
        row["dates"] = sorted(row["dates"])
        row["move_count"] = len(row["move_ids"])
        row["heterogeneous_locations"] = False
        aggregated.append(row)

    location_variants: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for row in aggregated:
        location_variants.setdefault((row["picking_id"], row["product_id"]), set()).add(
            (row["location_id"], row["location_dest_id"])
        )
    for row in aggregated:
        row["heterogeneous_locations"] = len(
            location_variants[(row["picking_id"], row["product_id"])]
        ) > 1
        row["heterogeneous_uom_categories"] = (
            len(product_categories[(row["picking_id"], row["product_id"])]) > 1
        )

    stats = {
        "moves_total": len(moves),
        "moves_done": done_count,
        "pickings": len(pickings),
        "aggregated_movements": len(aggregated),
        "rejected_rows": len(rejected),
        "partial_movements": sum(1 for row in aggregated if row["partial"]),
        "heterogeneous_location_groups": sum(
            1 for row in aggregated if row["heterogeneous_locations"]
        ),
        "heterogeneous_uom_groups": sum(
            1 for row in aggregated if row["heterogeneous_uom_categories"]
        ),
        "rejected": rejected,
    }
    return aggregated, stats


def _receipt_evidence_complete(receipt: Mapping) -> bool:
    required = (
        "counterpart_picking_id", "counterpart_qty", "counterpart_uom_id",
        "counterpart_date", "counterpart_system", "counterpart_source", "recorded_at",
    )
    return all(receipt.get(field) not in (None, "") for field in required)


def match_counterpart_receipts(
    shipments: list[Mapping],
    receipts: list[Mapping],
    uoms_by_id: Mapping[str, Mapping],
    date_window_days: int = 3,
    quantity_tolerance: Decimal = Decimal("0.01"),
) -> list[dict]:
    """Match independent receipt records to outbound movements.

    Exact identity requires an explicit source_picking_id on the receipt that points
    to the sender's picking_id. counterpart_picking_id remains the receiver's own
    document ID; it is not assumed to equal the sender's ID.

    Approximate matching uses product, destination, date window and quantity. It is
    a candidate only (never confirmed) and can never emit a loss classification.
    """
    results: list[dict] = []
    for shipment in shipments:
        shipment_id = relation_id(shipment.get("picking_id"))
        product_id = relation_id(shipment.get("product_id"))
        exact = [
            receipt for receipt in receipts
            if relation_id(receipt.get("source_picking_id")) == shipment_id
            and relation_id(receipt.get("product_id")) == product_id
            and (not relation_id(receipt.get("location_id")) or relation_id(receipt.get("location_id")) == relation_id(shipment.get("location_dest_id")))
        ]
        if len(exact) == 1 and not _receipt_evidence_complete(exact[0]):
            results.append({
                "picking_id": shipment_id, "product_id": product_id,
                "state": "ambiguous", "confidence": 0.0, "confirmed": False,
                "reason": "receipt_provenance_incomplete",
            })
            continue
        if len(exact) > 1:
            results.append({
                "picking_id": shipment_id, "product_id": product_id,
                "state": "ambiguous", "confidence": 0.0, "confirmed": False,
                "reason": "multiple_exact_receipts",
                "candidate_receipt_ids": [str(r.get("counterpart_picking_id") or "") for r in exact],
            })
            continue

        candidates = exact
        state = "exact"
        if not candidates:
            ship_date = _date((shipment.get("dates") or [None])[0])
            ship_qty = Decimal(str(shipment.get("quantity", "0")))
            candidates = []
            for receipt in receipts:
                if str(receipt.get("product_id") or "") != product_id:
                    continue
                receipt_location = relation_id(receipt.get("location_id"))
                if receipt_location and receipt_location != relation_id(shipment.get("location_dest_id")):
                    continue
                receipt_date = _date(receipt.get("counterpart_date"))
                if ship_date is None or receipt_date is None:
                    continue
                if abs((receipt_date - ship_date).days) > date_window_days:
                    continue
                try:
                    receipt_uom_id = relation_id(receipt.get("counterpart_uom_id"))
                    receipt_uom = uoms_by_id[receipt_uom_id]
                    receipt_qty, receipt_ref_id = normalize_to_reference(
                        receipt.get("counterpart_qty"), receipt_uom, uoms_by_id,
                        receipt.get("product_uom_category_id"),
                    )
                except (KeyError, UomNormalizationError):
                    continue
                if receipt_ref_id != relation_id(shipment.get("reference_uom_id")):
                    continue
                if abs(receipt_qty - ship_qty) <= quantity_tolerance:
                    candidates.append(receipt)
            if len(candidates) == 1:
                state = "approximate_unique"
            elif len(candidates) > 1:
                state = "ambiguous"
            else:
                state = "unmatched"

        if state in ("ambiguous", "unmatched"):
            results.append({
                "picking_id": shipment_id, "product_id": product_id,
                "state": state, "confidence": 0.0, "confirmed": False,
                "candidate_receipt_ids": [str(r.get("counterpart_picking_id") or "") for r in candidates],
            })
            continue

        receipt = candidates[0]
        try:
            receipt_uom_id = str(receipt.get("counterpart_uom_id") or "")
            receipt_uom = uoms_by_id[receipt_uom_id]
            received_qty, receipt_ref_id = normalize_to_reference(
                receipt.get("counterpart_qty"), receipt_uom, uoms_by_id,
                receipt.get("product_uom_category_id"),
            )
        except (KeyError, UomNormalizationError) as exc:
            results.append({
                "picking_id": shipment_id, "product_id": product_id,
                "state": "ambiguous", "confidence": 0.0, "confirmed": False,
                "reason": getattr(exc, "code", "receipt_uom_unresolved"),
            })
            continue

        sent_qty = Decimal(str(shipment.get("quantity", "0")))
        delta = sent_qty - received_qty
        confirmed = state == "exact"
        issues = []
        if confirmed and delta > quantity_tolerance:
            issues.append("loss")
        elif confirmed and delta < -quantity_tolerance:
            issues.append("over_receipt")
        ship_date = _date((shipment.get("dates") or [None])[0])
        receipt_date = _date(receipt.get("counterpart_date"))
        if confirmed and ship_date and receipt_date and (receipt_date - ship_date).days > date_window_days:
            issues.append("delay")

        results.append({
            "picking_id": shipment_id,
            "product_id": product_id,
            "counterpart_picking_id": str(receipt.get("counterpart_picking_id") or ""),
            "state": state,
            "confidence": 1.0 if confirmed else 0.5,
            "confirmed": confirmed,
            "qty_sent": str(sent_qty),
            "qty_received": str(received_qty),
            "delta": str(delta),
            "reference_uom_id": receipt_ref_id,
            "counterpart_system": receipt.get("counterpart_system"),
            "counterpart_source": receipt.get("counterpart_source"),
            "recorded_at": receipt.get("recorded_at"),
            "counterpart_date": receipt.get("counterpart_date"),
            "issues": issues,
        })
    return results

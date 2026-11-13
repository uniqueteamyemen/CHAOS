"""Hybrid shipment/receipt reconciliation.

Candidate discovery is intentionally permissive; confirmation is evidence-gated.
Only explicit, complete, non-conflicting source links can confirm a receipt and
produce loss/over-receipt/delay classifications. Approximate matches remain candidates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping

try:
    from .uom import UomNormalizationError, normalize_to_reference, relation_id
except ImportError:
    from uom import UomNormalizationError, normalize_to_reference, relation_id


def _date(value: object) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _decimal(value: object, code: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise UomNormalizationError(code, repr(value)) from exc
    if not result.is_finite() or result < 0:
        raise UomNormalizationError(code, repr(value))
    return result


def _receipt_complete(receipt: Mapping) -> bool:
    fields = (
        "source_picking_id", "counterpart_picking_id", "product_id",
        "location_id", "counterpart_qty", "counterpart_uom_id",
        "counterpart_date", "counterpart_system", "counterpart_source",
        "recorded_at",
    )
    return all(receipt.get(k) not in (None, "") for k in fields)


def _normalise_receipt(receipt: Mapping, shipment: Mapping,
                       uoms_by_id: Mapping[str, Mapping]) -> Decimal:
    uid = relation_id(receipt.get("counterpart_uom_id"))
    uom = uoms_by_id.get(uid)
    if uom is None:
        raise UomNormalizationError("receipt_uom_unresolved", uid)
    raw_qty = _decimal(receipt.get("counterpart_qty"), "receipt_quantity_invalid")
    qty, ref_id = normalize_to_reference(
        raw_qty, uom, uoms_by_id,
        receipt.get("product_uom_category_id"),
    )
    if ref_id != relation_id(shipment.get("reference_uom_id")):
        raise UomNormalizationError("reference_uom_mismatch")
    return qty


def _shipment_date(shipment: Mapping) -> date | None:
    dates = shipment.get("dates") or []
    return _date(min(dates)) if dates else _date(shipment.get("date"))


def _tolerance(sent: Decimal, absolute: Decimal, relative: Decimal) -> Decimal:
    return max(absolute, abs(sent) * relative)


def discover_candidates(
    shipment: Mapping,
    receipts: list[Mapping],
    uoms_by_id: Mapping[str, Mapping],
    date_window_days: int = 3,
    quantity_tolerance_absolute: Decimal = Decimal("0"),
    quantity_tolerance_relative: Decimal = Decimal("0.02"),
    excluded_receipt_ids: set[str] | None = None,
) -> list[dict]:
    """Return ranked approximate candidates; never confirms or classifies loss."""
    if not isinstance(date_window_days, int) or date_window_days < 0:
        raise ValueError("date_window_days must be a non-negative integer")
    quantity_tolerance_absolute = _decimal(
        quantity_tolerance_absolute, "candidate_absolute_tolerance_invalid"
    )
    quantity_tolerance_relative = _decimal(
        quantity_tolerance_relative, "candidate_relative_tolerance_invalid"
    )
    excluded = excluded_receipt_ids or set()
    product = relation_id(shipment.get("product_id"))
    destination = relation_id(shipment.get("location_dest_id"))
    sender = relation_id(shipment.get("location_id"))
    sent = _decimal(shipment.get("quantity", "0"), "shipment_quantity_invalid")
    sent_date = _shipment_date(shipment)
    found = []
    for receipt in receipts:
        rid = relation_id(receipt.get("counterpart_picking_id"))
        if not rid or rid in excluded:
            continue
        if relation_id(receipt.get("product_id")) != product:
            continue
        receipt_location = relation_id(receipt.get("location_id"))
        if destination and receipt_location != destination:
            continue
        receipt_sender = relation_id(receipt.get("from_entity"))
        shipment_sender = relation_id(shipment.get("from_entity") or sender)
        if receipt_sender and shipment_sender and receipt_sender != shipment_sender:
            continue
        received_date = _date(receipt.get("counterpart_date"))
        if sent_date is None or received_date is None:
            continue
        day_delta = (received_date - sent_date).days
        if abs(day_delta) > date_window_days:
            continue
        try:
            received = _normalise_receipt(receipt, shipment, uoms_by_id)
        except (KeyError, UomNormalizationError):
            continue
        delta = abs(sent - received)
        allowed = _tolerance(sent, quantity_tolerance_absolute,
                             quantity_tolerance_relative)
        if delta > allowed:
            continue
        found.append({
            "receipt_id": rid,
            "quantity_delta": str(delta),
            "date_delta_days": day_delta,
            "rank": [str(delta), abs(day_delta), rid],
        })
    return sorted(found, key=lambda row: (Decimal(row["quantity_delta"]),
                                          abs(row["date_delta_days"]), row["receipt_id"]))


def match_hybrid(
    shipments: list[Mapping],
    receipts: list[Mapping],
    uoms_by_id: Mapping[str, Mapping],
    *,
    date_window_days: int = 3,
    candidate_quantity_tolerance_absolute: Decimal = Decimal("0"),
    candidate_quantity_tolerance_relative: Decimal = Decimal("0.02"),
    reconciliation_quantity_tolerance: Decimal = Decimal("0.01"),
    loss_classification_threshold: Decimal = Decimal("0.5"),
) -> list[dict]:
    """Reconcile shipments with one-to-one receipt ownership and strict evidence gates.

    Multiple explicit partial receipts may be summed for one shipment. A receipt ID
    duplicated in the input, linked to multiple shipments, or linked with conflicting
    product/location evidence cannot confirm anything. Approximate matches never
    consume receipts and never emit financial/stock loss claims.
    """
    if not isinstance(date_window_days, int) or date_window_days < 0:
        raise ValueError("date_window_days must be a non-negative integer")
    candidate_quantity_tolerance_absolute = _decimal(
        candidate_quantity_tolerance_absolute, "candidate_absolute_tolerance_invalid"
    )
    candidate_quantity_tolerance_relative = _decimal(
        candidate_quantity_tolerance_relative, "candidate_relative_tolerance_invalid"
    )
    reconciliation_quantity_tolerance = _decimal(
        reconciliation_quantity_tolerance, "reconciliation_tolerance_invalid"
    )
    loss_classification_threshold = _decimal(
        loss_classification_threshold, "loss_threshold_invalid"
    )
    receipt_id_counts = Counter(
        relation_id(r.get("counterpart_picking_id")) for r in receipts
        if relation_id(r.get("counterpart_picking_id"))
    )
    links: dict[str, list[Mapping]] = defaultdict(list)
    for receipt in receipts:
        source = relation_id(receipt.get("source_picking_id"))
        if source:
            links[source].append(receipt)

    shipment_ids = [relation_id(s.get("picking_id")) for s in shipments]
    shipment_id_counts = Counter(x for x in shipment_ids if x)
    linked_owners: dict[str, set[str]] = defaultdict(set)
    for receipt in receipts:
        rid = relation_id(receipt.get("counterpart_picking_id"))
        source = relation_id(receipt.get("source_picking_id"))
        if rid and source:
            linked_owners[rid].add(source)

    # Reserve every receipt explicitly linked to an in-scope shipment before
    # approximate discovery. Otherwise an earlier shipment could claim a receipt
    # that belongs to a later exact-linked shipment.
    reserved_receipt_ids = {
        relation_id(r.get("counterpart_picking_id"))
        for r in receipts
        if relation_id(r.get("source_picking_id"))
        and relation_id(r.get("counterpart_picking_id"))
    }
    candidate_cache: dict[str, list[dict]] = {}
    candidate_owners: dict[str, set[str]] = defaultdict(set)
    for candidate_shipment in shipments:
        candidate_sid = relation_id(candidate_shipment.get("picking_id"))
        if not candidate_sid or links.get(candidate_sid):
            continue
        try:
            _decimal(candidate_shipment.get("quantity", "0"), "shipment_quantity_invalid")
        except UomNormalizationError:
            continue
        found = discover_candidates(
            candidate_shipment, receipts, uoms_by_id, date_window_days,
            candidate_quantity_tolerance_absolute,
            candidate_quantity_tolerance_relative, reserved_receipt_ids,
        )
        candidate_cache[candidate_sid] = found
        for candidate in found:
            candidate_owners[candidate["receipt_id"]].add(candidate_sid)

    used_receipt_ids: set[str] = set()
    results: list[dict] = []
    for shipment in shipments:
        sid = relation_id(shipment.get("picking_id"))
        pid = relation_id(shipment.get("product_id"))
        if not sid or shipment_id_counts[sid] != 1:
            results.append({"picking_id": sid, "product_id": pid,
                            "state": "ambiguous", "confirmed": False,
                            "reason": "shipment_identity_missing_or_duplicated",
                            "candidate_receipt_ids": []})
            continue
        try:
            sent = _decimal(shipment.get("quantity", "0"), "shipment_quantity_invalid")
        except UomNormalizationError as exc:
            results.append({"picking_id": sid, "product_id": pid,
                            "state": "ambiguous", "confirmed": False,
                            "reason": exc.code, "candidate_receipt_ids": []})
            continue
        linked = links.get(sid, [])
        if linked:
            linked_products = {relation_id(r.get("product_id")) for r in linked}
            linked_locations = {relation_id(r.get("location_id")) for r in linked}
            expected_location = relation_id(shipment.get("location_dest_id"))
            expected_sender = relation_id(shipment.get("from_entity") or shipment.get("location_id"))
            linked_senders = {
                relation_id(r.get("from_entity")) for r in linked
                if relation_id(r.get("from_entity"))
            }
            ids = [relation_id(r.get("counterpart_picking_id")) for r in linked]
            conflict = (
                linked_products != {pid}
                or (expected_location and linked_locations != {expected_location})
                or (expected_sender and linked_senders and linked_senders != {expected_sender})
                or any(not rid or receipt_id_counts[rid] != 1 for rid in ids)
                or any(len(linked_owners[rid]) != 1 for rid in ids if rid)
                or any(rid in used_receipt_ids for rid in ids)
            )
            if conflict:
                results.append({"picking_id": sid, "product_id": pid,
                                "state": "ambiguous", "confirmed": False,
                                "reason": "explicit_link_conflict_or_receipt_reuse",
                                "candidate_receipt_ids": ids})
                continue
            if not all(_receipt_complete(r) for r in linked):
                results.append({"picking_id": sid, "product_id": pid,
                                "state": "ambiguous", "confirmed": False,
                                "reason": "receipt_provenance_incomplete",
                                "candidate_receipt_ids": ids})
                continue
            try:
                quantities = [_normalise_receipt(r, shipment, uoms_by_id) for r in linked]
            except (KeyError, UomNormalizationError) as exc:
                results.append({"picking_id": sid, "product_id": pid,
                                "state": "ambiguous", "confirmed": False,
                                "reason": getattr(exc, "code", "receipt_uom_invalid"),
                                "candidate_receipt_ids": ids})
                continue
            received = sum(quantities, Decimal("0"))
            delta = sent - received
            issues = []
            if delta > loss_classification_threshold:
                issues.append("loss")
            elif delta > reconciliation_quantity_tolerance:
                issues.append("partial_delivery")
            elif delta < -reconciliation_quantity_tolerance:
                issues.append("over_receipt")
            dates = [_date(r.get("counterpart_date")) for r in linked]
            valid_dates = [d for d in dates if d is not None]
            shipped_date = _shipment_date(shipment)
            delay_days = ((max(valid_dates) - shipped_date).days
                          if valid_dates and shipped_date else None)
            if delay_days is not None and delay_days > date_window_days:
                issues.append("delay")
            used_receipt_ids.update(ids)
            results.append({
                "picking_id": sid, "product_id": pid, "state": "confirmed_exact",
                "confirmed": True, "confidence": 1.0,
                "counterpart_picking_ids": ids, "receipt_count": len(linked),
                "qty_sent": str(sent), "qty_received": str(received),
                "delta": str(delta), "issues": issues, "delay_days": delay_days,
                "evidence_complete": True,
            })
            continue

        candidates = candidate_cache.get(sid, [])
        shared_candidate = (
            len(candidates) == 1
            and len(candidate_owners[candidates[0]["receipt_id"]]) > 1
        )
        if shared_candidate:
            state, reason = "ambiguous", "receipt_candidate_shared_across_shipments"
        elif len(candidates) == 1:
            state, reason = "candidate_approximate", "single_approximate_candidate"
        elif len(candidates) > 1:
            state, reason = "ambiguous", "multiple_approximate_candidates"
        else:
            state, reason = "unmatched", "no_compatible_receipt"
        results.append({
            "picking_id": sid, "product_id": pid, "state": state,
            "confirmed": False, "confidence": 0.5 if len(candidates) == 1 else 0.0,
            "candidate_receipt_ids": [c["receipt_id"] for c in candidates],
            "candidate_details": candidates, "reason": reason,
            "issues": [], "loss_claim": False,
        })
    return results

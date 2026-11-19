"""Deterministic source-record identity and point-in-time vintage selection.

This module is an independent data-foundation utility. It does not modify the
legacy identity_v1 or residual_event_v1 contracts, detector code, or frozen
experiment archive.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import unicodedata
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "source-record-identity-v1"
VALID_SEMANTICS = {"periodic_measurement", "event_stream", "period_count"}
VALID_STATUSES = {"observed", "missing", "not_applicable", "pending", "invalid"}


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _canonical_decimal(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError("value_must_be_finite_number_or_null")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("value_must_be_finite_number_or_null") from exc
    if not number.is_finite():
        raise ValueError("value_must_be_finite_number_or_null")
    if number == 0:
        return "0"
    rendered = format(number.normalize(), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _canonical_event_time(value: Any, *, require_instant: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("event_time_or_available_at_missing")
    raw = _nfc(value.strip())
    if not require_instant and len(raw) == 4 and raw.isdigit():
        return raw
    if not require_instant and len(raw) == 7 and raw[4] == "-":
        try:
            datetime.strptime(raw, "%Y-%m")
            return raw
        except ValueError as exc:
            raise ValueError("event_time_invalid") from exc
    if not require_instant and len(raw) == 10 and raw[4] == "-":
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError as exc:
            raise ValueError("event_time_invalid") from exc
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp_invalid_iso8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp_must_include_timezone")
    if require_instant and ("T" not in raw and "t" not in raw):
        raise ValueError("available_at_must_be_datetime")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="auto").replace("+00:00", "Z")


def _canonical_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return {"$number": _canonical_decimal(value)}
    if isinstance(value, str):
        return _nfc(value)
    raise ValueError("logical_key_values_must_be_scalar")


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return rendered.encode("utf-8")


def _digest(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return f"{prefix}:sha256:{digest}"


def prepare_source_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and derive stable logical/version identifiers for one record.

    A logical ID is emitted only when the source supplies a stable
    source_record_id or the caller explicitly supplies a declared logical_key.
    The function never invents a natural key from row position or arrival order.
    """
    required = (
        "source_namespace", "dataset_id", "series_semantics", "entity_id",
        "metric_id", "event_time", "available_at", "value", "unit",
        "observation_status",
    )
    missing = [name for name in required if name not in record]
    if missing:
        raise ValueError("required_fields_missing:" + ",".join(missing))

    normalized: dict[str, Any] = dict(record)
    for field in ("source_namespace", "dataset_id", "entity_id", "metric_id"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field}_must_be_nonempty_string")
        normalized[field] = _nfc(value.strip())

    semantics = record["series_semantics"]
    if semantics not in VALID_SEMANTICS:
        raise ValueError("series_semantics_invalid")
    status = record["observation_status"]
    if status not in VALID_STATUSES:
        raise ValueError("observation_status_invalid")

    event_time = _canonical_event_time(record["event_time"])
    available_at = record["available_at"]
    available_at = (
        None if available_at is None
        else _canonical_event_time(available_at, require_instant=True)
    )

    value = record["value"]
    if status == "observed":
        canonical_value = _canonical_decimal(value)
    else:
        if value is not None:
            raise ValueError("non_observed_status_requires_null_value")
        canonical_value = None

    unit = record["unit"]
    if unit is not None and not isinstance(unit, str):
        raise ValueError("unit_must_be_string_or_null")
    unit = _nfc(unit) if isinstance(unit, str) else None

    source_record_id = record.get("source_record_id")
    if source_record_id is not None:
        if not isinstance(source_record_id, str) or not source_record_id.strip():
            raise ValueError("source_record_id_must_be_nonempty_string_or_null")
        source_record_id = _nfc(source_record_id.strip())

    logical_key = record.get("logical_key")
    if logical_key is not None:
        if not isinstance(logical_key, Mapping) or not logical_key:
            raise ValueError("logical_key_must_be_nonempty_object_or_null")
        normalized_key = {}
        for key, item in logical_key.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("logical_key_field_names_must_be_nonempty_strings")
            normalized_key[_nfc(key.strip())] = _canonical_scalar(item)
        logical_key = dict(sorted(normalized_key.items()))

    if source_record_id is not None:
        logical_basis = {"kind": "source_record_id", "value": source_record_id}
    elif logical_key is not None:
        logical_basis = {"kind": "declared_natural_key", "value": logical_key}
    else:
        logical_basis = None

    logical_record_id = None
    if logical_basis is not None:
        logical_payload = {
            "contract": CONTRACT_VERSION,
            "source_namespace": normalized["source_namespace"],
            "dataset_id": normalized["dataset_id"],
            "identity_basis": logical_basis,
        }
        logical_record_id = _digest("lrid:v1", logical_payload)

    source_revision = record.get("source_revision")
    if source_revision is not None:
        if not isinstance(source_revision, (str, int)) or isinstance(source_revision, bool):
            raise ValueError("source_revision_must_be_string_integer_or_null")
        source_revision = _nfc(str(source_revision))

    canonical_payload = {
        "contract": CONTRACT_VERSION,
        "source_namespace": normalized["source_namespace"],
        "dataset_id": normalized["dataset_id"],
        "identity_basis": logical_basis,
        "entity_id": normalized["entity_id"],
        "metric_id": normalized["metric_id"],
        "series_semantics": semantics,
        "event_time": event_time,
        "available_at": available_at,
        "source_revision": source_revision,
        "value": {"$number": canonical_value} if canonical_value is not None else None,
        "unit": unit,
        "observation_status": status,
    }
    canonical_record_id = _digest("crid:v1", canonical_payload)

    if semantics in {"event_stream", "period_count"}:
        multiplicity_policy = "PRESERVE_EACH_OCCURRENCE"
    else:
        multiplicity_policy = "PRESERVE_UNTIL_DUPLICATE_CONFIRMED_BY_SOURCE_CONTRACT"

    normalized.update({
        "event_time": event_time,
        "available_at": available_at,
        "source_record_id": source_record_id,
        "logical_key": logical_key,
        "source_revision": source_revision,
        "value": canonical_value,
        "unit": unit,
        "logical_record_id": logical_record_id,
        "canonical_record_id": canonical_record_id,
        "identity_basis": logical_basis["kind"] if logical_basis else "UNRESOLVED_NO_STABLE_KEY",
        "multiplicity_policy": multiplicity_policy,
    })
    return normalized


def canonical_order_key(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Order independent of ingest time, row number, and arrival sequence."""
    return (
        str(record["entity_id"]),
        str(record["metric_id"]),
        str(record["event_time"]),
        str(record.get("available_at") or ""),
        str(record["source_namespace"]),
        str(record["dataset_id"]),
        str(record.get("logical_record_id") or ""),
        str(record["canonical_record_id"]),
    )


def prepare_source_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Prepare and sort records while preserving every input occurrence."""
    prepared = [prepare_source_record(record) for record in records]
    return sorted(prepared, key=canonical_order_key)


def build_vintage_chains(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build immutable logical-record -> ordered canonical-vintage chains.

    Records without a stable logical ID remain unlinked observations. Versions
    with unknown available_at remain in the chain but sort after dated vintages;
    they cannot be used by point-in-time selection.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unlinked: list[dict[str, Any]] = []
    for raw in records:
        item = dict(raw)
        logical_id = item.get("logical_record_id")
        if logical_id is None:
            unlinked.append(item)
        else:
            grouped[str(logical_id)].append(item)

    chains: dict[str, list[dict[str, Any]]] = {}
    for logical_id, versions in sorted(grouped.items()):
        chains[logical_id] = sorted(
            versions,
            key=lambda item: (
                item.get("available_at") is None,
                str(item.get("available_at") or ""),
                str(item.get("canonical_record_id") or ""),
            ),
        )
    unlinked.sort(key=canonical_order_key)
    return {
        "chains": chains,
        "unlinked_records": unlinked,
        "logical_records": len(chains),
        "canonical_versions": sum(len(items) for items in chains.values()),
    }


def select_vintages_as_of(
    records: Iterable[Mapping[str, Any]], decision_time: str
) -> dict[str, Any]:
    """Select the latest unambiguous vintage available at decision_time.

    Unlinked records are retained as standalone observations if their
    available_at is known. Linked records are grouped only by logical_record_id.
    Equal latest available_at values with different canonical IDs are reported
    as ambiguous rather than broken by lexical revision or ingest order.
    """
    cutoff = _canonical_event_time(decision_time, require_instant=True)
    cutoff_dt = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    standalone: list[dict[str, Any]] = []
    missing_available_at = 0

    for raw in records:
        record = dict(raw)
        available_at = record.get("available_at")
        if available_at is None:
            missing_available_at += 1
            continue
        normalized_available = _canonical_event_time(available_at, require_instant=True)
        available_dt = datetime.fromisoformat(normalized_available.replace("Z", "+00:00"))
        if available_dt > cutoff_dt:
            continue
        record["available_at"] = normalized_available
        logical_id = record.get("logical_record_id")
        if logical_id is None:
            standalone.append(record)
        else:
            grouped[str(logical_id)].append(record)

    selected: list[dict[str, Any]] = list(standalone)
    ambiguous: list[dict[str, Any]] = []
    for logical_id, versions in sorted(grouped.items()):
        latest_time = max(item["available_at"] for item in versions)
        latest = [item for item in versions if item["available_at"] == latest_time]
        canonical_ids = {str(item["canonical_record_id"]) for item in latest}
        if len(canonical_ids) > 1:
            ambiguous.append({
                "logical_record_id": logical_id,
                "available_at": latest_time,
                "competing_canonical_record_ids": sorted(canonical_ids),
                "status": "AMBIGUOUS_SAME_AVAILABLE_AT",
            })
            continue
        # Preserve repeated occurrences even when their canonical content is identical.
        selected.extend(latest)

    selected.sort(key=canonical_order_key)
    return {
        "decision_time": cutoff,
        "selected": selected,
        "ambiguous": ambiguous,
        "missing_available_at_excluded": missing_available_at,
        "selection_policy": "LATEST_AVAILABLE_AT_PER_STABLE_LOGICAL_ID; NO_INGEST_ORDER_TIEBREAK; PRESERVE_MULTIPLICITY",
    }

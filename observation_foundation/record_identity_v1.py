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
ALLOWED_RECORD_FIELDS = {
    "source_namespace", "dataset_id", "series_semantics", "entity_id", "metric_id",
    "event_time", "available_at", "source_record_id", "logical_key", "source_revision",
    "revision_status", "value", "unit", "observation_status", "transport_metadata",
}
ALLOWED_TRANSPORT_FIELDS = {"retrieved_at", "ingest_batch_id", "row_number"}


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _canonical_decimal(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
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
        try:
            datetime.strptime(raw, "%Y")
            return raw
        except ValueError as exc:
            raise ValueError("event_time_invalid") from exc
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
        "metric_id", "event_time", "available_at", "revision_status", "value", "unit",
        "observation_status",
    )
    missing = [name for name in required if name not in record]
    if missing:
        raise ValueError("required_fields_missing:" + ",".join(missing))
    unknown = sorted(set(record) - ALLOWED_RECORD_FIELDS)
    if unknown:
        raise ValueError("unexpected_record_fields:" + ",".join(unknown))

    transport = record.get("transport_metadata")
    if "transport_metadata" in record:
        if not isinstance(transport, Mapping):
            raise ValueError("transport_metadata_must_be_object")
        unknown_transport = sorted(set(transport) - ALLOWED_TRANSPORT_FIELDS)
        if unknown_transport:
            raise ValueError("unexpected_transport_fields:" + ",".join(unknown_transport))
        retrieved_at = transport.get("retrieved_at")
        if retrieved_at is not None:
            _canonical_event_time(retrieved_at, require_instant=True)
        batch_id = transport.get("ingest_batch_id")
        if batch_id is not None and not isinstance(batch_id, str):
            raise ValueError("ingest_batch_id_must_be_string_or_null")
        row_number = transport.get("row_number")
        if row_number is not None and (
            not isinstance(row_number, int) or isinstance(row_number, bool) or row_number < 1
        ):
            raise ValueError("row_number_must_be_positive_integer_or_null")

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

    revision_status = record["revision_status"]
    if revision_status is not None:
        if not isinstance(revision_status, str) or not revision_status.strip():
            raise ValueError("revision_status_must_be_nonempty_string_or_null")
        revision_status = _nfc(revision_status.strip())

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
            canonical_key = _nfc(key.strip())
            if canonical_key in normalized_key:
                raise ValueError("logical_key_field_name_collision_after_unicode_normalization")
            normalized_key[canonical_key] = _canonical_scalar(item)
        logical_key = dict(sorted(normalized_key.items()))

    if source_record_id is not None:
        logical_basis = {"kind": "source_record_id", "value": source_record_id}
    elif logical_key is not None:
        logical_basis = {"kind": "declared_natural_key", "value": logical_key}
    elif semantics == "periodic_measurement":
        # One observation slot per entity/metric/time is the declared periodic key.
        logical_basis = {
            "kind": "periodic_series_key",
            "value": {
                "entity_id": normalized["entity_id"],
                "metric_id": normalized["metric_id"],
                "event_time": event_time,
            },
        }
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
        "revision_status": revision_status,
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
        "revision_status": revision_status,
        "value": value,
        "unit": unit,
        "logical_record_id": logical_record_id,
        "canonical_record_id": canonical_record_id,
        "identity_basis": logical_basis["kind"] if logical_basis else "UNRESOLVED_NO_STABLE_KEY",
        "multiplicity_policy": multiplicity_policy,
    })
    return normalized


def normalize_time_support(time_support: Mapping[str, Any]) -> dict[str, str]:
    """Validate source-declared series coverage in its native frequency.

    This metadata belongs to a series/collection, not to an individual record.
    Boundaries are never inferred from the first/last rows.
    """
    if not isinstance(time_support, Mapping):
        raise ValueError("time_support_must_be_object")
    allowed = {
        "observation_period_start", "observation_period_end",
        "native_frequency", "boundary_semantics",
    }
    unknown = sorted(set(time_support) - allowed)
    if unknown:
        raise ValueError("time_support_fields_invalid:" + ",".join(unknown))
    required = ("observation_period_start", "observation_period_end", "native_frequency")
    missing = [name for name in required if name not in time_support]
    if missing:
        raise ValueError("time_support_fields_missing:" + ",".join(missing))
    start = _canonical_event_time(time_support["observation_period_start"])
    end = _canonical_event_time(time_support["observation_period_end"])
    frequency = time_support["native_frequency"]
    if not isinstance(frequency, str) or not frequency.strip():
        raise ValueError("time_support_native_frequency_must_be_nonempty_string")
    if _event_time_sort_key(start) > _event_time_sort_key(end):
        raise ValueError("time_support_start_after_end")
    semantics = time_support.get("boundary_semantics", "SOURCE_DECLARED")
    if not isinstance(semantics, str) or not semantics.strip():
        raise ValueError("time_support_boundary_semantics_must_be_nonempty_string")
    return {
        "observation_period_start": start,
        "observation_period_end": end,
        "native_frequency": _nfc(frequency.strip()),
        "boundary_semantics": _nfc(semantics.strip()),
    }


def _parse_instant(value: str) -> datetime:
    normalized = _canonical_event_time(value, require_instant=True)
    return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(timezone.utc)


def _event_time_sort_key(value: str) -> tuple[datetime, int]:
    """Chronological sort key for native period labels and UTC instants."""
    normalized = _canonical_event_time(value)
    if len(normalized) == 4 and normalized.isdigit():
        return datetime(int(normalized), 1, 1, tzinfo=timezone.utc), 0
    if len(normalized) == 7 and normalized[4] == "-":
        year, month = (int(part) for part in normalized.split("-"))
        return datetime(year, month, 1, tzinfo=timezone.utc), 1
    if len(normalized) == 10 and normalized[4] == "-":
        year, month, day = (int(part) for part in normalized.split("-"))
        return datetime(year, month, day, tzinfo=timezone.utc), 2
    return _parse_instant(normalized), 3


def canonical_order_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    """Order independent of ingest time, row number, and arrival sequence."""
    available_at = record.get("available_at")
    available_key = (1, datetime.max.replace(tzinfo=timezone.utc)) if available_at is None else (0, _parse_instant(str(available_at)))
    return (
        str(record["entity_id"]),
        str(record["metric_id"]),
        _event_time_sort_key(str(record["event_time"])),
        available_key,
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
                datetime.max.replace(tzinfo=timezone.utc)
                if item.get("available_at") is None
                else _parse_instant(str(item["available_at"])),
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
    cutoff_dt = _parse_instant(cutoff)
    grouped: dict[str, list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    standalone: list[dict[str, Any]] = []
    missing_available_at = 0
    future_available_at = 0

    for raw in records:
        record = dict(raw)
        available_at = record.get("available_at")
        if available_at is None:
            missing_available_at += 1
            continue
        normalized_available = _canonical_event_time(available_at, require_instant=True)
        available_dt = _parse_instant(normalized_available)
        if available_dt > cutoff_dt:
            future_available_at += 1
            continue
        record["available_at"] = normalized_available
        logical_id = record.get("logical_record_id")
        if logical_id is None:
            standalone.append(record)
        else:
            grouped[str(logical_id)].append((available_dt, record))

    selected: list[dict[str, Any]] = list(standalone)
    ambiguous: list[dict[str, Any]] = []
    for logical_id, versions in sorted(grouped.items()):
        latest_time = max(available_dt for available_dt, _ in versions)
        latest = [record for available_dt, record in versions if available_dt == latest_time]
        canonical_ids = {str(item["canonical_record_id"]) for item in latest}
        if len(canonical_ids) > 1:
            ambiguous.append({
                "logical_record_id": logical_id,
                "source_namespace": latest[0]["source_namespace"],
                "dataset_id": latest[0]["dataset_id"],
                "available_at": latest[0]["available_at"],
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
        "future_available_at_excluded": future_available_at,
        "selection_policy": "LATEST_AVAILABLE_AT_PER_STABLE_LOGICAL_ID; NO_INGEST_ORDER_TIEBREAK; PRESERVE_MULTIPLICITY",
    }


def build_epoch_snapshot(
    records: Iterable[Mapping[str, Any]],
    decision_time: str,
    time_support: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, content-addressed point-in-time epoch manifest.

    Every selected occurrence contributes one canonical_record_id entry, so
    repeated events/counts remain multiplicity-preserving in the epoch digest.
    The returned selected_records are the exact normalized records for use by
    downstream computations; the manifest contains only stable lineage/IDs.
    """
    source_records = [dict(record) for record in records]
    required_identity_fields = {
        "source_namespace", "dataset_id", "entity_id", "metric_id",
        "event_time", "available_at", "canonical_record_id",
    }
    derived_fields = {
        "logical_record_id", "canonical_record_id", "identity_basis",
        "multiplicity_policy",
    }
    for index, record in enumerate(source_records):
        missing = sorted(required_identity_fields - set(record))
        if missing:
            raise ValueError(
                f"epoch_record_identity_fields_missing:index={index}:"
                + ",".join(missing)
            )
        unexpected = sorted(set(record) - ALLOWED_RECORD_FIELDS - derived_fields)
        if unexpected:
            raise ValueError(
                f"epoch_record_fields_invalid:index={index}:"
                + ",".join(unexpected)
            )
        canonical_id = record.get("canonical_record_id")
        if not isinstance(canonical_id, str) or not canonical_id.startswith("crid:v1:sha256:"):
            raise ValueError(f"epoch_canonical_record_id_invalid:index={index}")
        source_payload = {
            key: value for key, value in record.items()
            if key in ALLOWED_RECORD_FIELDS
        }
        recomputed = prepare_source_record(source_payload)
        if recomputed["canonical_record_id"] != canonical_id:
            raise ValueError(f"epoch_canonical_record_content_mismatch:index={index}")
        if recomputed["logical_record_id"] != record.get("logical_record_id"):
            raise ValueError(f"epoch_logical_record_identity_mismatch:index={index}")

    selection = select_vintages_as_of(source_records, decision_time)
    selected = selection["selected"]
    ambiguous = selection["ambiguous"]

    lineage_pairs = {
        (str(item["source_namespace"]), str(item["dataset_id"]))
        for item in source_records
    }
    source_lineage = [
        {"source_namespace": source, "dataset_id": dataset}
        for source, dataset in sorted(lineage_pairs)
    ]
    normalized_time_support = (
        normalize_time_support(time_support) if time_support is not None else None
    )
    manifest_payload = {
        "contract": "chaos-epoch-snapshot-v1",
        "time_support_status": "DECLARED" if normalized_time_support is not None else "NOT_DECLARED",
        "time_support": normalized_time_support,
        "decision_time": selection["decision_time"],
        "selection_policy": selection["selection_policy"],
        "source_lineage": source_lineage,
        "selected_occurrence_count": len(selected),
        "selected_canonical_record_ids": [
            str(item["canonical_record_id"]) for item in selected
        ],
        "unlinked_selected_occurrence_count": sum(
            item.get("logical_record_id") is None for item in selected
        ),
        "ambiguous": sorted(
            ambiguous,
            key=lambda item: (
                str(item["source_namespace"]),
                str(item["dataset_id"]),
                str(item["logical_record_id"]),
            ),
        ),
        "missing_available_at_excluded": selection["missing_available_at_excluded"],
        "future_available_at_excluded": selection["future_available_at_excluded"],
    }
    snapshot_sha256 = hashlib.sha256(_canonical_json(manifest_payload)).hexdigest()
    return {
        "epoch_id": f"epoch:v1:sha256:{snapshot_sha256}",
        "snapshot_sha256": snapshot_sha256,
        "manifest": manifest_payload,
        "selected_records": selected,
    }

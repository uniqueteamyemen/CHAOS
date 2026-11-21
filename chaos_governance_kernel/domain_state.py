from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, TextIO

from chaos_governance_kernel.core import sha256_file, utc_now, write_json

ALLOWED_EDGE_STATUSES = {
    "candidate", "supported_predictive", "unresolved", "rejected", "not_testable"
}
ALLOWED_DOMAINS = {
    "economic", "conflict", "energy", "trade", "environmental", "health",
    "institutions_policy", "institutional", "demographic", "other"
}
ALLOWED_FREQUENCIES = {
    "annual", "annual_source_defined_years", "monthly", "quarterly",
    "daily", "event", "source_defined_wave"
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_domain_state(
    record: Mapping[str, Any],
    required_fields: Iterable[str],
    expected_frequency: str | None = None,
    allowed_domains: Iterable[str] | None = None,
    allowed_frequencies: Iterable[str] | None = None,
) -> list[str]:
    """Return deterministic validation errors without mutating the source record."""
    errors: list[str] = []
    if not isinstance(record, Mapping):
        return ["record_must_be_object"]

    missing = sorted(set(required_fields) - set(record))
    if missing:
        errors.append("required_fields_missing:" + ",".join(missing))

    for field in ("pattern_id", "domain", "entity_id", "entity_name", "state_label"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field}_must_be_nonempty_string")

    domain = record.get("domain")
    domain_values = set(allowed_domains) if allowed_domains is not None else ALLOWED_DOMAINS
    if isinstance(domain, str) and domain not in domain_values:
        errors.append("domain_value_invalid")

    timestamp = record.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int)):
        errors.append("timestamp_must_be_native_string_or_integer")
    elif isinstance(timestamp, str) and not timestamp.strip():
        errors.append("timestamp_must_not_be_empty")

    frequency = record.get("native_frequency")
    frequency_values = set(allowed_frequencies) if allowed_frequencies is not None else ALLOWED_FREQUENCIES
    if not isinstance(frequency, str) or frequency not in frequency_values:
        errors.append("native_frequency_invalid")
    elif expected_frequency is not None and frequency != expected_frequency:
        errors.append(f"native_frequency_mismatch:expected={expected_frequency}:actual={frequency}")

    probability = record.get("state_probability")
    if probability is not None:
        if not _is_number(probability) or not 0.0 <= float(probability) <= 1.0:
            errors.append("state_probability_must_be_null_or_finite_0_to_1")

    for field in ("source_observations", "lead_profile"):
        if not isinstance(record.get(field), Mapping):
            errors.append(f"{field}_must_be_object")

    for field in ("uncertainty", "failure_cases", "evidence_refs"):
        value = record.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(f"{field}_must_be_array_of_nonempty_strings")

    edge_status = record.get("edge_status")
    if edge_status not in ALLOWED_EDGE_STATUSES:
        errors.append("edge_status_invalid")

    return errors


def domain_state_identity(record: Mapping[str, Any]) -> str:
    """Content-independent identity for a state slot; it never deduplicates records."""
    payload = {
        "schema": "CHAOS_DOMAIN_STATE_ID_V1",
        "domain": record["domain"],
        "entity_id": record["entity_id"],
        "pattern_id": record["pattern_id"],
        "timestamp": record["timestamp"],
        "native_frequency": record["native_frequency"],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "domain-state:v1:sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _open_jsonl(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")  # type: ignore[return-value]
    return path.open("r", encoding="utf-8")


def audit_domain_state_file(
    root: Path,
    relative_path: str,
    required_fields: Iterable[str],
    expected_frequency: str | None = None,
    max_errors: int = 100,
    allowed_domains: Iterable[str] | None = None,
    allowed_frequencies: Iterable[str] | None = None,
) -> dict[str, Any]:
    path = root / relative_path
    base: dict[str, Any] = {
        "path": relative_path,
        "expected_frequency": expected_frequency,
        "status": "missing",
        "records": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "duplicate_state_slots": 0,
        "domains": {},
        "frequencies": {},
        "entities": 0,
        "state_labels": {},
        "errors": [],
    }
    if not path.is_file():
        return base

    identity_counts: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    frequencies: Counter[str] = Counter()
    entities: set[str] = set()
    labels: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []
    invalid = 0

    try:
        with _open_jsonl(path) as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                base["records"] += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    invalid += 1
                    if len(errors) < max_errors:
                        errors.append({"line": line_number, "error": f"invalid_json:{exc.msg}"})
                    continue

                problems = validate_domain_state(
                    record, required_fields, expected_frequency,
                    allowed_domains=allowed_domains,
                    allowed_frequencies=allowed_frequencies,
                )
                if problems:
                    invalid += 1
                    if len(errors) < max_errors:
                        errors.append({"line": line_number, "errors": problems})
                    continue

                base["valid_records"] += 1
                identity_counts[domain_state_identity(record)] += 1
                domains[str(record["domain"])] += 1
                frequencies[str(record["native_frequency"])] += 1
                entities.add(str(record["entity_id"]))
                labels[str(record["state_label"])] += 1
    except (OSError, UnicodeError) as exc:
        base["status"] = "invalid"
        base["errors"] = [{"line": None, "error": f"read_error:{type(exc).__name__}:{exc}"}]
        return base

    duplicate_slots = sum(count - 1 for count in identity_counts.values() if count > 1)
    base.update({
        "status": "invalid" if invalid else ("empty" if base["records"] == 0 else "pass"),
        "invalid_records": invalid,
        "duplicate_state_slots": duplicate_slots,
        "domains": dict(sorted(domains.items())),
        "frequencies": dict(sorted(frequencies.items())),
        "entities": len(entities),
        "state_labels": dict(sorted(labels.items())),
        "errors": errors,
        "errors_truncated": invalid > len(errors),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "duplicate_policy": "PRESERVED_AND_REPORTED; no record is removed",
    })
    return base


def build_domain_state_integrity_report(
    root: Path,
    registry_path: Path,
    output_path: Path,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    schema_path = schema_path or (root / "experimental_contracts" / "DOMAIN_STATE_SCHEMA_V2.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else {}
    required_fields = schema.get("required_fields") or registry.get("required_fields")
    registry_required_fields = registry.get("required_fields")
    files = registry.get("files")
    if schema and set(required_fields) != set(registry_required_fields or []):
        raise ValueError("registry_schema_required_fields_mismatch")
    allowed_domains = schema.get("domain_values") or ALLOWED_DOMAINS
    allowed_frequencies = schema.get("native_frequency_values") or ALLOWED_FREQUENCIES
    if not isinstance(required_fields, list) or not required_fields:
        raise ValueError("registry_required_fields_missing")
    if not isinstance(files, list) or not files:
        raise ValueError("registry_files_missing")

    file_reports = [
        audit_domain_state_file(
            root=root,
            relative_path=item["path"],
            required_fields=required_fields,
            expected_frequency=item.get("native_frequency"),
            allowed_domains=allowed_domains,
            allowed_frequencies=allowed_frequencies,
        )
        for item in files
    ]
    counts = Counter(item["status"] for item in file_reports)
    total_records = sum(item["records"] for item in file_reports)
    invalid_records = sum(item["invalid_records"] for item in file_reports)
    missing_paths = [item["path"] for item in file_reports if item["status"] == "missing"]
    invalid_paths = [item["path"] for item in file_reports if item["status"] == "invalid"]
    empty_paths = [item["path"] for item in file_reports if item["status"] == "empty"]

    if invalid_paths or empty_paths:
        readiness = "FAIL"
    elif missing_paths:
        readiness = "BLOCKED_INCOMPLETE_ASSET_SET"
    else:
        readiness = "PASS"

    report = {
        "report_id": "CHAOS_DOMAIN_STATE_INTEGRITY_V2",
        "generated_at": utc_now(),
        "repository": "uniqueteamyemen/CHAOS",
        "registry_source": registry_path.relative_to(root).as_posix(),
        "schema_source": schema_path.relative_to(root).as_posix() if schema_path.is_file() else None,
        "schema_id": schema.get("schema_id"),
        "schema_version": schema.get("version"),
        "required_fields": required_fields,
        "read_only": True,
        "no_source_mutations": True,
        "files_registered": len(files),
        "files_by_status": dict(sorted(counts.items())),
        "records_seen": total_records,
        "invalid_records": invalid_records,
        "missing_references": missing_paths,
        "invalid_files": invalid_paths,
        "empty_files": empty_paths,
        "readiness": readiness,
        "policy": {
            "native_frequency_must_match_registry": True,
            "state_probability_is_optional_and_not_causal_confidence": True,
            "duplicate_state_slots_are_reported_not_removed": True,
            "missing_source_artifacts_are_not_reconstructed_or_imputed": True,
            "historical_experiment_files_are_read_only": True,
        },
        "files": file_reports,
    }
    write_json(output_path, report)
    return report

"""Explicit, lossless adaptation from CHAOS DomainState envelopes to source observations.

No metric, unit, availability time, revision order, natural key, or frequency
conversion is inferred. Every mapping and the source-declared time envelope
must be supplied by a versioned adapter contract.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .record_identity_v1 import (
    canonical_order_key,
    normalize_time_support,
    prepare_source_record,
)

ADAPTER_CONTRACT_ID = "domain-state-observation-adapter-v1"
ADAPTER_FIELDS = {
    "adapter_id", "source_namespace", "dataset_id", "domain",
    "native_frequency", "series_semantics", "entity_id_path",
    "event_time_path", "time_support", "available_at_path",
    "source_record_id_path", "source_revision_path", "revision_status_path",
    "metrics",
}
REQUIRED_ADAPTER_FIELDS = {
    "adapter_id", "source_namespace", "dataset_id", "domain",
    "native_frequency", "series_semantics", "entity_id_path",
    "event_time_path", "time_support", "metrics",
}
METRIC_FIELDS = {
    "metric_id", "value_path", "unit", "unit_path",
    "available_at_path", "source_record_id_path",
    "source_revision_path", "revision_status_path",
    "observation_status_path",
}
REQUIRED_METRIC_FIELDS = {"metric_id", "value_path"}


class DomainStateAdapterError(ValueError):
    """Raised when a DomainState cannot be mapped without guessing."""


def _path(value: Any, field: str, *, required: bool) -> tuple[str, ...] | None:
    if value is None and not required:
        return None
    if not isinstance(value, list) or not value:
        raise DomainStateAdapterError(f"{field}_must_be_nonempty_string_array")
    if any(not isinstance(part, str) or not part.strip() for part in value):
        raise DomainStateAdapterError(f"{field}_path_segments_must_be_nonempty_strings")
    return tuple(part.strip() for part in value)


def _read_path(root: Mapping[str, Any], path: Sequence[str], field: str) -> Any:
    current: Any = root
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            raise DomainStateAdapterError(f"source_path_missing:{field}:{'.'.join(path)}")
        current = current[segment]
    return current


def _text_identifier(value: Any, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DomainStateAdapterError(f"{field}_must_be_string_or_integer")
    rendered = str(value).strip()
    if not rendered:
        raise DomainStateAdapterError(f"{field}_must_be_nonempty")
    return rendered


def _event_time(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DomainStateAdapterError("event_time_must_be_native_string_or_integer")
    rendered = str(value).strip()
    if not rendered:
        raise DomainStateAdapterError("event_time_must_be_nonempty")
    return rendered


def _read_optional(
    state: Mapping[str, Any],
    metric: Mapping[str, Any],
    adapter: Mapping[str, Any],
    field: str,
) -> Any:
    selected = metric.get(f"{field}_path", adapter.get(f"{field}_path"))
    if selected is None:
        return None
    path = _path(selected, f"{field}_path", required=True)
    assert path is not None
    return _read_path(state, path, field)


def validate_adapter_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the explicit mapping and return its canonical time-support envelope."""
    if not isinstance(contract, Mapping):
        raise DomainStateAdapterError("adapter_contract_must_be_object")
    missing = sorted(REQUIRED_ADAPTER_FIELDS - set(contract))
    if missing:
        raise DomainStateAdapterError("adapter_contract_missing:" + ",".join(missing))
    unknown = sorted(set(contract) - ADAPTER_FIELDS)
    if unknown:
        raise DomainStateAdapterError("adapter_contract_unknown:" + ",".join(unknown))

    for field in ("adapter_id", "source_namespace", "dataset_id", "domain", "native_frequency"):
        value = contract.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DomainStateAdapterError(f"{field}_must_be_nonempty_string")
    if contract.get("series_semantics") not in {
        "periodic_measurement", "event_stream", "period_count"
    }:
        raise DomainStateAdapterError("series_semantics_invalid")

    _path(contract.get("entity_id_path"), "entity_id", required=True)
    _path(contract.get("event_time_path"), "event_time", required=True)
    time_support = normalize_time_support(contract.get("time_support"))
    if time_support["native_frequency"] != contract["native_frequency"]:
        raise DomainStateAdapterError("adapter_time_support_frequency_mismatch")

    for field in ("available_at", "source_record_id", "source_revision", "revision_status"):
        _path(contract.get(f"{field}_path"), field, required=False)

    metrics = contract.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise DomainStateAdapterError("metrics_must_be_nonempty_array")
    seen_metric_ids: set[str] = set()
    for index, metric in enumerate(metrics):
        if not isinstance(metric, Mapping):
            raise DomainStateAdapterError(f"metric_must_be_object:index={index}")
        missing_metric = sorted(REQUIRED_METRIC_FIELDS - set(metric))
        if missing_metric:
            raise DomainStateAdapterError(
                f"metric_fields_missing:index={index}:" + ",".join(missing_metric)
            )
        unknown_metric = sorted(set(metric) - METRIC_FIELDS)
        if unknown_metric:
            raise DomainStateAdapterError(
                f"metric_fields_unknown:index={index}:" + ",".join(unknown_metric)
            )
        metric_id = metric.get("metric_id")
        if not isinstance(metric_id, str) or not metric_id.strip():
            raise DomainStateAdapterError(f"metric_id_invalid:index={index}")
        if metric_id in seen_metric_ids:
            raise DomainStateAdapterError(f"metric_id_duplicate:{metric_id}")
        seen_metric_ids.add(metric_id)
        _path(metric.get("value_path"), f"metrics[{index}].value", required=True)

        has_unit = "unit" in metric
        has_unit_path = metric.get("unit_path") is not None
        if has_unit == has_unit_path:
            raise DomainStateAdapterError(
                f"metric_unit_requires_exactly_one_of_unit_or_unit_path:index={index}"
            )
        if has_unit and metric["unit"] is not None and not isinstance(metric["unit"], str):
            raise DomainStateAdapterError(f"metric_unit_invalid:index={index}")
        if has_unit_path:
            _path(metric.get("unit_path"), f"metrics[{index}].unit", required=True)

        for field in (
            "available_at", "source_record_id", "source_revision",
            "revision_status", "observation_status",
        ):
            if metric.get(f"{field}_path") is not None:
                _path(metric[f"{field}_path"], f"metrics[{index}].{field}", required=True)
    return time_support


def adapt_domain_state(
    state: Mapping[str, Any], contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Convert one DomainState row into one source observation per declared metric."""
    time_support = validate_adapter_contract(contract)
    if not isinstance(state, Mapping):
        raise DomainStateAdapterError("domain_state_must_be_object")

    required_state = {
        "pattern_id", "domain", "entity_id", "timestamp", "native_frequency",
        "state_label", "source_observations", "evidence_refs",
    }
    missing_state = sorted(required_state - set(state))
    if missing_state:
        raise DomainStateAdapterError("domain_state_fields_missing:" + ",".join(missing_state))
    if state["domain"] != contract["domain"]:
        raise DomainStateAdapterError("domain_mismatch")
    if state["native_frequency"] != contract["native_frequency"]:
        raise DomainStateAdapterError("native_frequency_mismatch")
    if not isinstance(state["source_observations"], Mapping):
        raise DomainStateAdapterError("source_observations_must_be_object")
    if not isinstance(state["pattern_id"], str) or not state["pattern_id"].strip():
        raise DomainStateAdapterError("domain_state_pattern_id_invalid")
    if not isinstance(state["state_label"], str) or not state["state_label"].strip():
        raise DomainStateAdapterError("domain_state_label_invalid")

    entity_path = _path(contract["entity_id_path"], "entity_id", required=True)
    time_path = _path(contract["event_time_path"], "event_time", required=True)
    assert entity_path is not None and time_path is not None
    entity_id = _text_identifier(_read_path(state, entity_path, "entity_id"), "entity_id")
    event_time = _event_time(_read_path(state, time_path, "event_time"))

    evidence_refs = state.get("evidence_refs")
    if not isinstance(evidence_refs, list) or any(
        not isinstance(item, str) for item in evidence_refs
    ):
        raise DomainStateAdapterError("evidence_refs_must_be_string_array")

    adapted: list[dict[str, Any]] = []
    for metric in contract["metrics"]:
        metric_id = metric["metric_id"]
        value_path = _path(metric["value_path"], f"{metric_id}.value", required=True)
        assert value_path is not None
        value = _read_path(state, value_path, f"{metric_id}.value")

        if "unit" in metric:
            unit = metric["unit"]
        else:
            unit_path = _path(metric["unit_path"], f"{metric_id}.unit", required=True)
            assert unit_path is not None
            unit = _read_path(state, unit_path, f"{metric_id}.unit")
        if unit is not None and not isinstance(unit, str):
            raise DomainStateAdapterError(f"unit_invalid:{metric_id}")

        available_at = _read_optional(state, metric, contract, "available_at")
        if available_at is not None and not isinstance(available_at, str):
            raise DomainStateAdapterError(f"available_at_invalid:{metric_id}")

        source_record_id = _read_optional(state, metric, contract, "source_record_id")
        if source_record_id is not None:
            source_record_id = _text_identifier(source_record_id, "source_record_id")

        source_revision = _read_optional(state, metric, contract, "source_revision")
        if source_revision is not None and (
            isinstance(source_revision, bool) or not isinstance(source_revision, (str, int))
        ):
            raise DomainStateAdapterError(f"source_revision_invalid:{metric_id}")

        revision_status = _read_optional(state, metric, contract, "revision_status")
        if revision_status is not None and not isinstance(revision_status, str):
            raise DomainStateAdapterError(f"revision_status_invalid:{metric_id}")

        status_path = metric.get("observation_status_path")
        if status_path is None:
            observation_status = "observed" if value is not None else "missing"
        else:
            parsed_status_path = _path(
                status_path, f"{metric_id}.observation_status", required=True
            )
            assert parsed_status_path is not None
            observation_status = _read_path(
                state, parsed_status_path, f"{metric_id}.observation_status"
            )

        source_record = prepare_source_record({
            "source_namespace": contract["source_namespace"],
            "dataset_id": contract["dataset_id"],
            "series_semantics": contract["series_semantics"],
            "entity_id": entity_id,
            "metric_id": metric_id,
            "event_time": event_time,
            "available_at": available_at,
            "source_record_id": source_record_id,
            "source_revision": source_revision,
            "revision_status": revision_status,
            "value": value,
            "unit": unit,
            "observation_status": observation_status,
        })
        if not (
            time_support["observation_period_start"]
            <= source_record["event_time"]
            <= time_support["observation_period_end"]
        ):
            raise DomainStateAdapterError("event_time_outside_declared_time_support")

        adapted.append({
            "observation": source_record,
            "lineage": {
                "adapter_contract_id": ADAPTER_CONTRACT_ID,
                "adapter_id": contract["adapter_id"],
                "domain": state["domain"],
                "native_frequency": state["native_frequency"],
                "domain_state_pattern_id": state["pattern_id"],
                "domain_state_label": state["state_label"],
                "domain_state_timestamp": state["timestamp"],
                "source_value_path": ".".join(value_path),
                "evidence_refs": list(evidence_refs),
            },
        })
    return adapted


def adapt_domain_states(
    states: Iterable[Mapping[str, Any]], contract: Mapping[str, Any]
) -> dict[str, Any]:
    """Adapt a collection deterministically without collapsing repeated observations."""
    time_support = validate_adapter_contract(contract)
    records: list[dict[str, Any]] = []
    input_count = 0
    for state in states:
        input_count += 1
        records.extend(adapt_domain_state(state, contract))

    records.sort(key=lambda item: (
        canonical_order_key(item["observation"]),
        item["lineage"]["domain_state_pattern_id"],
        item["lineage"]["source_value_path"],
    ))
    observations = [item["observation"] for item in records]
    return {
        "adapter_contract_id": ADAPTER_CONTRACT_ID,
        "adapter_id": contract["adapter_id"],
        "input_domain_state_count": input_count,
        "output_observation_count": len(records),
        "unknown_availability_count": sum(
            item["available_at"] is None for item in observations
        ),
        "unlinked_observation_count": sum(
            item["logical_record_id"] is None for item in observations
        ),
        "native_frequency": contract["native_frequency"],
        "time_support": time_support,
        "records": records,
    }

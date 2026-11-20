"""Separate hypothesis lifecycle from input-data disposition."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unicodedata
from typing import Any, Mapping

from chaos_governance_kernel.core import append_research_ledger_record, canonical_sha256

HYPOTHESIS_STATES = {
    "CANDIDATE", "UNDER_TEST", "DISCOVERED", "VALIDATION_PENDING",
    "VALIDATED", "REJECTED", "LOCKED_REJECTED", "UNRESOLVED",
}
INPUT_DISPOSITIONS = {"ACCEPT", "ABSTAIN", "QUARANTINE", "REJECT"}
_ALLOWED_TRANSITIONS = {
    "CANDIDATE": {"UNDER_TEST", "UNRESOLVED"},
    "UNDER_TEST": {"DISCOVERED", "REJECTED", "UNRESOLVED"},
    "DISCOVERED": {"VALIDATION_PENDING", "UNRESOLVED"},
    "VALIDATION_PENDING": {"VALIDATED", "REJECTED", "UNRESOLVED"},
    "REJECTED": {"LOCKED_REJECTED"},
    "VALIDATED": set(),
    "LOCKED_REJECTED": set(),
    "UNRESOLVED": set(),
}
_TRIGGER_FIELDS = ("kind", "observed_at", "evidence_ref", "description")
VALID_TRIGGER_KINDS = {
    "source_vintage_changed",
    "source_schema_changed",
    "source_namespace_changed",
    "dataset_scope_changed",
    "domain_definition_changed",
    "observation_contract_changed",
    "external_system_changed",
    "catalog_completeness_changed",
    "measurement_regime_changed",
    "independent_evidence_added",
}


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_must_be_nonempty_string")
    return unicodedata.normalize("NFC", value.strip())


def _validate_trigger_shift(trigger_shift: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(trigger_shift, Mapping):
        raise ValueError("trigger_shift_required_for_new_hypothesis_version")
    unknown = sorted(set(trigger_shift) - set(_TRIGGER_FIELDS))
    if unknown:
        raise ValueError("trigger_shift_fields_invalid:" + ",".join(unknown))
    result = {
        field: _required_text(trigger_shift.get(field), f"trigger_shift_{field}")
        for field in _TRIGGER_FIELDS
    }
    if result["kind"] not in VALID_TRIGGER_KINDS:
        if "threshold" in result["kind"].casefold():
            raise ValueError("threshold_only_change_is_not_trigger_shift")
        raise ValueError("trigger_shift_kind_invalid")
    stamp = result["observed_at"].replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise ValueError("trigger_shift_observed_at_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("trigger_shift_observed_at_requires_timezone")
    result["observed_at"] = parsed.astimezone(timezone.utc).isoformat(timespec="auto").replace("+00:00", "Z")
    return result


def transition_hypothesis(
    hypothesis: Mapping[str, Any], next_status: str
) -> dict[str, Any]:
    """Apply one same-version lifecycle transition; never mutates input."""
    current = hypothesis.get("status")
    if current not in HYPOTHESIS_STATES:
        raise ValueError("hypothesis_status_invalid")
    if next_status not in HYPOTHESIS_STATES:
        raise ValueError("hypothesis_status_invalid")
    if next_status not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"hypothesis_transition_forbidden:{current}->{next_status}")
    updated = deepcopy(dict(hypothesis))
    updated["status"] = next_status
    return updated


def create_triggered_hypothesis_version(
    previous: Mapping[str, Any], trigger_shift: Mapping[str, Any]
) -> dict[str, Any]:
    """Create a new candidate version after a documented trigger/data shift.

    The previous record is left unchanged and is referenced through supersedes.
    Trigger kinds are allowlisted; descriptions cannot promote a threshold edit.
    """
    current = previous.get("status")
    if current not in HYPOTHESIS_STATES:
        raise ValueError("hypothesis_status_invalid")
    trigger = _validate_trigger_shift(trigger_shift)
    hypothesis_id = _required_text(previous.get("hypothesis_id"), "hypothesis_id")
    version = previous.get("hypothesis_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("hypothesis_version_must_be_positive_integer")
    new_record = deepcopy(dict(previous))
    new_record["hypothesis_version"] = version + 1
    new_record["status"] = "CANDIDATE"
    new_record["supersedes"] = {
        "hypothesis_id": hypothesis_id,
        "hypothesis_version": version,
        "previous_status": current,
    }
    new_record["trigger_shift"] = trigger
    return new_record


def validate_input_disposition(
    input_ref: str, status: str, reason: str
) -> dict[str, str]:
    """Validate the independent disposition of an input/evidence item."""
    if status not in INPUT_DISPOSITIONS:
        raise ValueError("input_disposition_invalid")
    return {
        "input_ref": _required_text(input_ref, "input_ref"),
        "status": status,
        "reason": _required_text(reason, "reason"),
    }


DEFAULT_RESEARCH_LEDGER_PATH = Path("governance/ledger/RESEARCH_LEDGER_V1.jsonl")
RESEARCH_LEDGER_CONTRACT_REF = "experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json"


def _normalize_decision_time(value: str) -> str:
    stamp = _required_text(value, "decision_at_utc").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise ValueError("decision_at_utc_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("decision_at_utc_requires_timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="auto").replace("+00:00", "Z")


def build_lifecycle_ledger_record(
    *,
    input_disposition: Mapping[str, Any],
    hypothesis_before: Mapping[str, Any],
    hypothesis_after: Mapping[str, Any],
    decision_at_utc: str,
    source_refs: list[str],
    input_hashes: Mapping[str, str],
    output_refs: list[str],
    notes: str,
    contract_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build one ledger entry containing separate input and hypothesis decisions.

    Same-version transitions are validated against the allowlisted lifecycle.
    New versions are accepted only when they exactly match a documented trigger
    shift and preserve the old hypothesis through the supersedes reference.
    """
    disposition = validate_input_disposition(
        input_disposition.get("input_ref"),
        input_disposition.get("status"),
        input_disposition.get("reason"),
    )
    before = deepcopy(dict(hypothesis_before))
    after = deepcopy(dict(hypothesis_after))
    if after.get("hypothesis_id") != before.get("hypothesis_id"):
        raise ValueError("ledger_hypothesis_identity_changed")
    before_version = before.get("hypothesis_version")
    after_version = after.get("hypothesis_version")
    if before_version == after_version:
        expected_after = transition_hypothesis(before, str(after.get("status")))
        if expected_after != after:
            raise ValueError("ledger_hypothesis_transition_payload_mismatch")
        trigger_shift = None
    elif (
        isinstance(before_version, int) and not isinstance(before_version, bool)
        and after_version == before_version + 1
    ):
        trigger_shift = after.get("trigger_shift")
        expected_after = create_triggered_hypothesis_version(before, trigger_shift)
        if expected_after != after:
            raise ValueError("ledger_hypothesis_version_payload_mismatch")
    else:
        raise ValueError("ledger_hypothesis_version_transition_invalid")

    decision_time = _normalize_decision_time(decision_at_utc)
    refs = sorted({_required_text(item, "source_ref") for item in source_refs} | {disposition["input_ref"]})
    outputs = sorted({_required_text(item, "output_ref") for item in output_refs})
    if not outputs:
        outputs = [f"hypothesis://{before['hypothesis_id']}/v{after_version}"]
    hashes: dict[str, str] = {}
    for reference, digest in input_hashes.items():
        source_ref = _required_text(reference, "input_hash_ref")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("ledger_input_hash_must_be_sha256")
        if any(ch not in "0123456789abcdefABCDEF" for ch in digest):
            raise ValueError("ledger_input_hash_must_be_sha256")
        hashes[source_ref] = digest.lower()
    if not hashes:
        raise ValueError("ledger_input_hashes_required")
    note = _required_text(notes, "notes")
    contexts = sorted(set(contract_refs or []) | {
        "observation_foundation/contracts/input_disposition_v1.schema.json",
        "observation_foundation/contracts/hypothesis_lifecycle_v1.schema.json",
    })
    for ref in contexts:
        _required_text(ref, "contract_ref")

    decision_context = {
        "input_disposition": disposition,
        "hypothesis_transition": {
            "hypothesis_id": before["hypothesis_id"],
            "version_before": before_version,
            "version_after": after_version,
            "status_before": before["status"],
            "status_after": after["status"],
            "supersedes": after.get("supersedes"),
            "trigger_shift": trigger_shift,
        },
        "contract_refs": contexts,
    }
    payload = {
        "record_type": "pattern_decision",
        "created_at_utc": decision_time,
        "source_refs": refs,
        "contract_ref": RESEARCH_LEDGER_CONTRACT_REF,
        "input_hashes": hashes,
        "output_refs": outputs,
        "status": "RECORDED",
        "notes": note,
        "decision_context": decision_context,
    }
    ledger_id = "ledger:v1:sha256:" + canonical_sha256(payload)
    return {"ledger_id": ledger_id, **payload}


def append_lifecycle_decision(
    *,
    input_disposition: Mapping[str, Any],
    hypothesis_before: Mapping[str, Any],
    hypothesis_after: Mapping[str, Any],
    decision_at_utc: str,
    source_refs: list[str],
    input_hashes: Mapping[str, str],
    output_refs: list[str],
    notes: str,
    ledger_path: Path = DEFAULT_RESEARCH_LEDGER_PATH,
    contract_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Persist both decisions as one append-only entry in the shared Research Ledger."""
    record = build_lifecycle_ledger_record(
        input_disposition=input_disposition,
        hypothesis_before=hypothesis_before,
        hypothesis_after=hypothesis_after,
        decision_at_utc=decision_at_utc,
        source_refs=source_refs,
        input_hashes=input_hashes,
        output_refs=output_refs,
        notes=notes,
        contract_refs=contract_refs,
    )
    return append_research_ledger_record(ledger_path, record)

"""Separate hypothesis lifecycle from input-data disposition."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import unicodedata
from typing import Any, Mapping

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


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_must_be_nonempty_string")
    return unicodedata.normalize("NFC", value.strip())


def _validate_trigger_shift(trigger_shift: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(trigger_shift, Mapping):
        raise ValueError("trigger_shift_required_for_new_hypothesis_version")
    result = {
        field: _required_text(trigger_shift.get(field), f"trigger_shift_{field}")
        for field in _TRIGGER_FIELDS
    }
    stamp = result["observed_at"].replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise ValueError("trigger_shift_observed_at_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("trigger_shift_observed_at_requires_timezone")
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
    A threshold-only adjustment is not an accepted trigger-shift description.
    """
    current = previous.get("status")
    if current not in HYPOTHESIS_STATES:
        raise ValueError("hypothesis_status_invalid")
    trigger = _validate_trigger_shift(trigger_shift)
    kind_text = trigger["kind"].casefold()
    description = trigger["description"].casefold()
    if "threshold" in kind_text and not any(
        token in description for token in ("data", "source", "contract", "regime", "scope")
    ):
        raise ValueError("threshold_only_change_is_not_trigger_shift")
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

"""P1.4 runtime authorization against a schema-validated capability envelope.

PILOT_ELIGIBLE is deliberately distinct from scientific validation and production
authorization. Unknown or malformed tools fail closed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[1]
_ENVELOPE_PATH = _ROOT / "p1_4_validation" / "capability_envelope.json"
_SCHEMA_PATH = _ROOT / "p1_4_validation" / "capability_envelope.schema.json"


class CapabilityViolation(RuntimeError):
    def __init__(self, decision: Mapping[str, Any]):
        self.decision = dict(decision)
        reason = ",".join(self.decision.get("reason_codes", ())) or "NOT_ELIGIBLE"
        super().__init__(f"CAPABILITY_NOT_ELIGIBLE:{self.decision.get('tool')}:{reason}")


def _is_type(value: Any, expected: str | list[str]) -> bool:
    kinds = [expected] if isinstance(expected, str) else expected
    for kind in kinds:
        if kind == "null" and value is None:
            return True
        if kind == "object" and isinstance(value, dict):
            return True
        if kind == "array" and isinstance(value, list):
            return True
        if kind == "string" and isinstance(value, str):
            return True
        if kind == "boolean" and isinstance(value, bool):
            return True
        if kind == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if kind == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    return False


def _validate_schema(value: Any, schema: dict[str, Any], path: str, root_schema: dict[str, Any]) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"unsupported_schema_reference:{path}:{ref}")
        target = root_schema.get("$defs", {}).get(ref.split("/")[-1])
        if not isinstance(target, dict):
            raise ValueError(f"unresolved_schema_reference:{path}:{ref}")
        _validate_schema(value, target, path, root_schema)
        return
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"schema_const_violation:{path}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"schema_enum_violation:{path}")
    expected = schema.get("type")
    if expected is not None and not _is_type(value, expected):
        raise ValueError(f"schema_type_violation:{path}:{expected}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = sorted(set(required) - set(value))
        if missing:
            raise ValueError(f"schema_required_fields_missing:{path}:{','.join(missing)}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(props))
            if extra:
                raise ValueError(f"schema_additional_properties:{path}:{','.join(extra)}")
        for key, child in value.items():
            if key in props:
                _validate_schema(child, props[key], f"{path}.{key}", root_schema)
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate_schema(child, schema["additionalProperties"], f"{path}.{key}", root_schema)
    if isinstance(value, list):
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True, ensure_ascii=False) for x in value}) != len(value):
            raise ValueError(f"schema_unique_items_violation:{path}")
        if len(value) < int(schema.get("minItems", 0)):
            raise ValueError(f"schema_min_items_violation:{path}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                _validate_schema(child, item_schema, f"{path}[{index}]", root_schema)
    if isinstance(value, str) and len(value) < int(schema.get("minLength", 0)):
        raise ValueError(f"schema_min_length_violation:{path}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"schema_minimum_violation:{path}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"schema_maximum_violation:{path}")
    if "minProperties" in schema and isinstance(value, dict) and len(value) < schema["minProperties"]:
        raise ValueError(f"schema_min_properties_violation:{path}")


def load_envelope(envelope_path: Path | None = None, schema_path: Path | None = None) -> dict[str, Any]:
    envelope_file = _ENVELOPE_PATH if envelope_path is None else Path(envelope_path)
    schema_file = _SCHEMA_PATH if schema_path is None else Path(schema_path)
    document = json.loads(envelope_file.read_text(encoding="utf-8"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    _validate_schema(document, schema, "$", schema)
    if document["decision_contract"]["default"] != "fail_closed":
        raise ValueError("capability_envelope_must_fail_closed")
    if document["decision_contract"]["production_authorization"] is not False:
        raise ValueError("pilot_envelope_must_not_authorize_production")
    if document["common_controls"]["reserve_quiet_window_from_detection"] is not True:
        raise ValueError("quiet_calibration_window_must_be_reserved")
    if document["common_controls"]["no_future_suffix_access"] is not True:
        raise ValueError("future_suffix_access_must_be_forbidden")
    for key, spec in document["capabilities"].items():
        if spec["name"] != key:
            raise ValueError(f"capability_key_name_mismatch:{key}")
        if spec["not_standalone_detector"] and spec["role"] != "calibrator":
            raise ValueError(f"standalone_flag_role_mismatch:{key}")
        if spec["scientific_validation_status"] == "VALIDATED" and not any(
            row["validated_role"] for row in spec["validation_history"]
        ):
            raise ValueError(f"validated_without_role_evidence:{key}")
    return document


def envelope_sha256() -> str:
    return hashlib.sha256(_ENVELOPE_PATH.read_bytes()).hexdigest()


def assess_capability(
    tool: str,
    *,
    operation: str,
    intended_role: str | None = None,
    observations: int | None = None,
    prebreak_observations: int | None = None,
    online: bool | None = None,
    parent_tool: str | None = None,
    active_failure_conditions: tuple[str, ...] | list[str] = (),
    mitigated_failure_conditions: tuple[str, ...] | list[str] = (),
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document = load_envelope()
    spec = document["capabilities"].get(tool)
    base = {
        "tool": tool,
        "operation": operation,
        "requested_role": intended_role,
        "envelope_version": document["schema_version"],
        "envelope_sha256": envelope_sha256(),
        "authorizes_production": False,
    }
    if spec is None:
        return {**base, "status": "NOT_ELIGIBLE", "reason_codes": ["UNKNOWN_CAPABILITY"]}
    ctx = dict(context or {})
    reasons: list[str] = []
    if operation not in spec["allowed_operations"]:
        reasons.append("OPERATION_OUTSIDE_ENVELOPE")
    if intended_role is not None and intended_role != spec["role"]:
        reasons.append("ROLE_MISMATCH")
    if not isinstance(observations, int) or isinstance(observations, bool):
        reasons.append("OBSERVATION_COUNT_REQUIRED")
    elif observations < spec["minimum_observations"]:
        reasons.append("MINIMUM_OBSERVATIONS_NOT_MET")
    if spec["minimum_prebreak_observations"] > 0:
        if not isinstance(prebreak_observations, int):
            reasons.append("PREBREAK_CALIBRATION_COUNT_REQUIRED")
        elif prebreak_observations < spec["minimum_prebreak_observations"]:
            reasons.append("PREBREAK_CALIBRATION_SAMPLE_TOO_SHORT")
    if spec["requires_online"] is True and online is not True:
        reasons.append("ONLINE_PREFIX_MODE_REQUIRED")
    if spec["requires_online"] is False and online is True:
        reasons.append("RETROSPECTIVE_TOOL_CANNOT_RUN_ONLINE")
    if spec["requires_reset"] and ctx.get("reset_rearm_implemented") is not True:
        reasons.append("RESET_REARM_REQUIRED")
    if spec["requires_per_series_p0"]:
        if ctx.get("per_series_null_calibrated") is not True:
            reasons.append("PER_SERIES_NULL_CALIBRATION_REQUIRED")
        upper = ctx.get("development_p0_wilson_upper")
        target = float(document["common_controls"]["per_series_null_p0_target"])
        if not isinstance(upper, (int, float)) or isinstance(upper, bool) or upper > target:
            reasons.append("PER_SERIES_P0_UPPER_BOUND_EXCEEDS_TARGET")
        valid = ctx.get("valid_null_replicates")
        minimum = int(document["common_controls"]["minimum_valid_null_replicates"])
        if not isinstance(valid, int) or valid < minimum:
            reasons.append("INSUFFICIENT_VALID_NULL_REPLICATES")
    if spec["role"] == "feature_generator" and ctx.get("full_run_length_pmf_exported") is not True:
        reasons.append("FULL_RUN_LENGTH_POSTERIOR_REQUIRED")
    if tool == "R-FPOP" and ctx.get("penalty_frozen_before_holdout") is not True:
        reasons.append("R_FPOP_PENALTY_MUST_BE_FROZEN_BEFORE_HOLDOUT")
    if spec["not_standalone_detector"]:
        if operation != "calibrate_scale":
            reasons.append("CALIBRATOR_CANNOT_EMIT_DETECTOR_EVENTS")
        if ctx.get("standalone") is True or not parent_tool:
            reasons.append("CALIBRATOR_REQUIRES_PARENT_TOOL")
        elif parent_tool not in spec["allowed_parent_tools"]:
            reasons.append("PARENT_TOOL_NOT_ALLOWED")
    active = set(active_failure_conditions)
    mitigated = set(mitigated_failure_conditions)
    for condition in sorted(active.intersection(spec["known_failure_conditions"]) - mitigated):
        reasons.append(f"KNOWN_FAILURE_CONDITION_UNMITIGATED:{condition}")
    if not spec["runtime_supported"]:
        reasons.append(f"IMPLEMENTATION_NOT_READY:{spec['implementation_status']}")
    if not spec["pilot_enabled"]:
        reasons.append("PILOT_DISABLED")
    return {
        **base,
        "role": spec["role"],
        "status": "PILOT_ELIGIBLE" if not reasons else "NOT_ELIGIBLE",
        "reason_codes": reasons,
        "implementation_status": spec["implementation_status"],
        "scientific_validation_status": spec["scientific_validation_status"],
        "runtime_supported": spec["runtime_supported"],
        "pilot_enabled": spec["pilot_enabled"],
        "time_semantics": spec["time_semantics"],
        "input_contract": list(spec["input_contract"]),
        "output_contract": list(spec["output_contract"]),
        "minimum_observations": spec["minimum_observations"],
        "minimum_prebreak_observations": spec["minimum_prebreak_observations"],
        "restrictions": list(spec["restricted_uses"]),
        "known_failure_conditions": list(spec["known_failure_conditions"]),
        "validation_history": [dict(item) for item in spec["validation_history"]],
    }


def require_capability(tool: str, **request: Any) -> dict[str, Any]:
    decision = assess_capability(tool, **request)
    if decision["status"] != "PILOT_ELIGIBLE":
        raise CapabilityViolation(decision)
    return decision

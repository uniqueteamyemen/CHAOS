"""P1.4 capability operating envelope and fail-closed runtime authorization.

This module is the executable source of truth for tool roles, time semantics,
input/output contracts, restrictions, and validation provenance. It does not
claim scientific validation merely because an implementation exists.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


ENVELOPE_VERSION = "1.0.0"

_P2C_BENCHMARK_HISTORY = (
    {
        "evidence_id": "github-actions:45524159488",
        "status": "BENCHMARK_ESTABLISHED_NOT_CAPABILITY_VALIDATION",
        "scope": "509 economic series, causal replay and retrospective segmentation diagnostics",
        "validated_role": False,
        "note": "Execution and coverage passed; detector-role operating envelopes remain pending.",
    },
)

@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    role: str
    time_semantics: str
    allowed_operations: tuple[str, ...]
    output_contract: tuple[str, ...]
    minimum_observations: int
    minimum_prebreak_observations: int = 0
    requires_reset: bool = False
    requires_per_series_arl: bool = False
    requires_known_regimes: bool = False
    requires_online: bool | None = None
    not_binary: bool = False
    not_standalone_detector: bool = False
    integrates_into: tuple[str, ...] = ()
    known_failure_conditions: tuple[str, ...] = ()
    forbidden_uses: tuple[str, ...] = ()
    runtime_supported: bool = False
    implementation_status: str = "NOT_IMPLEMENTED"
    validation_history: tuple[Mapping[str, Any], ...] = _P2C_BENCHMARK_HISTORY


CAPABILITIES: dict[str, CapabilitySpec] = {
    "FOCuS": CapabilitySpec(
        name="FOCuS",
        role="online_detector",
        time_semantics="online_prefix_only",
        allowed_operations=("online_detect",),
        output_contract=("change_event", "detection_index", "estimated_change_index", "direction"),
        minimum_observations=41,
        minimum_prebreak_observations=40,
        requires_reset=True,
        requires_per_series_arl=True,
        requires_online=True,
        known_failure_conditions=(
            "high_autocorrelation_without_per_series_null_calibration",
            "variance_jump_without_scale_model",
            "heavy_tails_without_robust_loss",
            "gradual_or_temporary_shift",
            "multiple_changes_without_reset_rearm",
        ),
        forbidden_uses=(
            "single_hit_runner_without_reset_rearm",
            "global_threshold_without_per_series_arl_calibration",
            "retrospective_boundary_used_as_online_alarm",
        ),
        runtime_supported=False,
        implementation_status="BLOCKED_RESET_AND_PER_SERIES_ARL_NOT_IMPLEMENTED",
    ),
    "FOCUS_RESET_ARL_PILOT": CapabilitySpec(
        name="FOCUS_RESET_ARL_PILOT",
        role="online_detector",
        time_semantics="online_prefix_only",
        allowed_operations=("online_detect",),
        output_contract=("change_event", "detection_index", "estimated_change_index", "direction", "reset_state"),
        minimum_observations=41,
        minimum_prebreak_observations=40,
        requires_reset=True,
        requires_per_series_arl=True,
        requires_online=True,
        known_failure_conditions=(
            "high_autocorrelation_order_above_selected_model",
            "variance_jump_not_represented_in_null_model",
            "heavy_tails_outside_fitted_ar_null",
            "gradual_or_temporary_shift",
            "poorly_identified_ar_parameters",
        ),
        forbidden_uses=(
            "un-calibrated_threshold",
            "threshold_tuned_on_holdout",
            "future_suffix_access",
        ),
        runtime_supported=False,
        implementation_status="PILOT_IMPLEMENTATION_PENDING",
    ),
    "R-FPOP": CapabilitySpec(
        name="R-FPOP",
        role="offline_segmenter",
        time_semantics="retrospective_full_series",
        allowed_operations=("retrospective_segment",),
        output_contract=("breakpoint_set", "estimated_change_index", "segment_parameters"),
        minimum_observations=52,
        requires_known_regimes=False,
        requires_online=False,
        known_failure_conditions=(
            "penalty_misspecification",
            "too_many_breakpoints_under_weak_penalty",
            "short_segments_below_minimum_support",
            "retrospective_boundaries_mistaken_for_realtime_warnings",
        ),
        forbidden_uses=(
            "online_alarm_claim",
            "future_information_in_point_in_time_features",
            "breakpoint_count_selected_after_holdout_review",
        ),
        runtime_supported=True,
        implementation_status="IMPLEMENTED_RETROSPECTIVE_VALIDATION_PENDING",
    ),
    "BOCPD": CapabilitySpec(
        name="BOCPD",
        role="feature_generator",
        time_semantics="online_prefix_only",
        allowed_operations=("emit_run_length_features",),
        output_contract=(
            "posterior_run_length_distribution",
            "expected_run_length",
            "run_length_variance",
            "posterior_entropy",
            "short_run_probability",
            "change_probability",
        ),
        minimum_observations=41,
        requires_online=True,
        not_binary=True,
        known_failure_conditions=(
            "hazard_misspecification",
            "run_length_truncation",
            "prior_sensitivity",
            "serial_dependence_misspecification",
            "variance_change_confounded_with_mean_change",
        ),
        forbidden_uses=(
            "binary_detector_only_interface",
            "single_map_run_length_as_full_posterior",
            "posterior_features_from_future_suffix",
        ),
        runtime_supported=False,
        implementation_status="BLOCKED_FULL_RUN_LENGTH_PMF_NOT_EXPORTED",
    ),
    "Bartlett_LRV": CapabilitySpec(
        name="Bartlett_LRV",
        role="calibrator",
        time_semantics="calibration_slice_only",
        allowed_operations=("calibrate_scale",),
        output_contract=("long_run_variance", "long_run_scale", "bandwidth"),
        minimum_observations=8,
        not_standalone_detector=True,
        integrates_into=("FOCUS_RESET_ARL_PILOT", "A_FAST_BARTLETT_PILOT"),
        known_failure_conditions=(
            "short_calibration_window",
            "non_positive_long_run_variance",
            "bandwidth_sensitive_estimate",
            "nonstationary_calibration_slice",
        ),
        forbidden_uses=(
            "standalone_detector",
            "emit_binary_alarm",
            "retrospective_scale_leakage",
        ),
        runtime_supported=True,
        implementation_status="IMPLEMENTED_CALIBRATOR_VALIDATION_PENDING",
    ),
    "A_FAST": CapabilitySpec(
        name="A_FAST",
        role="reference_detector",
        time_semantics="online_prefix_only",
        allowed_operations=("reference_only",),
        output_contract=("frozen_reference_events",),
        minimum_observations=52,
        requires_online=True,
        known_failure_conditions=("pre_onset_alerts", "directional_or_domain_misspecification"),
        forbidden_uses=("mutate_frozen_implementation", "retune_on_pilot_holdout"),
        runtime_supported=True,
        implementation_status="FROZEN_REFERENCE",
    ),
    "A_CONSENSUS": CapabilitySpec(
        name="A_CONSENSUS",
        role="reference_detector",
        time_semantics="online_prefix_only",
        allowed_operations=("reference_only",),
        output_contract=("frozen_reference_events",),
        minimum_observations=87,
        requires_online=True,
        known_failure_conditions=("excessive_confirmation_delay", "missed_short_lived_changes"),
        forbidden_uses=("mutate_frozen_implementation", "retune_on_pilot_holdout"),
        runtime_supported=True,
        implementation_status="FROZEN_REFERENCE",
    ),
    "A_FAST_BARTLETT_PILOT": CapabilitySpec(
        name="A_FAST_BARTLETT_PILOT",
        role="online_detector",
        time_semantics="online_prefix_only",
        allowed_operations=("online_detect",),
        output_contract=("change_event", "detection_index", "direction", "bartlett_calibration"),
        minimum_observations=52,
        requires_online=True,
        known_failure_conditions=("calibration_window_misspecification", "scale_estimator_instability"),
        forbidden_uses=("mutate_A_FAST", "claim_A_FAST_baseline_was_modified"),
        runtime_supported=False,
        implementation_status="PILOT_IMPLEMENTATION_PENDING",
    ),
}


class CapabilityViolation(RuntimeError):
    """Raised when a requested operation is outside its declared capability."""

    def __init__(self, decision: Mapping[str, Any]):
        self.decision = dict(decision)
        code = ",".join(self.decision.get("reason_codes", ())) or "NOT_ELIGIBLE"
        super().__init__(f"CAPABILITY_NOT_ELIGIBLE:{self.decision.get('tool')}:{code}")


def envelope_document() -> dict[str, Any]:
    """Return the deterministic, JSON-compatible operating envelope."""
    return {
        "schema_version": ENVELOPE_VERSION,
        "capabilities": {
            name: asdict(spec)
            for name, spec in sorted(CAPABILITIES.items())
        },
        "decision_contract": {
            "eligible_status": "ELIGIBLE",
            "ineligible_status": "NOT_ELIGIBLE",
            "default": "fail_closed",
            "note": "Implementation status and runtime restrictions override caller-supplied flags.",
        },
    }


def envelope_sha256() -> str:
    raw = json.dumps(
        envelope_document(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
    """Assess one use against the envelope; return NOT_ELIGIBLE rather than guessing."""
    spec = CAPABILITIES.get(tool)
    base = {
        "tool": tool,
        "operation": operation,
        "requested_role": intended_role,
        "envelope_version": ENVELOPE_VERSION,
        "envelope_sha256": envelope_sha256(),
    }
    if spec is None:
        return {**base, "status": "NOT_ELIGIBLE", "reason_codes": ["UNKNOWN_CAPABILITY"]}

    ctx = dict(context or {})
    reasons: list[str] = []
    if operation not in spec.allowed_operations:
        reasons.append("OPERATION_OUTSIDE_ENVELOPE")
    if intended_role is not None and intended_role != spec.role:
        reasons.append("ROLE_MISMATCH")
    if observations is not None and observations < spec.minimum_observations:
        reasons.append("MINIMUM_OBSERVATIONS_NOT_MET")
    if spec.minimum_observations > 0 and observations is None:
        reasons.append("OBSERVATION_COUNT_REQUIRED")
    if spec.minimum_prebreak_observations > 0:
        if prebreak_observations is None:
            reasons.append("PREBREAK_CALIBRATION_COUNT_REQUIRED")
        elif prebreak_observations < spec.minimum_prebreak_observations:
            reasons.append("PREBREAK_CALIBRATION_SAMPLE_TOO_SHORT")
    if spec.requires_online is True and online is not True:
        reasons.append("ONLINE_PREFIX_MODE_REQUIRED")
    if spec.requires_online is False and online is True:
        reasons.append("RETROSPECTIVE_TOOL_CANNOT_RUN_ONLINE")
    if spec.requires_reset and ctx.get("reset_rearm_implemented") is not True:
        reasons.append("RESET_REARM_REQUIRED")
    if spec.requires_per_series_arl and ctx.get("per_series_arl_calibrated") is not True:
        reasons.append("PER_SERIES_ARL_CALIBRATION_REQUIRED")
    if spec.requires_known_regimes and ctx.get("known_regimes_count") is None:
        reasons.append("KNOWN_REGIME_COUNT_REQUIRED")
    if spec.not_standalone_detector:
        if operation != "calibrate_scale":
            reasons.append("CALIBRATOR_CANNOT_EMIT_DETECTOR_EVENTS")
        if ctx.get("standalone") is True or not parent_tool:
            reasons.append("CALIBRATOR_REQUIRES_PARENT_TOOL")
        elif parent_tool not in spec.integrates_into:
            reasons.append("PARENT_TOOL_NOT_ALLOWED")
    active = set(active_failure_conditions)
    mitigated = set(mitigated_failure_conditions)
    unmitigated = sorted(active.intersection(spec.known_failure_conditions) - mitigated)
    if unmitigated:
        reasons.extend(f"KNOWN_FAILURE_CONDITION_UNMITIGATED:{item}" for item in unmitigated)
    if not spec.runtime_supported:
        reasons.append(f"IMPLEMENTATION_NOT_READY:{spec.implementation_status}")

    return {
        **base,
        "role": spec.role,
        "status": "ELIGIBLE" if not reasons else "NOT_ELIGIBLE",
        "reason_codes": reasons,
        "implementation_status": spec.implementation_status,
        "runtime_supported": spec.runtime_supported,
        "time_semantics": spec.time_semantics,
        "requires_reset": spec.requires_reset,
        "requires_per_series_arl": spec.requires_per_series_arl,
        "requires_known_regimes": spec.requires_known_regimes,
        "not_binary": spec.not_binary,
        "not_standalone_detector": spec.not_standalone_detector,
        "integrates_into": list(spec.integrates_into),
        "known_failure_conditions": list(spec.known_failure_conditions),
        "validation_history": [dict(item) for item in spec.validation_history],
    }


def require_capability(tool: str, **request: Any) -> dict[str, Any]:
    """Fail-closed guard for a runtime entrypoint."""
    decision = assess_capability(tool, **request)
    if decision["status"] != "ELIGIBLE":
        raise CapabilityViolation(decision)
    return decision

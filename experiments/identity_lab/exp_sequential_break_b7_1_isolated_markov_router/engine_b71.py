"""B-v7 robust innovation sign-CUSUM structural detector over the corrected B-v6.1 baseline."""
from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_THRESHOLD = 85.0

class InnovationSignCusumEngineB7:
    """B-v6 engine with raw rho and a fixed three-point PENDING gate.

    Only the correlation estimator (Pearson/Spearman) and break threshold
    vary across B-v6 configurations. Structural scoring and lifecycle logic
    are retained from the B-v4/B-v5 lineage.
    """

    def __init__(
        self,
        quiet_end: int = 40,
        window_size: int = 12,
        anomaly_z_thresh: float = 3.8,
        winsor_cap: float = 1.8,
        cusum_threshold: float = 12.5,
        resolution_horizon: int = 14,
        return_to_baseline_z: float = 1.5,
        persistence_z_thresh: float = 1.45,
        correlation_method: str = "pearson",
        structural_rho_bias_correction: bool = True,
        innovation_drain: bool = False,
        persistence_floor: bool = False,
        heuristic_scale_guard: bool = False,
    ) -> None:
        if quiet_end < 4:
            raise ValueError("quiet_end_must_be_at_least_4")
        if window_size < 4:
            raise ValueError("window_size_must_be_at_least_4")
        if anomaly_z_thresh <= 0:
            raise ValueError("anomaly_z_thresh_must_be_positive")
        if winsor_cap <= 0:
            raise ValueError("winsor_cap_must_be_positive")
        if not np.isfinite(cusum_threshold) or cusum_threshold <= 0:
            raise ValueError("cusum_threshold_must_be_positive")
        if resolution_horizon < 1:
            raise ValueError("resolution_horizon_must_be_at_least_1")
        if return_to_baseline_z <= 0:
            raise ValueError("return_to_baseline_z_must_be_positive")
        if persistence_z_thresh <= 0:
            raise ValueError("persistence_z_thresh_must_be_positive")
        if correlation_method not in {"pearson", "spearman"}:
            raise ValueError("correlation_method_must_be_pearson_or_spearman")
        if not isinstance(structural_rho_bias_correction, bool):
            raise ValueError("structural_rho_bias_correction_must_be_boolean")

        self.quiet_end = int(quiet_end)
        self.window_size = int(window_size)
        self.anomaly_z_thresh = float(anomaly_z_thresh)
        self.winsor_cap = float(winsor_cap)
        self.cusum_threshold = float(cusum_threshold)
        self.cusum_alt_sign_probability = 0.65
        self.resolution_horizon = int(resolution_horizon)
        self.rho_bias_correction = False
        self.correlation_method = correlation_method
        self.structural_rho_bias_correction = structural_rho_bias_correction
        self.return_to_baseline_z = float(return_to_baseline_z)
        self.persistence_z_thresh = float(persistence_z_thresh)
        for name, flag in (
            ("innovation_drain", innovation_drain),
            ("persistence_floor", persistence_floor),
            ("heuristic_scale_guard", heuristic_scale_guard),
        ):
            if not isinstance(flag, bool):
                raise ValueError(f"{name}_must_be_boolean")
        self.innovation_drain = innovation_drain
        self.persistence_floor = persistence_floor
        self.heuristic_scale_guard = heuristic_scale_guard

    def _pending_gate_decision(
        self, recent_z: np.ndarray, rho: float
    ) -> tuple[bool, bool, list[float]]:
        """Return (raw_three_point_gate, drain_rejected, normalized_innovations)."""
        if recent_z.size != 3:
            return False, False, []
        if self.innovation_drain:
            # D=1: only the initiating point must cross 3.8. The following
            # two points are judged by normalized innovations, not raw z.
            first_point_triggered = bool(
                abs(float(recent_z[0])) > self.anomaly_z_thresh
            )
            if not first_point_triggered:
                return False, False, []
            innovation_scale = float(np.sqrt(max(1.0 - rho * rho, 0.15)))
            innovations = (
                recent_z[1:] - rho * recent_z[:-1]
            ) / innovation_scale
            same_direction = bool(
                np.all(np.sign(innovations) == np.sign(recent_z[0]))
            )
            accepted = (
                bool(np.all(np.abs(innovations) > 2.8))
                and same_direction
            )
            return True, not accepted, [float(x) for x in innovations]

        # D=0: preserve the frozen B-v6a three-raw-point rule exactly.
        raw_gate = (
            bool(np.all(np.abs(recent_z) > self.anomaly_z_thresh))
            and bool(np.all(np.sign(recent_z) == np.sign(recent_z[-1])))
        )
        return raw_gate, False, []

    def _passes_persistence_floor(self, dominant_persistence: float) -> bool:
        return not self.persistence_floor or dominant_persistence >= 0.75

    @staticmethod
    def _correct_short_sample_ar1_rho(rho_raw: float, sample_count: int) -> float:
        """Approximate first-order finite-sample correction for AR(1) sample lag-1 rho."""
        if sample_count <= 3:
            return float(np.clip(rho_raw, 0.0, 0.88))
        corrected = (float(rho_raw) + 1.0 / sample_count) / (1.0 - 3.0 / sample_count)
        return float(np.clip(corrected, 0.0, 0.88))

    @staticmethod
    def _markov_sign_cusum_update(
        positive: float, negative: float, previous_sign: int,
        innovation_sign: int, latched_direction: int,
        transition_positive: dict[int, float], q: float = 0.65,
    ) -> tuple[float, float]:
        """Conditional Markov sign log-likelihood increments with Laplace-smoothed H0."""
        if innovation_sign == 0:
            return float(positive), float(negative)
        p0_pos = float(np.clip(transition_positive[int(previous_sign)], 1e-9, 1.0-1e-9))
        odds = q / (1.0-q)
        p1_positive = (p0_pos * odds) / (1.0-p0_pos+p0_pos*odds)
        inverse_odds = 1.0 / odds
        p1_negative = (p0_pos * inverse_odds) / (1.0-p0_pos+p0_pos*inverse_odds)
        pos_increment = float(np.log(p1_positive/p0_pos)) if innovation_sign > 0 else float(np.log((1.0-p1_positive)/(1.0-p0_pos)))
        neg_increment = float(np.log((1.0-p1_negative)/(1.0-p0_pos))) if innovation_sign < 0 else float(np.log(p1_negative/p0_pos))
        if latched_direction == 0:
            positive = max(0.0, positive + pos_increment)
            negative = max(0.0, negative + neg_increment)
        elif latched_direction > 0:
            positive = 0.0
            negative = max(0.0, negative + neg_increment)
        else:
            negative = 0.0
            positive = max(0.0, positive + pos_increment)
        return float(positive), float(negative)

    def _apply_heuristic_scale_guard(self, context_scale: float, rho: float) -> float:
        if not self.heuristic_scale_guard:
            return float(context_scale)
        return float(context_scale * (1.0 + 0.25 * rho))

    def _estimate_onset(
        self, series: np.ndarray, detection_t: int, lookback: int = 22
    ) -> int:
        start = max(self.quiet_end, detection_t - int(lookback))
        segment = series[start : detection_t + 1]
        if len(segment) < 6:
            return int(start)

        best_tau = start
        best_contrast = -1.0
        for split in range(2, len(segment) - 2):
            contrast = abs(
                float(np.median(segment[split:]) - np.median(segment[:split]))
            )
            if contrast > best_contrast:
                best_contrast = contrast
                best_tau = start + split
        return int(best_tau)

    def analyze(self, series: np.ndarray | list[float]) -> dict[str, Any]:
        values = np.asarray(series, dtype=float)
        if values.ndim != 1:
            raise ValueError("series_must_be_one_dimensional")
        if not np.all(np.isfinite(values)):
            raise ValueError("series_contains_nonfinite_values")
        n = int(values.size)
        if n < self.quiet_end + self.window_size:
            raise ValueError("series_too_short_for_quiet_and_window")

        quiet = values[: self.quiet_end]
        baseline_center = float(np.median(quiet))

        quiet_diffs = np.diff(quiet)
        base_diff_mad = float(
            np.median(np.abs(quiet_diffs)) * 1.4826 / np.sqrt(2.0)
        )
        base_diff_mad = max(base_diff_mad, 1e-6)

        q_spread = float(
            np.median(np.abs(quiet - baseline_center)) * 1.4826
        )
        q_spread = max(q_spread, 1e-6)
        # Fixed robust scale from the original quiet segment for reversion tests.
        baseline_level_scale = q_spread
        q_norm = (quiet - baseline_center) / q_spread

        # Estimate lag-1 dependence in the quiet segment without any inflation.
        if self.correlation_method == "pearson":
            left = q_norm[:-1]
            right = q_norm[1:]
            has_variation = (
                left.size > 2
                and np.std(left) > 1e-12
                and np.std(right) > 1e-12
            )
            rho_raw = (
                float(np.corrcoef(left, right)[0, 1]) if has_variation else 0.0
            )
        else:
            # Follow the experiment's specified double-argsort ordinal ranks.
            # np.corrcoef returns a 2x2 matrix; [0, 1] is the scalar lag-1 rho.
            left_values = quiet[:-1]
            right_values = quiet[1:]
            r0 = np.argsort(np.argsort(left_values)).astype(float)
            r1 = np.argsort(np.argsort(right_values)).astype(float)
            has_variation = (
                r0.size > 2
                and np.std(left_values) > 1e-12
                and np.std(right_values) > 1e-12
                and np.std(r0) > 1e-12
                and np.std(r1) > 1e-12
            )
            rho_raw = (
                float(np.corrcoef(r0, r1)[0, 1]) if has_variation else 0.0
            )
        if not np.isfinite(rho_raw):
            rho_raw = 0.0
        rho_raw = float(rho_raw)
        rho_adjusted = rho_raw
        rho = float(np.clip(rho_raw, 0.0, 0.88))

        # Use the exact same AR coefficient for quiet-period null calibration
        # and live innovation signs; otherwise P(s_t|s_{t-1}) is miscalibrated.
        rho_cusum_raw = (
            (rho_raw + (1.0 / len(quiet)))
            / (1.0 - (3.0 / len(quiet)))
        )
        rho_cusum = (
            self._correct_short_sample_ar1_rho(rho_raw, len(quiet))
            if self.structural_rho_bias_correction
            else float(np.clip(rho_raw, 0.0, 0.88))
        )

        # Quiet-period Markov null estimated from the same AR innovation signs
        # used online. Laplace alpha=1 is applied independently to each row.
        quiet_residuals = (
            quiet[1:] - baseline_center
            - rho_cusum * (quiet[:-1] - baseline_center)
        )
        quiet_signs = np.sign(quiet_residuals).astype(int)
        transition_counts = {-1: {-1: 1.0, 1: 1.0}, 1: {-1: 1.0, 1: 1.0}}
        for prev_s, next_s in zip(quiet_signs[:-1], quiet_signs[1:]):
            if prev_s != 0 and next_s != 0:
                transition_counts[int(prev_s)][int(next_s)] += 1.0
        transition_positive = {
            p: transition_counts[p][1] /
            (transition_counts[p][-1] + transition_counts[p][1])
            for p in (-1, 1)
        }
        nonzero_quiet_signs = quiet_signs[quiet_signs != 0]
        previous_innovation_sign = (
            int(nonzero_quiet_signs[-1]) if nonzero_quiet_signs.size else 1
        )

        ar_factor = 1.0 / np.sqrt(max(1.0 - rho, 0.12))
        f_lrv_corrected = np.sqrt(1.0 + rho) / max(1.0 - rho, 0.12)

        structural_breaks: list[dict[str, Any]] = []
        transient_anomalies: list[dict[str, Any]] = []
        unresolved_alerts: list[dict[str, Any]] = []
        pending_spikes: list[dict[str, Any]] = []
        # Shadow lifecycle for the D1_P1_G0 PENDING gate. Markov structural
        # resolutions must never change the reference channel's open eligibility.
        pending_reference_spikes: list[dict[str, Any]] = []
        pending_opened = 0
        pending_reference_opened = 0
        pending_gate_opportunities = 0
        innovation_gate_rejections = 0
        structural_threshold_candidates = 0
        persistence_floor_rejections = 0
        latched_direction = 0
        # Independent D-channel latch mirrors B-v6.1's 85-point structural gate.
        pending_latched_direction = 0
        cusum_positive = 0.0
        cusum_negative = 0.0
        cusum_threshold_crossings = 0
        cusum_updates = 0
        cusum_peak = 0.0
        cusum_directional_resets = 0

        # Both one-step structural innovations and the independent PENDING
        # reference channel begin immediately after quiet calibration.
        start_t = self.quiet_end
        for t in range(start_t, n):
            win_start = t - self.window_size + 1
            window = values[win_start : t + 1]

            hist_start = max(1, win_start - 10)
            local_diffs = np.abs(np.diff(values[hist_start : t + 1]))
            local_diff_mad = (
                float(np.median(local_diffs) * 1.4826 / np.sqrt(2.0))
                if local_diffs.size
                else 0.0
            )
            active_diff_scale = max(base_diff_mad, local_diff_mad, 1e-6)

            marginal_scale = active_diff_scale * ar_factor
            context_scale = self._apply_heuristic_scale_guard(
                active_diff_scale * f_lrv_corrected, rho
            )

            z_point_raw = (window - baseline_center) / marginal_scale
            z_context_raw = (window - baseline_center) / context_scale

            # Stage 1: record a spike as pending; do not prematurely call it transient.
            z_current = float(z_point_raw[-1])
            recent_pending = any(
                0 <= t - int(p["time"]) <= 2 for p in pending_reference_spikes
            )
            # Stage 1 is the transient-only channel. The structural channel below
            # remains independent and never waits for PENDING.
            recent_z = z_point_raw[-3:]
            raw_gate, drain_rejected, normalized_innovations = (
                self._pending_gate_decision(recent_z, rho)
            )
            # Match the D1_P1_G0 PENDING scan start (quiet_end), while
            # keeping its reference latch independent of the Markov structural latch.
            if (
                raw_gate
                and pending_latched_direction == 0
                and not recent_pending
            ):
                pending_gate_opportunities += 1
                if drain_rejected:
                    innovation_gate_rejections += 1
                else:
                    pending_event = {
                        "time": int(t),
                        "value": round(float(values[t]), 3),
                        "deviation_sigma": round(z_current, 2),
                        "direction": 1 if recent_z[0] > 0 else -1,
                    }
                    pending_spikes.append(dict(pending_event))
                    pending_reference_spikes.append(dict(pending_event))
                    pending_opened += 1
                    pending_reference_opened += 1

            # Stage 2: use the unchanged B-v3 structural-break score.
            z_point = np.clip(z_point_raw, -self.winsor_cap, self.winsor_cap)
            z_context = np.clip(z_context_raw, -self.winsor_cap, self.winsor_cap)

            full_pos = float(np.mean(z_point > self.persistence_z_thresh))
            full_neg = float(np.mean(z_point < -self.persistence_z_thresh))
            dominant_persistence = max(full_pos, full_neg)
            direction = 1 if full_pos >= full_neg else -1

            window_shift_z = float(np.median(z_context))
            separation_score = min(abs(window_shift_z) / 1.45, 1.0)
            break_pct = round(
                float(
                    (0.45 * dominant_persistence + 0.55 * separation_score)
                    * 100.0
                ),
                1,
            )

            # Keep the transient-channel latch exactly aligned with Fast_Ref,
            # independent of the Markov structural detector's own latch.
            pending_reference_candidate = (
                break_pct >= 85.0 and pending_latched_direction != direction
            )
            if pending_reference_candidate:
                # Resolve the shadow PENDING ledger exactly as Fast_Ref does;
                # do not use Markov's independent structural confirmation here.
                reference_still_pending: list[dict[str, Any]] = []
                for pending in pending_reference_spikes:
                    age = t - int(pending["time"])
                    if not (
                        pending["direction"] == direction
                        and 0 <= age <= self.resolution_horizon + 4
                    ):
                        reference_still_pending.append(pending)
                pending_reference_spikes = reference_still_pending
                pending_latched_direction = direction
            elif abs(window_shift_z) < 0.40:
                pending_latched_direction = 0

            # B-v7 structural evidence: one-step AR innovation signs.
            # The B-v6.1 raw rho remains untouched for the D/PENDING channel
            # and context scaling. A finite-sample corrected rho is used only
            # to whiten the structural evidence stream.
            structural_innovation = float(
                values[t]
                - baseline_center
                - rho_cusum * (values[t - 1] - baseline_center)
            )
            innovation_sign = (
                1 if structural_innovation > 0.0
                else (-1 if structural_innovation < 0.0 else 0)
            )
            cusum_updates += 1

            # A bounded conditional log-likelihood score prevents a single
            # innovation from dominating the structural decision. Each side is a
            # reflected Markov sign-CUSUM using the quiet transition null and its
            # directional odds-tilted alternative. Only opposite-direction
            # evidence accumulates while a direction is latched.
            previous_evidence_peak = max(cusum_positive, cusum_negative)
            cusum_positive, cusum_negative = self._markov_sign_cusum_update(
                cusum_positive, cusum_negative, previous_innovation_sign,
                innovation_sign, latched_direction, transition_positive,
                self.cusum_alt_sign_probability,
            )
            if innovation_sign != 0:
                previous_innovation_sign = innovation_sign

            evidence_peak = max(cusum_positive, cusum_negative)
            cusum_peak = max(cusum_peak, evidence_peak)
            cusum_candidate = evidence_peak >= self.cusum_threshold
            if cusum_candidate and previous_evidence_peak < self.cusum_threshold:
                cusum_threshold_crossings += 1
            cusum_direction = (
                1 if cusum_positive >= cusum_negative else -1
            )
            structural_threshold_candidate = bool(
                cusum_candidate and latched_direction != cusum_direction
            )
            if structural_threshold_candidate:
                structural_threshold_candidates += 1

            if structural_threshold_candidate:
                estimated_onset = self._estimate_onset(values, t)
                resolved_pending: list[dict[str, Any]] = []
                still_pending: list[dict[str, Any]] = []
                for pending in pending_spikes:
                    age = t - int(pending["time"])
                    if (
                        pending["direction"] == cusum_direction
                        and 0 <= age <= self.resolution_horizon + 4
                    ):
                        resolved_pending.append(
                            {
                                **pending,
                                "resolved_at": int(t),
                                "status": "RESOLVED_STRUCTURAL",
                            }
                        )
                    else:
                        still_pending.append(pending)
                pending_spikes = still_pending

                structural_breaks.append(
                    {
                        "detection_time": int(t),
                        "estimated_onset": int(estimated_onset),
                        "direction": int(cusum_direction),
                        "break_percentage": float(break_pct),
                        "structural_evidence": float(evidence_peak),
                        "evidence_kind": "innovation_sign_cusum",
                        "resolved_pending_alerts": resolved_pending,
                    }
                )
                latched_direction = cusum_direction
                cusum_positive = 0.0
                cusum_negative = 0.0
            elif abs(window_shift_z) < 0.40 and latched_direction != 0:
                # The baseline-return condition releases an existing latch.
                # Do not erase unlatched evidence merely because a change has
                # not yet occupied half of the rolling window; that would make
                # the sequential detector wait for the old median-window gate.
                cusum_directional_resets += 1
                latched_direction = 0
                cusum_positive = 0.0
                cusum_negative = 0.0

            # Stage 3: a transient requires an observed return to the fixed
            # quiet-period band during the configured horizon. Expiry alone
            # is not evidence of reversion.
            still_pending = []
            for pending in pending_spikes:
                age = t - int(pending["time"])
                return_z = abs(
                    (float(values[t]) - baseline_center) / baseline_level_scale
                )
                returned_to_baseline = (
                    0 < age <= self.resolution_horizon
                    and return_z < self.return_to_baseline_z
                )
                if returned_to_baseline:
                    transient_anomalies.append(
                        {
                            **pending,
                            "resolved_at": int(t),
                            "status": "RESOLVED_TRANSIENT",
                            "resolution_age": int(age),
                            "return_z": round(float(return_z), 4),
                        }
                    )
                else:
                    # Keep it eligible for structural linkage; if no structural
                    # event resolves it, terminal accounting marks it unresolved.
                    still_pending.append(pending)
            pending_spikes = still_pending

            # Mirror Fast_Ref's transient-return removal on the gate-only shadow
            # ledger. This preserves the exact PENDING re-open timing.
            reference_still_pending = []
            for pending in pending_reference_spikes:
                age = t - int(pending["time"])
                reference_return_z = abs(
                    (float(values[t]) - baseline_center) / baseline_level_scale
                )
                returned_to_baseline = (
                    0 < age <= self.resolution_horizon
                    and reference_return_z < self.return_to_baseline_z
                )
                if not returned_to_baseline:
                    reference_still_pending.append(pending)
            pending_reference_spikes = reference_still_pending

        # Stage 4: preserve pending events when the series ends before resolution.
        for pending in pending_spikes:
            unresolved_alerts.append(
                {
                    **pending,
                    "status": "UNRESOLVED_AT_END",
                }
            )

        resolved_structural_count = sum(
            len(item["resolved_pending_alerts"]) for item in structural_breaks
        )
        resolved_transient_count = len(transient_anomalies)
        unresolved_count = len(unresolved_alerts)
        accounted_for = (
            resolved_structural_count + resolved_transient_count + unresolved_count
        )
        # Audit invariant: every opened PENDING alert has exactly one terminal state.
        if pending_opened != accounted_for:
            raise AssertionError(
                "pending_lifecycle_accounting_mismatch:"
                f"opened={pending_opened}, terminal={accounted_for}"
            )

        return {
            "structural_breaks": structural_breaks,
            "transient_anomalies": transient_anomalies,
            "unresolved_alerts": unresolved_alerts,
            "pending_lifecycle": {
                "opened_count": pending_opened,
                "resolved_structural_count": resolved_structural_count,
                "resolved_transient_count": resolved_transient_count,
                "unresolved_count": unresolved_count,
                "accounting_complete": pending_opened == accounted_for,
            },
            "diagnostics": {
                "rho_estimate": round(rho, 6),
                "rho_raw": round(rho_raw, 6),
                "rho_adjusted": round(rho_adjusted, 6),
                "rho_used": round(rho, 6),
                "rho_bias_correction_enabled": self.rho_bias_correction,
                "rho_method": self.correlation_method,
                "pending_gate_points": 3,
                "baseline_center": round(baseline_center, 6),
                "baseline_level_scale": round(baseline_level_scale, 6),
                "base_diff_scale": round(base_diff_mad, 6),
                "innovation_drain_enabled": self.innovation_drain,
                "persistence_floor_enabled": self.persistence_floor,
                "heuristic_scale_guard_enabled": self.heuristic_scale_guard,
                "heuristic_scale_guard_factor": round(
                    (1.0 + 0.25 * rho) if self.heuristic_scale_guard else 1.0, 6
                ),
                "pending_gate_opportunities": pending_gate_opportunities,
                "pending_reference_opened_count": pending_reference_opened,
                "pending_reference_gate_independent": True,
                "innovation_gate_rejections": innovation_gate_rejections,
                "structural_threshold_candidates": structural_threshold_candidates,
                "persistence_floor_rejections": persistence_floor_rejections,
                "cusum_threshold": self.cusum_threshold,
                "cusum_alt_sign_probability": self.cusum_alt_sign_probability,
                "markov_null_transition_positive": transition_positive,
                "markov_laplace_alpha": 1.0,
                "pending_gate_latch_isolated_from_structural": True,
                "pending_reference_latched_direction": pending_latched_direction,
                "cusum_likelihood_model": "conditional Markov null P(s_t|s_t-1) with Laplace alpha=1; directional H1 exponential-odds tilt",
                "cusum_threshold_crossings": cusum_threshold_crossings,
                "cusum_updates": cusum_updates,
                "cusum_peak": round(cusum_peak, 6),
                "cusum_positive_final": round(cusum_positive, 6),
                "cusum_negative_final": round(cusum_negative, 6),
                "cusum_directional_resets": cusum_directional_resets,
                "rho_cusum_used": round(rho_cusum, 6),
                "rho_cusum_corrected_candidate_unclipped": round(rho_cusum_raw, 6),
                "rho_cusum_bias_correction_enabled": self.structural_rho_bias_correction,
                "structural_evidence_kind": "innovation_sign_cusum",
            },
        }



"""B-v6 paired-ablation engine: uninflated Pearson or Spearman lag-1 rho."""
from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_THRESHOLD = 85.0

class PearsonSpearmanFixedGateEngineB6:
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
        break_percent_thresh: float = DEFAULT_THRESHOLD,
        resolution_horizon: int = 14,
        return_to_baseline_z: float = 1.5,
        persistence_z_thresh: float = 1.45,
        correlation_method: str = "pearson",
    ) -> None:
        if quiet_end < 4:
            raise ValueError("quiet_end_must_be_at_least_4")
        if window_size < 4:
            raise ValueError("window_size_must_be_at_least_4")
        if anomaly_z_thresh <= 0:
            raise ValueError("anomaly_z_thresh_must_be_positive")
        if winsor_cap <= 0:
            raise ValueError("winsor_cap_must_be_positive")
        if not 0 <= break_percent_thresh <= 100:
            raise ValueError("break_percent_thresh_out_of_range")
        if resolution_horizon < 1:
            raise ValueError("resolution_horizon_must_be_at_least_1")
        if return_to_baseline_z <= 0:
            raise ValueError("return_to_baseline_z_must_be_positive")
        if persistence_z_thresh <= 0:
            raise ValueError("persistence_z_thresh_must_be_positive")
        if correlation_method not in {"pearson", "spearman"}:
            raise ValueError("correlation_method_must_be_pearson_or_spearman")

        self.quiet_end = int(quiet_end)
        self.window_size = int(window_size)
        self.anomaly_z_thresh = float(anomaly_z_thresh)
        self.winsor_cap = float(winsor_cap)
        self.break_percent_thresh = float(break_percent_thresh)
        self.resolution_horizon = int(resolution_horizon)
        self.rho_bias_correction = False
        self.correlation_method = correlation_method
        self.return_to_baseline_z = float(return_to_baseline_z)
        self.persistence_z_thresh = float(persistence_z_thresh)

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

        ar_factor = 1.0 / np.sqrt(max(1.0 - rho, 0.12))
        f_lrv_corrected = np.sqrt(1.0 + rho) / max(1.0 - rho, 0.12)

        structural_breaks: list[dict[str, Any]] = []
        transient_anomalies: list[dict[str, Any]] = []
        unresolved_alerts: list[dict[str, Any]] = []
        pending_spikes: list[dict[str, Any]] = []
        pending_opened = 0
        latched_direction = 0

        start_t = self.quiet_end + self.window_size - 1
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
            context_scale = active_diff_scale * f_lrv_corrected

            z_point_raw = (window - baseline_center) / marginal_scale
            z_context_raw = (window - baseline_center) / context_scale

            # Stage 1: record a spike as pending; do not prematurely call it transient.
            z_current = float(z_point_raw[-1])
            recent_pending = any(
                0 <= t - int(p["time"]) <= 2 for p in pending_spikes
            )
            # B-v6 fixes the PENDING gate at three adjacent same-sign points.
            recent_z = z_point_raw[-3:]
            three_point_gate_passed = (
                bool(np.all(np.abs(recent_z) > self.anomaly_z_thresh))
                and bool(np.all(np.sign(recent_z) == np.sign(recent_z[-1])))
            )
            if (
                three_point_gate_passed
                and latched_direction == 0
                and not recent_pending
            ):
                pending_spikes.append(
                    {
                        "time": int(t),
                        "value": round(float(values[t]), 3),
                        "deviation_sigma": round(z_current, 2),
                        "direction": 1 if z_current > 0 else -1,
                    }
                )
                pending_opened += 1

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

            if (
                break_pct >= self.break_percent_thresh
                and latched_direction != direction
            ):
                estimated_onset = self._estimate_onset(values, t)
                resolved_pending: list[dict[str, Any]] = []
                still_pending: list[dict[str, Any]] = []
                for pending in pending_spikes:
                    age = t - int(pending["time"])
                    if (
                        pending["direction"] == direction
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
                        "direction": int(direction),
                        "break_percentage": float(break_pct),
                        # Explicitly retain the pending alerts absorbed by this break.
                        "resolved_pending_alerts": resolved_pending,
                    }
                )
                latched_direction = direction
            elif abs(window_shift_z) < 0.40:
                latched_direction = 0

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
            },
        }



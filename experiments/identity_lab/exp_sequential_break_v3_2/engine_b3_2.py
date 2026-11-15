"""SequentialBreakEngine B-v3.2 Calibrated.

Independent candidate derived from B-v3.1 Audit-Complete.
The optional rho adjustment is an experimental small-sample heuristic,
not a validated Kendall estimator correction.
"""
from __future__ import annotations

from typing import Any

import numpy as np


class CalibratedSequentialBreakEngineB32:
    def __init__(
        self,
        quiet_end: int = 40,
        window_size: int = 12,
        anomaly_z_thresh: float = 4.5,
        winsor_cap: float = 2.5,
        break_percent_thresh: float = 85.0,
        resolution_horizon: int = 14,
        rho_bias_correction: bool = True,
        return_to_baseline_z: float = 1.5,
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

        self.quiet_end = int(quiet_end)
        self.window_size = int(window_size)
        self.anomaly_z_thresh = float(anomaly_z_thresh)
        self.winsor_cap = float(winsor_cap)
        self.break_percent_thresh = float(break_percent_thresh)
        self.resolution_horizon = int(resolution_horizon)
        self.rho_bias_correction = bool(rho_bias_correction)
        self.return_to_baseline_z = float(return_to_baseline_z)

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

    def _estimate_rho(self, quiet: np.ndarray) -> tuple[float, float, float]:
        center = float(np.median(quiet))
        spread = max(
            float(np.median(np.abs(quiet - center)) * 1.4826),
            1e-6,
        )
        normalized = (quiet - center) / spread

        if (
            normalized.size > 2
            and np.std(normalized[:-1]) > 1e-12
            and np.std(normalized[1:]) > 1e-12
        ):
            rho_raw = float(
                np.corrcoef(normalized[:-1], normalized[1:])[0, 1]
            )
        else:
            rho_raw = 0.0

        if not np.isfinite(rho_raw):
            rho_raw = 0.0
        rho_raw = float(np.clip(rho_raw, 0.0, 0.88))

        rho_adjusted = min(
            0.90,
            rho_raw + (1.0 + 3.0 * rho_raw) / float(self.quiet_end),
        )
        rho_used = rho_adjusted if self.rho_bias_correction else rho_raw
        return rho_raw, float(rho_adjusted), float(rho_used)

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
        base_diff_mad = max(
            float(np.median(np.abs(quiet_diffs)) * 1.4826 / np.sqrt(2.0)),
            1e-6,
        )

        rho_raw, rho_adjusted, rho_used = self._estimate_rho(quiet)
        ar_factor = 1.0 / np.sqrt(max(1.0 - rho_used, 0.12))
        f_lrv_corrected = (
            np.sqrt(1.0 + rho_used) / max(1.0 - rho_used, 0.12)
        )

        # Reversion is assessed against the fixed quiet-period scale, not the
        # adaptive local-difference scale. Otherwise a volatility burst can
        # inflate the denominator and masquerade as a return to baseline.
        baseline_context_scale = max(
            base_diff_mad * f_lrv_corrected, 1e-6
        )

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
                if local_diffs.size else 0.0
            )
            active_diff_scale = max(base_diff_mad, local_diff_mad, 1e-6)

            marginal_scale = active_diff_scale * ar_factor
            context_scale = active_diff_scale * f_lrv_corrected
            z_point_raw = (window - baseline_center) / marginal_scale
            z_context_raw = (window - baseline_center) / context_scale

            # Pending event is opened on a large one-point deviation.
            z_current = float(z_point_raw[-1])
            recent_pending = any(
                0 <= t - int(p["time"]) <= 2
                for p in pending_spikes
            )
            if (
                abs(z_current) > self.anomaly_z_thresh
                and latched_direction == 0
                and not recent_pending
            ):
                pending_spikes.append(
                    {
                        "time": int(t),
                        "value": round(float(values[t]), 6),
                        "deviation_sigma": round(z_current, 3),
                        "direction": 1 if z_current > 0 else -1,
                        "status": "PENDING",
                    }
                )
                pending_opened += 1

            # Structural score is unchanged from the B-v3.1 design.
            z_point = np.clip(z_point_raw, -self.winsor_cap, self.winsor_cap)
            z_context = np.clip(
                z_context_raw, -self.winsor_cap, self.winsor_cap
            )
            full_pos = float(np.mean(z_point > 1.30))
            full_neg = float(np.mean(z_point < -1.30))
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
                    onset_linked = (
                        int(pending["time"]) >= estimated_onset - 3
                        and int(pending["time"]) <= t
                    )
                    within_horizon = 0 <= age <= self.resolution_horizon
                    if (
                        int(pending["direction"]) == direction
                        and (within_horizon or onset_linked)
                    ):
                        resolved_pending.append(
                            {
                                **pending,
                                "resolved_at": int(t),
                                "status": "RESOLVED_STRUCTURAL",
                                "resolution_age": int(age),
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
                        "resolved_pending_alerts": resolved_pending,
                    }
                )
                latched_direction = direction
            elif abs(window_shift_z) < 0.40:
                latched_direction = 0

            # Only a measured return to the original quiet band can resolve
            # an alert as transient. Expiry by itself never does so.
            current_baseline_z = (
                float(values[t]) - baseline_center
            ) / baseline_context_scale

            still_pending = []
            for pending in pending_spikes:
                age = t - int(pending["time"])
                returned_to_baseline = (
                    0 < age <= self.resolution_horizon
                    and abs(current_baseline_z) < self.return_to_baseline_z
                )
                if returned_to_baseline:
                    transient_anomalies.append(
                        {
                            **pending,
                            "resolved_at": int(t),
                            "status": "RESOLVED_TRANSIENT",
                            "resolution_age": int(age),
                            "return_z": round(abs(current_baseline_z), 4),
                        }
                    )
                else:
                    still_pending.append(pending)
            pending_spikes = still_pending

        for pending in pending_spikes:
            age_at_end = (n - 1) - int(pending["time"])
            unresolved_alerts.append(
                {
                    **pending,
                    "status": "UNRESOLVED_AT_END",
                    "age_at_end": int(age_at_end),
                    "resolution_horizon_elapsed": (
                        age_at_end >= self.resolution_horizon
                    ),
                }
            )

        resolved_structural_count = sum(
            len(item["resolved_pending_alerts"])
            for item in structural_breaks
        )
        resolved_transient_count = len(transient_anomalies)
        unresolved_count = len(unresolved_alerts)
        terminal_count = (
            resolved_structural_count
            + resolved_transient_count
            + unresolved_count
        )
        if pending_opened != terminal_count:
            raise AssertionError(
                "pending_lifecycle_accounting_mismatch:"
                f"opened={pending_opened}, terminal={terminal_count}"
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
                "accounting_complete": pending_opened == terminal_count,
            },
            "diagnostics": {
                "rho_raw": round(rho_raw, 6),
                "rho_adjusted": round(rho_adjusted, 6),
                "rho_used": round(rho_used, 6),
                "rho_bias_correction_enabled": self.rho_bias_correction,
                "baseline_center": round(baseline_center, 6),
                "base_diff_scale": round(base_diff_mad, 6),
            },
        }

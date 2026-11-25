"""Faithful implementation of Gemini's ImprovedSequentialBreakEngine."""
from __future__ import annotations

from typing import Any
import numpy as np


class ImprovedSequentialBreakEngine:
    """Three-stage structural-break classifier.

    onset_time is the retrospective start of the confirming window.
    The decision is only available at onset_time + confirm_window - 1 because
    the algorithm reads the complete confirmation window.
    """

    def __init__(
        self,
        quiet_end: int = 40,
        anomaly_z_thresh: float = 3.2,
        confirm_window: int = 12,
        break_percent_thresh: float = 76.0,
    ) -> None:
        if quiet_end < 3:
            raise ValueError("quiet_end_must_be_at_least_3")
        if anomaly_z_thresh <= 0:
            raise ValueError("anomaly_z_thresh_must_be_positive")
        if confirm_window < 2:
            raise ValueError("confirm_window_must_be_at_least_2")
        if not 0 <= break_percent_thresh <= 100:
            raise ValueError("break_percent_thresh_out_of_range")
        self.quiet_end = quiet_end
        self.anomaly_z_thresh = anomaly_z_thresh
        self.confirm_window = confirm_window
        self.break_percent_thresh = break_percent_thresh

    def analyze(self, series: np.ndarray | list[float]) -> dict[str, Any]:
        values = np.asarray(series, dtype=float)
        if values.ndim != 1:
            raise ValueError("series_must_be_one_dimensional")
        n = int(values.size)
        if n <= self.quiet_end + self.confirm_window - 1:
            raise ValueError("series_too_short_for_quiet_and_confirmation_windows")
        if not np.all(np.isfinite(values)):
            raise ValueError("series_contains_nonfinite_values")

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
        q_norm = (quiet - baseline_center) / q_spread
        rho = (
            float(np.corrcoef(q_norm[:-1], q_norm[1:])[0, 1])
            if len(q_norm) > 2
            else 0.0
        )
        rho = float(np.clip(0.0 if np.isnan(rho) else rho, 0.0, 0.88))

        ar_factor = 1.0 / np.sqrt(max(1.0 - rho, 0.18))
        lrv_factor = np.sqrt((1.0 + rho) / max(1.0 - rho, 0.18))

        transient_anomalies: list[dict[str, Any]] = []
        structural_breaks: list[dict[str, Any]] = []
        latched_direction = 0

        for t in range(self.quiet_end, n - self.confirm_window + 1):
            hist_start = max(1, t - 15)
            local_diffs = np.abs(
                np.diff(values[hist_start : t + self.confirm_window])
            )
            local_diff_mad = float(
                np.median(local_diffs) * 1.4826 / np.sqrt(2.0)
            )
            current_diff_scale = max(base_diff_mad, local_diff_mad)

            marginal_scale = current_diff_scale * ar_factor
            context_scale = current_diff_scale * lrv_factor

            # This full future window is intentional: it means evidence is
            # available only at t + confirm_window - 1, not at t.
            window = values[t : t + self.confirm_window]
            z_point = (window - baseline_center) / marginal_scale
            z_context = (window - baseline_center) / context_scale

            z_current = float(z_point[0])
            pos_persistence = float(np.mean(z_point > 1.25))
            neg_persistence = float(np.mean(z_point < -1.25))
            window_shift_z = float(np.median(z_context))

            if (
                abs(z_current) > self.anomaly_z_thresh
                and max(pos_persistence, neg_persistence) < 0.45
            ):
                transient_anomalies.append(
                    {
                        "time": int(t),
                        "value": round(float(values[t]), 3),
                        "deviation_sigma": round(z_current, 2),
                    }
                )
                continue

            dominant_persistence = max(
                pos_persistence, neg_persistence
            )
            direction = (
                1 if pos_persistence >= neg_persistence else -1
            )
            signs = np.sign(window - baseline_center)
            directional_purity = float(np.mean(signs == direction))
            separation_score = min(abs(window_shift_z) / 2.1, 1.0)
            break_pct = round(
                float(
                    (
                        0.45 * dominant_persistence
                        + 0.35 * separation_score
                        + 0.20 * directional_purity
                    )
                    * 100.0
                ),
                1,
            )

            if (
                break_pct >= self.break_percent_thresh
                and latched_direction != direction
            ):
                structural_breaks.append(
                    {
                        "onset_time": int(t),
                        "direction": int(direction),
                        "break_percentage": float(break_pct),
                        "new_level": round(float(np.median(window)), 3),
                        "baseline_level": round(baseline_center, 3),
                    }
                )
                latched_direction = direction
            elif abs(window_shift_z) < 0.45:
                latched_direction = 0

        return {
            "transient_anomalies": transient_anomalies,
            "structural_breaks": structural_breaks,
        }

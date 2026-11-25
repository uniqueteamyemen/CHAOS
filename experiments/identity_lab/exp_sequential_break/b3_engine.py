"""Isolated B-v3 candidate: FLRV + local difference scale + winsorized scores."""
from __future__ import annotations

from typing import Any

import numpy as np


class SequentialBreakEngineB3:
    """Causal rolling-window B-v3 detector.

    detection_time is the current observation index at which evidence is
    sufficient. estimated_onset is a retrospective robust contrast estimate
    using observations no later than detection_time.
    """

    def __init__(
        self,
        quiet_end: int = 40,
        window_size: int = 12,
        anomaly_z_thresh: float = 3.2,
        winsor_cap: float = 2.5,
        break_percent_thresh: float = 82.0,
        onset_lookback: int = 22,
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
        if onset_lookback < 6:
            raise ValueError("onset_lookback_must_be_at_least_6")

        self.quiet_end = quiet_end
        self.window_size = window_size
        self.anomaly_z_thresh = anomaly_z_thresh
        self.winsor_cap = winsor_cap
        self.break_percent_thresh = break_percent_thresh
        self.onset_lookback = onset_lookback

    def _estimate_onset(
        self, series: np.ndarray, detection_t: int, lookback: int | None = None
    ) -> int:
        """Estimate a historical split using only data available at detection_t."""
        lookback = self.onset_lookback if lookback is None else int(lookback)
        start = max(self.quiet_end, detection_t - lookback)
        segment = series[start : detection_t + 1]
        if len(segment) < 6:
            return int(start)

        best_tau = start
        best_contrast = -1.0
        for split in range(2, len(segment) - 2):
            before = float(np.median(segment[:split]))
            after = float(np.median(segment[split:]))
            contrast = abs(after - before)
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
        q_norm = (quiet - baseline_center) / q_spread

        # Correct lag-1 autocorrelation: correlate adjacent observations.
        # np.corrcoef(q_norm[:-1]) would correlate a vector with itself and
        # return 1.0, incorrectly forcing the estimate to the upper clamp.
        if len(q_norm) > 2 and np.std(q_norm[:-1]) > 1e-12 and np.std(q_norm[1:]) > 1e-12:
            rho_raw = float(np.corrcoef(q_norm[:-1], q_norm[1:])[0, 1])
        else:
            rho_raw = 0.0
        rho = float(np.clip(0.0 if not np.isfinite(rho_raw) else rho_raw, 0.0, 0.88))

        ar_factor = 1.0 / np.sqrt(max(1.0 - rho, 0.12))
        lrv_factor = np.sqrt(1.0 + rho) / max(1.0 - rho, 0.12)

        transient_anomalies: list[dict[str, Any]] = []
        structural_breaks: list[dict[str, Any]] = []
        latched_direction = 0

        start_t = self.quiet_end + self.window_size - 1
        for detection_t in range(start_t, n):
            win_start = detection_t - self.window_size + 1
            window = values[win_start : detection_t + 1]

            # Strictly causal: difference history ends at detection_t.
            hist_start = max(1, win_start - 10)
            local_diffs = np.abs(np.diff(values[hist_start : detection_t + 1]))
            local_diff_mad = (
                float(np.median(local_diffs) * 1.4826 / np.sqrt(2.0))
                if local_diffs.size
                else 0.0
            )
            active_diff_scale = max(base_diff_mad, local_diff_mad, 1e-6)

            marginal_scale = active_diff_scale * ar_factor
            context_scale = active_diff_scale * lrv_factor

            z_point_raw = (window - baseline_center) / marginal_scale
            z_context_raw = (window - baseline_center) / context_scale

            # Preserve transient-outlier detection on the unbounded current score.
            z_current = float(z_point_raw[-1])
            pos_hist = float(np.mean(z_point_raw[:-1] > 1.35))
            neg_hist = float(np.mean(z_point_raw[:-1] < -1.35))
            if (
                abs(z_current) > self.anomaly_z_thresh
                and max(pos_hist, neg_hist) < 0.30
            ):
                transient_anomalies.append(
                    {
                        "time": int(detection_t),
                        "value": round(float(values[detection_t]), 6),
                        "deviation_sigma": round(z_current, 3),
                    }
                )
                continue

            # Winsorize only the scores used by the structural-break classifier.
            z_point = np.clip(z_point_raw, -self.winsor_cap, self.winsor_cap)
            z_context = np.clip(z_context_raw, -self.winsor_cap, self.winsor_cap)

            full_pos = float(np.mean(z_point > 1.30))
            full_neg = float(np.mean(z_point < -1.30))
            dominant_persistence = max(full_pos, full_neg)
            direction = 1 if full_pos >= full_neg else -1

            window_shift_z = float(np.median(z_context))
            separation_score = min(abs(window_shift_z) / 1.45, 1.0)
            break_pct = (
                0.45 * dominant_persistence + 0.55 * separation_score
            ) * 100.0

            if (
                break_pct >= self.break_percent_thresh
                and latched_direction != direction
            ):
                estimated_onset = self._estimate_onset(values, detection_t)
                structural_breaks.append(
                    {
                        "detection_time": int(detection_t),
                        "estimated_onset": int(estimated_onset),
                        "direction": int(direction),
                        "break_percentage": round(float(break_pct), 1),
                    }
                )
                latched_direction = direction
            elif abs(window_shift_z) < 0.40:
                latched_direction = 0

        return {
            "transient_anomalies": transient_anomalies,
            "structural_breaks": structural_breaks,
            "diagnostics": {
                "rho_estimate": round(rho, 6),
                "base_diff_scale": round(base_diff_mad, 6),
                "baseline_center": round(baseline_center, 6),
            },
        }

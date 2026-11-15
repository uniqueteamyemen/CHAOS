"""B-v7 quantized block-fusion sequential-break detector.

No autocorrelation coefficient is estimated. Dependence is represented only
through overlapping quiet-block median dispersion and a robust difference-
scale ratio. Structural decisions use strict, non-compensatory gates.
"""
from __future__ import annotations

from typing import Any

import numpy as np


class QuantizedBlockFusionEngineB7:
    def __init__(
        self,
        quiet_end: int = 40,
        window_size: int = 12,
        series_length: int = 140,
        onset: int = 65,
        resolution_horizon: int = 14,
        anomaly_z_thresh: float = 3.8,
        c_sup: float = 1.15,
        z_block: float = 2.0,
        epoch_z_threshold: float = 1.25,
        quantized_mean_min: float = 1.15,
        return_to_baseline_z: float = 1.5,
        latch_reset_block_z: float = 0.40,
    ) -> None:
        if quiet_end < window_size or window_size != 12:
            raise ValueError("quiet_end_must_cover_a_12_point_window")
        if series_length <= quiet_end + window_size:
            raise ValueError("series_length_too_short")
        if not 0 <= onset < series_length:
            raise ValueError("onset_out_of_range")
        if resolution_horizon < 1:
            raise ValueError("resolution_horizon_must_be_positive")
        if anomaly_z_thresh <= 0 or c_sup <= 0 or z_block <= 0:
            raise ValueError("positive_thresholds_required")
        if epoch_z_threshold <= 0 or quantized_mean_min <= 0:
            raise ValueError("positive_fusion_thresholds_required")
        if return_to_baseline_z <= 0 or latch_reset_block_z < 0:
            raise ValueError("invalid_lifecycle_thresholds")

        self.quiet_end = int(quiet_end)
        self.window_size = int(window_size)
        self.series_length = int(series_length)
        self.onset = int(onset)
        self.resolution_horizon = int(resolution_horizon)
        self.anomaly_z_thresh = float(anomaly_z_thresh)
        self.c_sup = float(c_sup)
        self.z_block = float(z_block)
        self.epoch_z_threshold = float(epoch_z_threshold)
        self.quantized_mean_min = float(quantized_mean_min)
        self.return_to_baseline_z = float(return_to_baseline_z)
        self.latch_reset_block_z = float(latch_reset_block_z)

    @staticmethod
    def _estimate_onset(
        series: np.ndarray, detection_t: int, quiet_end: int, lookback: int = 22
    ) -> int:
        start = max(quiet_end, detection_t - int(lookback))
        segment = series[start : detection_t + 1]
        if segment.size < 6:
            return int(start)
        best_split = start
        best_contrast = -1.0
        for split in range(2, segment.size - 2):
            contrast = abs(
                float(np.median(segment[split:]) - np.median(segment[:split]))
            )
            if contrast > best_contrast:
                best_contrast = contrast
                best_split = start + split
        return int(best_split)

    @staticmethod
    def _robust_difference_scale(values: np.ndarray) -> float:
        differences = np.diff(np.asarray(values, dtype=float))
        if differences.size == 0:
            return 1e-6
        return max(
            float(1.4826 * np.median(np.abs(differences)) / np.sqrt(2.0)),
            1e-6,
        )

    @staticmethod
    def _quantize_z(z_values: np.ndarray) -> np.ndarray:
        # np.rint uses round-to-nearest, ties-to-even; then saturate at +/-2.
        return np.clip(np.rint(np.asarray(z_values, dtype=float)), -2.0, 2.0)

    def _baseline(self, quiet: np.ndarray) -> dict[str, Any]:
        center = float(np.median(quiet))
        point_scale = max(
            float(1.4826 * np.median(np.abs(quiet - center))),
            1e-6,
        )
        difference_scale = self._robust_difference_scale(quiet)
        block_medians = np.asarray(
            [
                float(np.median(quiet[index : index + self.window_size]))
                for index in range(self.quiet_end - self.window_size + 1)
            ],
            dtype=float,
        )
        block_deviations = np.abs(block_medians - center)
        block_scale = max(
            float(1.4826 * np.median(block_deviations)),
            1e-6,
        )
        block_supremum = float(np.percentile(block_deviations, 95.0))
        return {
            "center": center,
            "point_scale": point_scale,
            "difference_scale": difference_scale,
            "block_medians": block_medians,
            "block_scale": block_scale,
            "block_supremum": block_supremum,
        }

    def _structural_gates(
        self,
        window: np.ndarray,
        z_points: np.ndarray,
        center: float,
        block_scale_t: float,
        block_supremum_t: float,
    ) -> dict[str, Any]:
        window_median = float(np.median(window))
        displacement = window_median - center
        direction = 1 if displacement > 0 else (-1 if displacement < 0 else 0)
        abs_displacement = abs(displacement)

        amplitude_supremum = abs_displacement > self.c_sup * block_supremum_t
        amplitude_block_z = abs_displacement / block_scale_t > self.z_block
        amplitude_gate = amplitude_supremum and amplitude_block_z

        epoch_medians = [
            float(np.median(window[0:4])),
            float(np.median(window[4:8])),
            float(np.median(window[8:12])),
        ]
        epoch_deviations = [value - center for value in epoch_medians]
        epoch_block_z = [
            abs(value) / block_scale_t for value in epoch_deviations
        ]
        epoch_position_gate = direction != 0 and all(
            np.sign(value) == direction
            and score > self.epoch_z_threshold
            for value, score in zip(epoch_deviations, epoch_block_z)
        )

        quantized = self._quantize_z(z_points)
        quantized_directional_mean = (
            float(direction * np.mean(quantized)) if direction else 0.0
        )
        quantized_gate = (
            direction != 0
            and quantized_directional_mean >= self.quantized_mean_min
        )

        return {
            "direction": int(direction),
            "window_median": window_median,
            "displacement": float(displacement),
            "amplitude_supremum_gate": bool(amplitude_supremum),
            "amplitude_block_z_gate": bool(amplitude_block_z),
            "amplitude_gate": bool(amplitude_gate),
            "epoch_medians": epoch_medians,
            "epoch_deviations": epoch_deviations,
            "epoch_block_z": epoch_block_z,
            "epoch_position_gate": bool(epoch_position_gate),
            "quantized_values": quantized.astype(int).tolist(),
            "quantized_directional_mean": round(quantized_directional_mean, 6),
            "quantized_gate": bool(quantized_gate),
            "structural_gate_passed": bool(
                amplitude_gate and epoch_position_gate and quantized_gate
            ),
        }

    def analyze(self, series: np.ndarray | list[float]) -> dict[str, Any]:
        values = np.asarray(series, dtype=float)
        if values.ndim != 1:
            raise ValueError("series_must_be_one_dimensional")
        if not np.all(np.isfinite(values)):
            raise ValueError("series_contains_nonfinite_values")
        if values.size != self.series_length:
            raise ValueError(
                f"series_length_must_equal_{self.series_length}:got_{values.size}"
            )

        baseline = self._baseline(values[: self.quiet_end])
        center = float(baseline["center"])
        point_scale = float(baseline["point_scale"])
        difference_scale = float(baseline["difference_scale"])
        block_scale = float(baseline["block_scale"])
        block_supremum = float(baseline["block_supremum"])

        structural_breaks: list[dict[str, Any]] = []
        transient_anomalies: list[dict[str, Any]] = []
        unresolved_alerts: list[dict[str, Any]] = []
        pending_alerts: list[dict[str, Any]] = []
        pending_opened = 0
        latched_direction = 0

        first_t = self.quiet_end + self.window_size - 1
        for t in range(first_t, self.series_length):
            window_start = t - self.window_size + 1
            window = values[window_start : t + 1]
            hist_start = max(1, t - 21)
            hist = values[hist_start : t + 1]

            local_difference_scale = self._robust_difference_scale(hist)
            scale_ratio = max(1.0, local_difference_scale / difference_scale)
            point_scale_t = point_scale * scale_ratio
            block_scale_t = max(block_scale * scale_ratio, 1e-6)
            block_supremum_t = block_supremum * scale_ratio

            z_points = (window - center) / max(point_scale_t, 1e-6)
            current_z = float(z_points[-1])

            # PENDING gate: exactly three adjacent, same-sign point scores.
            recent_z = z_points[-3:]
            pending_gate_passed = (
                bool(np.all(np.abs(recent_z) > self.anomaly_z_thresh))
                and bool(np.all(np.sign(recent_z) == np.sign(recent_z[-1])))
            )
            recent_pending = any(
                0 <= t - int(alert["time"]) <= 2
                for alert in pending_alerts
            )
            pending_direction = (
                1 if current_z > 0 else (-1 if current_z < 0 else 0)
            )
            if (
                pending_gate_passed
                and latched_direction == 0
                and not recent_pending
                and pending_direction != 0
            ):
                pending_alerts.append(
                    {
                        "time": int(t),
                        "value": round(float(values[t]), 6),
                        "deviation_sigma": round(current_z, 6),
                        "direction": int(pending_direction),
                    }
                )
                pending_opened += 1

            gates = self._structural_gates(
                window, z_points, center, block_scale_t, block_supremum_t
            )
            direction = int(gates["direction"])
            structural_now = (
                bool(gates["structural_gate_passed"])
                and direction != 0
                and latched_direction != direction
            )
            if structural_now:
                estimated_onset = self._estimate_onset(
                    values, t, self.quiet_end
                )
                resolved_pending: list[dict[str, Any]] = []
                still_pending: list[dict[str, Any]] = []
                for alert in pending_alerts:
                    age = t - int(alert["time"])
                    if (
                        int(alert["direction"]) == direction
                        and 0 <= age <= self.resolution_horizon
                    ):
                        resolved_pending.append(
                            {
                                **alert,
                                "resolved_at": int(t),
                                "status": "RESOLVED_STRUCTURAL",
                            }
                        )
                    else:
                        still_pending.append(alert)
                pending_alerts = still_pending
                structural_breaks.append(
                    {
                        "detection_time": int(t),
                        "estimated_onset": int(estimated_onset),
                        "direction": direction,
                        "window_median": round(float(gates["window_median"]), 6),
                        "c_sup": self.c_sup,
                        "z_block": self.z_block,
                        "scale_ratio": round(float(scale_ratio), 6),
                        "amplitude_supremum_gate": gates["amplitude_supremum_gate"],
                        "amplitude_block_z_gate": gates["amplitude_block_z_gate"],
                        "epoch_medians": gates["epoch_medians"],
                        "epoch_block_z": gates["epoch_block_z"],
                        "quantized_directional_mean": gates[
                            "quantized_directional_mean"
                        ],
                        "resolved_pending_alerts": resolved_pending,
                    }
                )
                latched_direction = direction
            else:
                window_block_z = (
                    abs(float(gates["displacement"])) / block_scale_t
                )
                if window_block_z < self.latch_reset_block_z:
                    latched_direction = 0

            # Resolve on an observed return within the horizon. At age 14,
            # no return means an explicit unresolved terminal state.
            still_pending = []
            for alert in pending_alerts:
                age = t - int(alert["time"])
                return_z = abs(
                    (float(values[t]) - center) / max(point_scale, 1e-6)
                )
                returned = (
                    0 < age <= self.resolution_horizon
                    and return_z < self.return_to_baseline_z
                )
                if returned:
                    transient_anomalies.append(
                        {
                            **alert,
                            "resolved_at": int(t),
                            "status": "RESOLVED_TRANSIENT",
                            "resolution_age": int(age),
                            "return_z": round(float(return_z), 6),
                        }
                    )
                elif age >= self.resolution_horizon:
                    unresolved_alerts.append(
                        {
                            **alert,
                            "status": "UNRESOLVED_HORIZON_EXPIRED",
                            "terminal_at": int(t),
                            "last_return_z": round(float(return_z), 6),
                        }
                    )
                else:
                    still_pending.append(alert)
            pending_alerts = still_pending

        # Alerts whose horizon has not elapsed by the end of the series are
        # terminally classified as unresolved-at-end.
        for alert in pending_alerts:
            unresolved_alerts.append(
                {
                    **alert,
                    "status": "UNRESOLVED_AT_END",
                    "terminal_at": self.series_length - 1,
                }
            )

        resolved_structural_count = sum(
            len(item["resolved_pending_alerts"]) for item in structural_breaks
        )
        resolved_transient_count = len(transient_anomalies)
        unresolved_count = len(unresolved_alerts)
        terminal_count = (
            resolved_structural_count + resolved_transient_count + unresolved_count
        )
        if pending_opened != terminal_count:
            raise AssertionError(
                "pending_lifecycle_accounting_mismatch:"
                f"opened={pending_opened},terminal={terminal_count}"
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
                "baseline_center": round(center, 8),
                "point_scale": round(point_scale, 8),
                "difference_scale_baseline": round(difference_scale, 8),
                "block_median_count": int(baseline["block_medians"].size),
                "block_scale": round(block_scale, 8),
                "block_supremum_95": round(block_supremum, 8),
                "c_sup": self.c_sup,
                "z_block": self.z_block,
                "pending_gate_points": 3,
                "pending_gate_threshold": self.anomaly_z_thresh,
                "resolution_horizon": self.resolution_horizon,
                "rho_estimated": False,
            },
        }

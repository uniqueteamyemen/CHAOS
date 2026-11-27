from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np


def _mad_sigma(values: np.ndarray) -> tuple[float, str]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or x.size < 3 or not np.all(np.isfinite(x)):
        return 0.0, "INSUFFICIENT_SCALE_WINDOW"
    center = float(np.median(x))
    deviations = np.abs(x - center)
    mad = 1.4826 * float(np.median(deviations))
    if math.isfinite(mad) and mad > 1e-12:
        return mad, "MAD_SIGMA"
    q25, q75 = np.quantile(x, [0.25, 0.75])
    iqr = float((q75 - q25) / 1.3489795003921634)
    if math.isfinite(iqr) and iqr > 1e-12:
        return iqr, "IQR_SIGMA_FALLBACK"
    nonzero = deviations[deviations > 1e-12]
    if nonzero.size:
        fallback = 1.4826 * float(np.median(nonzero))
        if math.isfinite(fallback) and fallback > 1e-12:
            return fallback, "QUANTIZED_NONZERO_FALLBACK"
    return 0.0, "ZERO_DISPERSION"


class _CausalMultiScaleBase:
    def __init__(
        self,
        *,
        windows: tuple[int, ...],
        baseline_points: int = 24,
        guard_points: int = 2,
        initial_quiet_points: int = 40,
        confirm_points: int = 2,
        rearm_quiet_points: int | None = None,
        max_hits: int | None = None,
        representation: str,
    ) -> None:
        normalized = tuple(sorted({int(value) for value in windows}))
        if not normalized or any(value < 2 for value in normalized):
            raise ValueError("BAD_WINDOWS")
        if isinstance(baseline_points, bool) or int(baseline_points) < 8:
            raise ValueError("BAD_BASELINE_POINTS")
        if isinstance(guard_points, bool) or int(guard_points) < 1:
            raise ValueError("BAD_GUARD_POINTS")
        if isinstance(initial_quiet_points, bool) or int(initial_quiet_points) < 40:
            raise ValueError("BAD_INITIAL_QUIET_POINTS")
        if isinstance(confirm_points, bool) or int(confirm_points) < 1:
            raise ValueError("BAD_CONFIRM_POINTS")
        if rearm_quiet_points is not None and (
            isinstance(rearm_quiet_points, bool) or int(rearm_quiet_points) < 1
        ):
            raise ValueError("BAD_REARM_QUIET_POINTS")
        if max_hits is not None and (
            isinstance(max_hits, bool) or int(max_hits) < 1
        ):
            raise ValueError("BAD_MAX_HITS")
        self.windows = normalized
        self.baseline_points = int(baseline_points)
        self.guard_points = int(guard_points)
        self.initial_quiet_points = int(initial_quiet_points)
        self.confirm_points = int(confirm_points)
        self.rearm_quiet_points = (
            int(rearm_quiet_points) if rearm_quiet_points is not None else None
        )
        self.max_hits = int(max_hits) if max_hits is not None else None
        self.representation = str(representation)

    @staticmethod
    def _positive(value: float) -> bool:
        return math.isfinite(float(value)) and float(value) > 1e-12

    def _score_rows(self, values: Any) -> dict[str, Any]:
        x = np.asarray(values, dtype=float)
        if x.ndim != 1 or x.size == 0:
            raise ValueError("BAD_VALUES")
        if not np.all(np.isfinite(x)):
            raise ValueError("NONFINITE_VALUES")
        if x.size <= max(self.windows) + self.baseline_points + self.guard_points:
            return {
                "status": "NOT_ELIGIBLE", "observations": int(x.size),
                "scores": [], "max_confirmed_score": None,
                "scale_source_counts": {}, "zero_scale_points": 0,
            }

        diffs = np.diff(x)
        rows: list[dict[str, Any]] = []
        scale_sources: Counter[str] = Counter()
        zero_scale_points = 0
        max_window = max(self.windows)
        first_t = max(
            self.initial_quiet_points,
            40 + max_window,
            self.baseline_points + max_window + self.guard_points,
        )
        for t in range(first_t, int(x.size)):
            current_start = t - max_window + 1
            baseline_end = current_start - self.guard_points - 1
            baseline_start = baseline_end - self.baseline_points + 1
            baseline = x[baseline_start:baseline_end + 1]
            if baseline.size != self.baseline_points:
                continue

            scale_window_start = current_start - 40
            scale_window_end = current_start
            if self.representation == "level":
                # 40 first differences ending strictly before the current window.
                scale_values = diffs[scale_window_start - 1:scale_window_end - 1]
            else:
                # Flow is already delta_x; do not difference it again.
                scale_values = x[scale_window_start:scale_window_end]
            if scale_values.size != 40:
                continue
            scale, scale_source = _mad_sigma(scale_values)
            if not self._positive(scale):
                zero_scale_points += 1
                continue

            up_scores: list[float] = []
            down_scores: list[float] = []
            window_scores: dict[str, dict[str, float]] = {}
            if self.representation == "level":
                q15, q85 = (float(value) for value in np.quantile(baseline, [0.15, 0.85]))
                for window in self.windows:
                    current = x[t - window + 1:t + 1]
                    if current.size != window:
                        continue
                    current_mean = float(np.mean(current))
                    up = max(0.0, (current_mean - q85) / scale)
                    down = max(0.0, (q15 - current_mean) / scale)
                    up_scores.append(up)
                    down_scores.append(down)
                    window_scores[str(window)] = {"up": up, "down": down}
                baseline_meta = {"q15": q15, "q85": q85}
            else:
                baseline_median = float(np.median(baseline))
                for window in self.windows:
                    current = x[t - window + 1:t + 1]
                    if current.size != window:
                        continue
                    current_mean = float(np.mean(current))
                    up = max(0.0, (current_mean - baseline_median) / scale)
                    down = max(0.0, (baseline_median - current_mean) / scale)
                    up_scores.append(up)
                    down_scores.append(down)
                    window_scores[str(window)] = {"up": up, "down": down}
                baseline_meta = {"median": baseline_median}

            if not up_scores or not down_scores:
                continue
            score_up = max(up_scores)
            score_down = max(down_scores)
            scale_sources[scale_source] += 1
            rows.append({
                "index": int(t),
                "score_up": float(score_up),
                "score_down": float(score_down),
                "scale": float(scale),
                "scale_source": scale_source,
                "baseline_start_index": int(baseline_start),
                "baseline_end_index": int(baseline_end),
                "current_start_index": int(current_start),
                "current_end_index": int(t),
                "window_scores": window_scores,
                **baseline_meta,
            })

        max_confirmed = self._max_confirmed_score(rows, self.confirm_points)
        return {
            "status": "OK" if rows else "NOT_ELIGIBLE",
            "observations": int(x.size),
            "windows": list(self.windows),
            "baseline_points": self.baseline_points,
            "guard_points": self.guard_points,
            "initial_quiet_points": self.initial_quiet_points,
            "confirm_points": self.confirm_points,
            "scores": rows,
            "max_confirmed_score": max_confirmed,
            "scale_source_counts": dict(sorted(scale_sources.items())),
            "zero_scale_points": int(zero_scale_points),
            "score_definition": (
                "max over registered windows of directional mean excursion beyond "
                "the prior q85/q15 band divided by causal MAD_40(first_difference)"
                if self.representation == "level" else
                "max over registered windows of directional mean-flow displacement "
                "from prior baseline median divided by causal MAD_40(delta_x)"
            ),
        }

    def score_trace(self, values: Any) -> dict[str, Any]:
        return self._score_rows(values)

    def detect(self, values: Any, *, threshold: float) -> dict[str, Any]:
        if isinstance(threshold, bool) or not self._positive(float(threshold)):
            raise ValueError("BAD_THRESHOLD")
        scored = self._score_rows(values)
        if scored["status"] != "OK":
            return {
                "status": scored["status"], "hits": [], "event_count": 0,
                "threshold": float(threshold),
                "zero_scale_points": scored.get("zero_scale_points", 0),
            }

        armed_pos = True
        armed_neg = True
        pos_streak = neg_streak = 0
        pos_rearm_count = neg_rearm_count = 0
        hits: list[dict[str, Any]] = []
        for row in scored["scores"]:
            index = int(row["index"])
            up = float(row["score_up"])
            down = float(row["score_down"])

            if armed_pos:
                if up >= float(threshold):
                    pos_streak += 1
                else:
                    pos_streak = 0
                if pos_streak >= self.confirm_points:
                    hits.append({
                        "index": index, "sign": 1, "score": up,
                        "scale": row["scale"], "scale_source": row["scale_source"],
                        "detector": type(self).__name__,
                    })
                    armed_pos = False
                    pos_streak = 0
                    pos_rearm_count = 0
            else:
                # Directional hysteresis: the opposite track remains armed.
                if up < float(threshold) * 0.5:
                    pos_rearm_count += 1
                else:
                    pos_rearm_count = 0
                if pos_rearm_count >= self.confirm_points:
                    armed_pos = True
                    pos_rearm_count = 0

            if armed_neg:
                if down >= float(threshold):
                    neg_streak += 1
                else:
                    neg_streak = 0
                if neg_streak >= self.confirm_points:
                    hits.append({
                        "index": index, "sign": -1, "score": down,
                        "scale": row["scale"], "scale_source": row["scale_source"],
                        "detector": type(self).__name__,
                    })
                    armed_neg = False
                    neg_streak = 0
                    neg_rearm_count = 0
            else:
                if down < float(threshold) * 0.5:
                    neg_rearm_count += 1
                else:
                    neg_rearm_count = 0
                if neg_rearm_count >= self.confirm_points:
                    armed_neg = True
                    neg_rearm_count = 0

            if self.max_hits is not None and len(hits) >= self.max_hits:
                break

        hits.sort(key=lambda item: (int(item["index"]), -int(item["sign"])))
        return {
            "status": "OK", "hits": hits, "event_count": len(hits),
            "observations": int(scored["observations"]),
            "windows": list(self.windows),
            "baseline_points": self.baseline_points,
            "guard_points": self.guard_points,
            "confirm_points": self.confirm_points,
            "threshold": float(threshold),
            "rearm_policy": (
                f"independent_directional_tracks_rearm_after_{self.confirm_points}_"
                "consecutive_scores_below_half_threshold"
            ),
            "max_confirmed_score": scored["max_confirmed_score"],
            "scale_source_counts": scored["scale_source_counts"],
            "zero_scale_points": scored["zero_scale_points"],
        }

    @staticmethod
    def _max_confirmed_score(rows: list[dict[str, Any]], confirm_points: int) -> float | None:
        best: float | None = None
        for field, sign in (("score_up", 1), ("score_down", -1)):
            for start in range(len(rows)):
                segment = rows[start:start + confirm_points]
                if len(segment) != confirm_points:
                    break
                if any(
                    int(segment[i + 1]["index"]) != int(segment[i]["index"]) + 1
                    for i in range(confirm_points - 1)
                ):
                    continue
                values = [float(item[field]) for item in segment]
                if all(value > 0 for value in values):
                    value = min(values)
                    best = value if best is None else max(best, value)
        return best


class CausalMultiScaleExcursionDetector(_CausalMultiScaleBase):
    def __init__(
        self, *, windows: tuple[int, ...], baseline_points: int = 24,
        guard_points: int = 2, initial_quiet_points: int = 40,
        confirm_points: int = 2,
    ) -> None:
        super().__init__(
            windows=windows, baseline_points=baseline_points,
            guard_points=guard_points, initial_quiet_points=initial_quiet_points,
            confirm_points=confirm_points, representation="level",
        )


class CausalMultiScaleFlowDetector(_CausalMultiScaleBase):
    def __init__(
        self, *, windows: tuple[int, ...] = (3, 12), baseline_points: int = 24,
        guard_points: int = 2, initial_quiet_points: int = 40,
        confirm_points: int = 2, rearm_quiet_points: int = 6,
    ) -> None:
        super().__init__(
            windows=windows, baseline_points=baseline_points,
            guard_points=guard_points, initial_quiet_points=initial_quiet_points,
            confirm_points=confirm_points, rearm_quiet_points=rearm_quiet_points,
            representation="flow",
        )

    def detect(self, values: Any, *, threshold: float) -> dict[str, Any]:
        if isinstance(threshold, bool) or not self._positive(float(threshold)):
            raise ValueError("BAD_THRESHOLD")
        scored = self._score_rows(values)
        if scored["status"] != "OK":
            return {
                "status": scored["status"], "hits": [], "event_count": 0,
                "threshold": float(threshold),
                "zero_scale_points": scored.get("zero_scale_points", 0),
            }

        armed_pos = True
        armed_neg = True
        pos_streak = neg_streak = 0
        pos_quiet = neg_quiet = 0
        hits: list[dict[str, Any]] = []
        for row in scored["scores"]:
            index = int(row["index"])
            up = float(row["score_up"])
            down = float(row["score_down"])
            if armed_pos:
                pos_streak = pos_streak + 1 if up >= threshold else 0
                if pos_streak >= self.confirm_points:
                    hits.append({
                        "index": index, "sign": 1, "score": up,
                        "scale": row["scale"], "scale_source": row["scale_source"],
                        "detector": type(self).__name__,
                    })
                    armed_pos, pos_streak, pos_quiet = False, 0, 0
            else:
                pos_quiet = pos_quiet + 1 if up < threshold * 0.5 else 0
                if pos_quiet >= int(self.rearm_quiet_points):
                    armed_pos, pos_quiet = True, 0

            if armed_neg:
                neg_streak = neg_streak + 1 if down >= threshold else 0
                if neg_streak >= self.confirm_points:
                    hits.append({
                        "index": index, "sign": -1, "score": down,
                        "scale": row["scale"], "scale_source": row["scale_source"],
                        "detector": type(self).__name__,
                    })
                    armed_neg, neg_streak, neg_quiet = False, 0, 0
            else:
                neg_quiet = neg_quiet + 1 if down < threshold * 0.5 else 0
                if neg_quiet >= int(self.rearm_quiet_points):
                    armed_neg, neg_quiet = True, 0

        hits.sort(key=lambda item: (int(item["index"]), -int(item["sign"])))
        return {
            "status": "OK", "hits": hits, "event_count": len(hits),
            "observations": int(scored["observations"]),
            "windows": list(self.windows),
            "baseline_points": self.baseline_points,
            "guard_points": self.guard_points,
            "confirm_points": self.confirm_points,
            "rearm_quiet_points": int(self.rearm_quiet_points),
            "threshold": float(threshold),
            "rearm_policy": "independent_directional_tracks_after_six_quiet_scores_below_half_threshold",
            "max_confirmed_score": scored["max_confirmed_score"],
            "scale_source_counts": scored["scale_source_counts"],
            "zero_scale_points": scored["zero_scale_points"],
        }

import math
from collections import Counter
import numpy as np

class CausalLocalSlopeShiftDetector:

    def __init__(self, *, window=12, initial_quiet_points=40, confirm_points=3, rearm_quiet_points=6, rearm_ratio=0.5, max_hits=12):
        if isinstance(window, bool) or int(window) < 4:
            raise ValueError('BAD_WINDOW')
        if isinstance(initial_quiet_points, bool) or int(initial_quiet_points) < 2 * int(window):
            raise ValueError('BAD_INITIAL_QUIET')
        if isinstance(confirm_points, bool) or int(confirm_points) < 1:
            raise ValueError('BAD_CONFIRM_POINTS')
        if isinstance(rearm_quiet_points, bool) or int(rearm_quiet_points) < 1:
            raise ValueError('BAD_REARM_POINTS')
        if not math.isfinite(float(rearm_ratio)) or not 0.0 < float(rearm_ratio) < 1.0:
            raise ValueError('BAD_REARM_RATIO')
        if isinstance(max_hits, bool) or int(max_hits) < 1:
            raise ValueError('BAD_MAX_HITS')
        self.window = int(window)
        self.initial_quiet_points = int(initial_quiet_points)
        self.confirm_points = int(confirm_points)
        self.rearm_quiet_points = int(rearm_quiet_points)
        self.rearm_ratio = float(rearm_ratio)
        self.max_hits = int(max_hits)

    @staticmethod
    def _positive_finite(value):
        return math.isfinite(float(value)) and float(value) > 1e-12

    @classmethod
    def _scale_from_window(cls, values):
        if values.size < 3:
            return (0.0, 'TOO_FEW_BASELINE_POINTS')
        center = float(np.median(values))
        deviations = np.abs(values - center)
        mad_sigma = 1.4826 * float(np.median(deviations))
        if cls._positive_finite(mad_sigma):
            return (mad_sigma, 'LOCAL_BASELINE_MAD_SIGMA')
        q25, q75 = np.quantile(values, [0.25, 0.75])
        iqr_sigma = float((q75 - q25) / 1.3489795003921634)
        if cls._positive_finite(iqr_sigma):
            return (iqr_sigma, 'LOCAL_BASELINE_IQR_SIGMA')
        nonzero = deviations[deviations > 1e-12]
        if nonzero.size >= 1:
            quantized_sigma = 1.4826 * float(np.median(nonzero))
            if cls._positive_finite(quantized_sigma):
                return (quantized_sigma, 'LOCAL_QUANTIZATION_FALLBACK')
        return (0.0, 'ZERO_LOCAL_DISPERSION')

    def score_trace(self, values):
        x = np.asarray(values, dtype=float)
        if x.ndim != 1 or x.size == 0:
            raise ValueError('BAD_VALUES')
        if not np.all(np.isfinite(x)):
            raise ValueError('NONFINITE_VALUES')
        w = self.window
        minimum_required = max(2 * w + 1, self.initial_quiet_points + self.confirm_points)
        if x.size < minimum_required:
            return {'status': 'NOT_ELIGIBLE', 'observations': int(x.size), 'scores': [], 'max_confirmed_score': None, 'scale_source_counts': {}, 'zero_scale_points': 0}
        diffs = np.diff(x)
        rows = []
        scale_sources = Counter()
        zero_scale_points = 0
        first_j = max(2 * w - 1, self.initial_quiet_points - 1)
        for j in range(first_j, diffs.size):
            baseline_end = j - w + 1
            baseline_start = baseline_end - w
            baseline = diffs[baseline_start:baseline_end]
            current = diffs[baseline_end:j + 1]
            if baseline.size != w or current.size != w:
                continue
            scale, source = self._scale_from_window(baseline)
            if not self._positive_finite(scale):
                zero_scale_points += 1
                continue
            baseline_slope = float(np.median(baseline))
            current_slope = float(np.median(current))
            standard_error = scale * math.sqrt(math.pi / float(w))
            if not self._positive_finite(standard_error):
                zero_scale_points += 1
                continue
            score = (current_slope - baseline_slope) / standard_error
            sign = 1 if score > 0.0 else -1 if score < 0.0 else 0
            scale_sources[source] += 1
            rows.append({'index': int(j + 1), 'score': float(score), 'sign': int(sign), 'baseline_slope': baseline_slope, 'current_slope': current_slope, 'baseline_scale_sigma': float(scale), 'scale_source': source})
        max_confirmed = self._max_confirmed_score(rows, self.confirm_points)
        return {'status': 'OK', 'observations': int(x.size), 'window_points': w, 'initial_quiet_points': self.initial_quiet_points, 'confirm_points': self.confirm_points, 'scores': rows, 'max_confirmed_score': max_confirmed, 'scale_source_counts': dict(sorted(scale_sources.items())), 'zero_scale_points': int(zero_scale_points)}

    @staticmethod
    def _max_confirmed_score(rows, confirm_points):
        best = None
        if not rows:
            return None
        for start in range(len(rows)):
            segment = rows[start:start + confirm_points]
            if len(segment) != confirm_points:
                break
            if any((int(segment[k + 1]['index']) != int(segment[k]['index']) + 1 for k in range(confirm_points - 1))):
                continue
            sign = int(segment[0]['sign'])
            if sign == 0 or any((int(row['sign']) != sign for row in segment)):
                continue
            value = min((abs(float(row['score'])) for row in segment))
            best = value if best is None else max(best, value)
        return best

    def detect(self, values, *, threshold):
        if isinstance(threshold, bool) or not math.isfinite(float(threshold)) or float(threshold) <= 0:
            raise ValueError('BAD_THRESHOLD')
        scored = self.score_trace(values)
        if scored['status'] != 'OK':
            return {'status': scored['status'], 'hits': [], 'event_count': 0, 'threshold': float(threshold), 'zero_scale_points': scored.get('zero_scale_points', 0)}
        cutoff = float(threshold)
        armed = True
        quiet_count = 0
        streak_sign = 0
        streak_count = 0
        hits = []
        previous_index = None
        for row in scored['scores']:
            row_index = int(row['index'])
            if previous_index is not None and row_index != previous_index + 1:
                streak_sign = 0
                streak_count = 0
                quiet_count = 0
            previous_index = row_index
            score = float(row['score'])
            sign = int(row['sign'])
            if not armed:
                if abs(score) < cutoff * self.rearm_ratio:
                    quiet_count += 1
                else:
                    quiet_count = 0
                if quiet_count >= self.rearm_quiet_points:
                    armed = True
                    quiet_count = 0
                    streak_sign = 0
                    streak_count = 0
                continue
            if sign != 0 and abs(score) >= cutoff:
                if sign == streak_sign:
                    streak_count += 1
                else:
                    streak_sign = sign
                    streak_count = 1
                if streak_count >= self.confirm_points:
                    hits.append({'index': int(row['index']), 'sign': sign, 'score': score, 'baseline_slope': float(row['baseline_slope']), 'current_slope': float(row['current_slope']), 'baseline_scale_sigma': float(row['baseline_scale_sigma']), 'scale_source': row['scale_source']})
                    armed = False
                    quiet_count = 0
                    streak_sign = 0
                    streak_count = 0
                    if len(hits) >= self.max_hits:
                        break
            else:
                streak_sign = 0
                streak_count = 0
        return {'status': 'OK', 'hits': hits, 'event_count': len(hits), 'observations': int(scored['observations']), 'window_points': self.window, 'initial_quiet_points': self.initial_quiet_points, 'confirm_points': self.confirm_points, 'rearm_quiet_points': self.rearm_quiet_points, 'rearm_ratio': self.rearm_ratio, 'threshold': cutoff, 'max_confirmed_score': scored['max_confirmed_score'], 'scale_source_counts': scored['scale_source_counts'], 'zero_scale_points': scored['zero_scale_points']}

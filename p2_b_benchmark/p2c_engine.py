"""P2-C detector implementations.

FOCuS is an exact Gaussian functional-pruning CUSUM envelope on a continuous
mean-shift parameter interval (no fixed window bank / no parameter grid).
BOCPD uses a Normal-Inverse-Gamma predictive Student-t model and posterior
short-run-length mass. Bartlett LRV is a scale estimator used only inside the
Post-Quiet Huber comparison. R-FPOP is a separate retrospective Huber
segmentation track backed by the pinned LGPL robseg implementation.
"""
from __future__ import annotations

import ctypes
import hashlib
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.special import gammaln, logsumexp

from p2_b_benchmark.engine import mad_sigma

QUIET_POINTS = 40
FOCUS_THRESHOLD = 45.0
BOCPD_HAZARD = 1.0 / 60.0
BOCPD_MAX_RUN = 539
BOCPD_SHORT_RUN_MAX = 24
BOCPD_SHORT_MASS_THRESHOLD = 0.35
BOCPD_PERSISTENCE = 12
BOCPD_MIN_REGIME_SHIFT = 1.0
BOCPD_MIN_CONTRAST_Z = 2.0
BOCPD_REARM_LONG_MASS = 0.80
BOCPD_REARM_PERSISTENCE = 3
HUBER_C = 1.345
HUBER_K = 0.50
HUBER_THRESHOLD = 12.0
HUBER_MAX_EVENTS = 12
R_FPOP_HUBER_K = 1.345
R_FPOP_PENALTY_MULTIPLIER = 1.4

P2C_VARIANTS: dict[str, dict[str, Any]] = {
    "A_FAST": {"kind": "frozen_break_detector_v1", "mode": "fast", "version": "frozen"},
    "A_CONSENSUS": {"kind": "frozen_break_detector_v1", "mode": "consensus", "version": "frozen"},
    "FOCUS": {
        "kind": "online_functional_pruning_cusum", "version": "p2c-focus-1.0",
        "parameters": {"quiet_points": QUIET_POINTS, "threshold": FOCUS_THRESHOLD,
                       "delta_domain": "(-inf,+inf)",
                       "functional_pruning": True, "parameter_grid": False},
    },
    "BOCPD": {
        "kind": "bayesian_online_changepoint", "version": "p2c-bocpd-1.0",
        "parameters": {"hazard": BOCPD_HAZARD, "max_run_length": BOCPD_MAX_RUN,
                       "short_run_max": BOCPD_SHORT_RUN_MAX,
                       "short_run_mass_threshold": BOCPD_SHORT_MASS_THRESHOLD,
                       "posterior_persistence": BOCPD_PERSISTENCE,
                       "predictive": "Normal-Inverse-Gamma Student-t"},
    },
    "POST_QUIET_HUBER_MAD": {
        "kind": "post_quiet_huber", "version": "p2c-huber-1.0",
        "parameters": {"scale_estimator": "MAD", "huber_c": HUBER_C,
                       "k": HUBER_K, "threshold": HUBER_THRESHOLD,
                       "quiet_points": QUIET_POINTS},
    },
    "POST_QUIET_HUBER_BARTLETT": {
        "kind": "post_quiet_huber", "version": "p2c-huber-1.0",
        "parameters": {"scale_estimator": "Bartlett-LRV", "huber_c": HUBER_C,
                       "k": HUBER_K, "threshold": HUBER_THRESHOLD,
                       "quiet_points": QUIET_POINTS},
    },
}
ONLINE_ARMS = (
    "FOCUS", "BOCPD", "POST_QUIET_HUBER_MAD", "POST_QUIET_HUBER_BARTLETT"
)


def _validate_series(values: Any, quiet_points: int = QUIET_POINTS) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)):
        raise ValueError("p2c_series_must_be_finite_1d")
    return x


def _abstain_result(reason: str, **metadata: Any) -> dict[str, Any]:
    return {"status": "ABSTAIN", "abstain_reason": reason,
            "hits": [], "events": [], "event_count": 0, "metadata": metadata}


def bartlett_lrv_scale(values: Any, bandwidth: int | None = None) -> dict[str, Any]:
    """Bartlett-kernel HAC long-run SD; never divide by n or emit a detector hit."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or x.size < 8 or not np.all(np.isfinite(x)):
        return {"status": "ABSTAIN", "reason": "INSUFFICIENT_OR_INVALID_CALIBRATION"}
    n = int(x.size)
    y = x - float(np.mean(x))
    if bandwidth is None:
        bandwidth = max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))
    bandwidth = min(int(bandwidth), n - 1)
    gamma0 = float(np.dot(y, y) / n)
    lrv = gamma0
    for lag in range(1, bandwidth + 1):
        gamma = float(np.dot(y[lag:], y[:-lag]) / n)
        weight = 1.0 - lag / float(bandwidth + 1)
        lrv += 2.0 * weight * gamma
    if not math.isfinite(lrv) or lrv <= 0:
        return {"status": "ABSTAIN", "reason": "NON_POSITIVE_BARTLETT_LRV",
                "lrv": float(lrv), "bandwidth": bandwidth}
    return {"status": "OK", "lrv": float(lrv), "scale": math.sqrt(lrv),
            "bandwidth": bandwidth, "gamma0": gamma0, "n": n,
            "kernel": "Bartlett", "normalization": "gamma_k divided by n; no standard-error / n factor"}


def _quadratic_roots(a: float, b: float, c: float) -> list[float]:
    eps = 1e-14
    if abs(a) <= eps:
        return [] if abs(b) <= eps else [-c / b]
    disc = b * b - 4.0 * a * c
    if disc < 0:
        return []
    root = math.sqrt(max(0.0, disc))
    # Stable quadratic roots; duplicates are removed by the caller.
    q = -0.5 * (b + math.copysign(root, b if b else 1.0))
    if q == 0:
        return [-b / (2.0 * a)]
    return [q / a, c / q]


def _quadratic_max(a: float, b: float, c: float, left: float, right: float) -> tuple[float, float]:
    candidates: list[float] = []
    if math.isfinite(left):
        candidates.append(left)
    if math.isfinite(right):
        candidates.append(right)
    if a < 0:
        vertex = -b / (2.0 * a)
        if left <= vertex <= right:
            candidates.append(vertex)
    if not candidates:
        return -math.inf, 0.0
    arg = max(candidates, key=lambda z: a * z * z + b * z + c)
    return a * arg * arg + b * arg + c, arg


def _interval_probe(left: float, right: float) -> float:
    if math.isinf(left) and math.isinf(right):
        return 0.0
    if math.isinf(left):
        return right - max(1.0, abs(right) * 0.5)
    if math.isinf(right):
        return left + max(1.0, abs(left) * 0.5)
    return 0.5 * (left + right)


def focus_detector(values: Any, *, quiet_points: int = QUIET_POINTS,
                   threshold: float = FOCUS_THRESHOLD) -> dict[str, Any]:
    """Two-sided Gaussian FOCuS statistic with exact functional pruning.

    Each active piece stores the upper-envelope quadratic over a disjoint
    interval in delta. At each observation all old candidates receive the same
    quadratic increment; the zero candidate for the next onset is then overlaid
    by exact root splitting. This is functional pruning, not a fixed window scan.
    """
    x = _validate_series(values, quiet_points)
    if x.size <= quiet_points:
        return _abstain_result("INSUFFICIENT_QUIET_WINDOW",
                               observations=int(x.size), required=quiet_points + 1)
    q = x[:quiet_points]
    scale = mad_sigma(q)
    if not math.isfinite(scale) or scale <= 0:
        return {"status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                "hits": [], "events": [], "event_count": 0}
    center = float(np.median(q))
    lo, hi = -math.inf, math.inf
    # (left, right, a, b, c, estimated_change_index), q(delta)=a*delta^2+b*delta+c
    envelope: list[tuple[float, float, float, float, float, int]] = [
        (lo, hi, 0.0, 0.0, 0.0, quiet_points)
    ]
    for t in range(quiet_points, int(x.size)):
        z = float((x[t] - center) / scale)
        updated = [(l, r, a - 0.5, b + z, c, cp)
                   for l, r, a, b, c, cp in envelope]
        best_score, best_delta, best_cp = -math.inf, 0.0, quiet_points
        for l, r, a, b, c, cp in updated:
            score, delta = _quadratic_max(a, b, c, l, r)
            if score > best_score:
                best_score, best_delta, best_cp = score, delta, cp
        if best_score >= threshold and abs(best_delta) > 1e-12:
            sign = 1 if best_delta > 0 else -1
            hit = {
                "index": t, "sign": sign, "detector": "FOCuS",
                "estimated_change_index": int(best_cp), "detection_index": t,
                "score": float(best_score), "delta_hat_sigma": float(best_delta),
            }
            event = {
                "start_index": int(best_cp), "end_index": t, "sign": sign,
                "estimated_change_index": int(best_cp), "detection_index": t,
                "method": "functional_pruning_upper_envelope",
            }
            return {"status": "OK", "hits": [hit], "events": [event],
                    "event_count": 1, "metadata": {
                        "version": "p2c-focus-1.0", "threshold": threshold,
                        "delta_domain": "(-inf,+inf)",
                        "functional_pruning": True, "fixed_window_bank": False,
                        "parameter_grid": False, "quiet_points": quiet_points,
                    }}

        # Overlay the zero candidate for the next observation. Split only at
        # exact roots of each active quadratic, preserving the continuous domain.
        next_cp = t + 1
        next_envelope: list[tuple[float, float, float, float, float, int]] = []
        for l, r, a, b, c, cp in updated:
            cuts = [l]
            for root in _quadratic_roots(a, b, c):
                if l + 1e-12 < root < r - 1e-12:
                    cuts.append(root)
            cuts.append(r)
            cuts = sorted(set(cuts))
            for left, right in zip(cuts[:-1], cuts[1:]):
                mid = _interval_probe(left, right)
                if a * mid * mid + b * mid + c > 0.0:
                    next_envelope.append((left, right, a, b, c, cp))
                else:
                    next_envelope.append((left, right, 0.0, 0.0, 0.0, next_cp))
        merged: list[tuple[float, float, float, float, float, int]] = []
        for piece in next_envelope:
            if (merged and piece[5] == merged[-1][5]
                    and all(abs(piece[i] - merged[-1][i]) <= 1e-12 for i in (2, 3, 4))
                    and abs(piece[0] - merged[-1][1]) <= 1e-10):
                prev = merged[-1]
                merged[-1] = (prev[0], piece[1], prev[2], prev[3], prev[4], prev[5])
            else:
                merged.append(piece)
        envelope = merged
    return {"status": "OK", "hits": [], "events": [], "event_count": 0,
            "metadata": {"version": "p2c-focus-1.0", "threshold": threshold,
                         "delta_domain": "(-inf,+inf)",
                         "functional_pruning": True, "fixed_window_bank": False,
                         "parameter_grid": False, "quiet_points": quiet_points}}


def bocpd_detector(values: Any, *, quiet_points: int = QUIET_POINTS,
                   hazard: float = BOCPD_HAZARD, max_run: int = BOCPD_MAX_RUN,
                   short_run_max: int = BOCPD_SHORT_RUN_MAX,
                   short_mass_threshold: float = BOCPD_SHORT_MASS_THRESHOLD,
                   persistence: int = BOCPD_PERSISTENCE,
                   diagnostics: bool = False) -> dict[str, Any]:
    """Bayesian online run-length posterior with Student-t predictive density.

    The initial active state is seeded from the 40-point quiet calibration with
    run length 40. New-regime direction is compared with the MAP active prior
    regime mean, not the original quiet centre.
    """
    x = _validate_series(values, quiet_points)
    if x.size <= quiet_points:
        return _abstain_result("INSUFFICIENT_QUIET_WINDOW",
                               observations=int(x.size), required=quiet_points + 1)
    q = x[:quiet_points]
    scale = mad_sigma(q)
    if not math.isfinite(scale) or scale <= 0:
        return {"status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                "hits": [], "events": [], "event_count": 0}
    center = float(np.median(q))
    y = (x - center) / scale
    mu0, kappa0, alpha0, beta0 = 0.0, 0.25, 3.0, 2.0
    quiet_normalized = (q - center) / scale
    active_mean = float(np.mean(quiet_normalized))
    active_var = float(np.var(quiet_normalized, ddof=1))
    active_alpha = alpha0 + quiet_points / 2.0
    active_beta = beta0 + 0.5 * quiet_points * active_var
    active_kappa = kappa0 + quiet_points

    posterior = np.array([1.0], dtype=float)
    means = np.array([active_mean], dtype=float)
    kappas = np.array([active_kappa], dtype=float)
    alphas = np.array([active_alpha], dtype=float)
    betas = np.array([active_beta], dtype=float)
    run_lengths = np.array([quiet_points], dtype=int)
    log_h = math.log(float(hazard))
    log_1mh = math.log1p(-float(hazard))
    streak = 0
    candidate: dict[str, Any] | None = None
    armed = True
    stable_long_streak = 0
    hits: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    posterior_short_run_mass_max = 0.0
    posterior_diagnostic_tail: list[dict[str, Any]] = []

    for t in range(quiet_points, int(x.size)):
        # Use the posterior MAP among established (long-run) states. A fresh
        # change-point branch has a reset prior mean and must not overwrite the
        # active previous-regime reference used for direction.
        prior_long_indices = np.flatnonzero(run_lengths > int(short_run_max))
        if prior_long_indices.size:
            prior_map = int(prior_long_indices[
                int(np.argmax(posterior[prior_long_indices]))
            ])
        else:
            prior_map = int(np.argmax(posterior))
        prior_regime_mean = float(means[prior_map])
        df = 2.0 * alphas
        predictive_scale = np.sqrt(np.maximum(
            betas * (kappas + 1.0) / (alphas * kappas), 1e-12
        ))
        residual = (y[t] - means) / predictive_scale
        log_likelihood = (
            gammaln((df + 1.0) / 2.0) - gammaln(df / 2.0)
            - 0.5 * np.log(df * math.pi) - np.log(predictive_scale)
            - ((df + 1.0) / 2.0) * np.log1p((residual * residual) / df)
        )
        log_joint = np.log(np.maximum(posterior, 1e-300)) + log_likelihood

        # The reset branch is a *new* regime. Its predictive likelihood must
        # come from the reset Normal-Inverse-Gamma prior, not from the active
        # old-run predictive likelihood. Reusing log_likelihood here makes the
        # reset mass collapse to the hazard itself under constant hazard,
        # irrespective of whether the observation contradicts the old regime.
        reset_df = 2.0 * alpha0
        reset_scale = math.sqrt(
            beta0 * (kappa0 + 1.0) / (alpha0 * kappa0)
        )
        # Center the new-regime prior on the active previous regime. A fixed
        # global-zero reset prior suppresses legitimate reversals that remain
        # above/below the original quiet centre (e.g. +5σ -> +2σ).
        reset_prior_mean = prior_regime_mean
        reset_residual = (y[t] - reset_prior_mean) / reset_scale
        reset_log_likelihood = (
            gammaln((reset_df + 1.0) / 2.0) - gammaln(reset_df / 2.0)
            - 0.5 * math.log(reset_df * math.pi) - math.log(reset_scale)
            - ((reset_df + 1.0) / 2.0)
            * math.log1p((reset_residual * reset_residual) / reset_df)
        )
        change_log_mass = (
            float(logsumexp(np.log(np.maximum(posterior, 1e-300)) + log_h))
            + float(reset_log_likelihood)
        )
        growth_log_mass = log_joint + log_1mh
        new_log_posterior = np.concatenate(([change_log_mass], growth_log_mass))
        new_log_posterior -= float(logsumexp(new_log_posterior))
        posterior = np.exp(new_log_posterior)

        growth_mean = (kappas * means + y[t]) / (kappas + 1.0)
        growth_kappa = kappas + 1.0
        growth_alpha = alphas + 0.5
        growth_beta = betas + (
            kappas * (y[t] - means) ** 2 / (2.0 * (kappas + 1.0))
        )
        # The r_t=0 branch is a new regime containing x_t as its first
        # observation. Update its Normal-Inverse-Gamma sufficient statistics
        # from the reset prior with this same datum; retaining the untouched
        # prior here would silently discard the change-point observation.
        change_mean = (kappa0 * reset_prior_mean + y[t]) / (kappa0 + 1.0)
        change_kappa = kappa0 + 1.0
        change_alpha = alpha0 + 0.5
        change_beta = beta0 + (
            kappa0 * (y[t] - reset_prior_mean) ** 2 / (2.0 * (kappa0 + 1.0))
        )
        means = np.concatenate(([change_mean], growth_mean))
        kappas = np.concatenate(([change_kappa], growth_kappa))
        alphas = np.concatenate(([change_alpha], growth_alpha))
        betas = np.concatenate(([change_beta], growth_beta))
        run_lengths = np.concatenate(([0], run_lengths + 1))

        keep = run_lengths <= int(max_run)
        posterior = posterior[keep]
        means, kappas = means[keep], kappas[keep]
        alphas, betas = alphas[keep], betas[keep]
        run_lengths = run_lengths[keep]
        total = float(posterior.sum())
        if not math.isfinite(total) or total <= 0:
            return {"status": "ABSTAIN", "abstain_reason": "POSTERIOR_NORMALIZATION_FAILED",
                    "hits": [], "events": [], "event_count": 0}
        posterior /= total

        # Do not count r=0 by itself: an isolated outlier can produce a
        # one-observation reset branch. Confirmation requires posterior mass
        # on short *grown* runs (at least one observation after the reset).
        short_mask = (
            (run_lengths >= 1) & (run_lengths <= int(short_run_max))
        )
        short_mass = float(posterior[short_mask].sum())
        posterior_short_run_mass_max = max(posterior_short_run_mass_max, short_mass)
        short_mean = (
            float(np.dot(posterior[short_mask], means[short_mask]) / short_mass)
            if short_mass > 0 else float(prior_regime_mean)
        )
        regime_contrast = short_mean - prior_regime_mean
        short_mean_variance = (
            float(np.dot(
                posterior[short_mask],
                betas[short_mask] / (alphas[short_mask] * kappas[short_mask])
            ) / short_mass)
            if short_mass > 0 else math.inf
        )
        prior_mean_variance = float(
            betas[prior_map] / (alphas[prior_map] * kappas[prior_map])
        )
        contrast_z = abs(regime_contrast) / math.sqrt(
            max(short_mean_variance + prior_mean_variance, 1e-12)
        )

        # Confirmation requires posterior mass, material mean separation, and
        # separation relative to uncertainty in both regime means. A spike
        # produces a high-variance short-run posterior and fails this gate.
        if (short_mass >= float(short_mass_threshold)
                and abs(regime_contrast) >= float(BOCPD_MIN_REGIME_SHIFT)
                and contrast_z >= float(BOCPD_MIN_CONTRAST_Z)):
            if streak == 0:
                short_indices = np.flatnonzero(short_mask)
                short_map = int(short_indices[int(np.argmax(posterior[short_mask]))])
                estimate = max(quiet_points, t - int(run_lengths[short_map]))
                sign = 1 if regime_contrast > 0 else -1
                candidate = {"estimated_change_index": estimate, "sign": sign,
                             "prior_regime_mean": prior_regime_mean,
                             "posterior_new_regime_mean": short_mean,
                             "regime_contrast": regime_contrast,
                             "posterior_contrast_z": contrast_z}
            streak += 1
        else:
            streak = 0
            candidate = None

        long_mass = float(posterior[run_lengths > int(short_run_max)].sum())
        if diagnostics:
            posterior_diagnostic_tail.append({
                "index": int(t),
                "short_run_mass": float(short_mass),
                "long_run_mass": float(long_mass),
                "prior_regime_mean": float(prior_regime_mean),
                "posterior_new_regime_mean": float(short_mean),
                "regime_contrast": float(regime_contrast),
                "posterior_contrast_z": float(contrast_z),
                "streak": int(streak),
                "armed": bool(armed),
                "map_run_length": int(run_lengths[int(np.argmax(posterior))]),
            })
            if len(posterior_diagnostic_tail) > 128:
                posterior_diagnostic_tail.pop(0)
        if not armed:
            stable_long_streak = (
                stable_long_streak + 1
                if long_mass >= float(BOCPD_REARM_LONG_MASS) else 0
            )
            if stable_long_streak >= int(BOCPD_REARM_PERSISTENCE):
                armed = True
                stable_long_streak = 0

        if streak >= int(persistence) and armed and candidate is not None:
            estimate = int(candidate["estimated_change_index"])
            sign = int(candidate["sign"])
            hits.append({
                "index": t, "sign": sign, "detector": "BOCPD",
                "estimated_change_index": estimate, "detection_index": t,
                "posterior_short_run_mass": short_mass,
                "prior_regime_mean": float(candidate["prior_regime_mean"]),
                "posterior_new_regime_mean": float(candidate["posterior_new_regime_mean"]),
                "regime_contrast": float(candidate["regime_contrast"]),
                "posterior_contrast_z": float(candidate["posterior_contrast_z"]),
                "posterior_map_run_length": int(run_lengths[int(np.argmax(posterior))]),
            })
            events.append({
                "start_index": estimate, "end_index": t, "sign": sign,
                "estimated_change_index": estimate, "detection_index": t,
                "method": "posterior_short_run_length_mass",
            })
            # A confirmed transition closes the previous active regime.
            # Re-seed the online posterior from the newly confirmed segment so
            # the next transition is measured against this active regime rather
            # than a mixture dominated by much older run-length hypotheses.
            segment = y[estimate:t + 1]
            segment_n = int(segment.size)
            segment_mean = float(np.mean(segment))
            segment_sum = float(np.sum(segment))
            segment_ss = float(np.sum((segment - segment_mean) ** 2))
            new_kappa = kappa0 + segment_n
            new_mean = (kappa0 * mu0 + segment_sum) / new_kappa
            new_alpha = alpha0 + segment_n / 2.0
            new_beta = (
                beta0 + 0.5 * segment_ss
                + (kappa0 * segment_n * (segment_mean - mu0) ** 2)
                  / (2.0 * new_kappa)
            )
            posterior = np.array([1.0], dtype=float)
            means = np.array([new_mean], dtype=float)
            kappas = np.array([new_kappa], dtype=float)
            alphas = np.array([new_alpha], dtype=float)
            betas = np.array([new_beta], dtype=float)
            run_lengths = np.array([segment_n], dtype=int)
            armed = True
            stable_long_streak = 0
            streak = 0
            candidate = None

    return {"status": "OK", "hits": hits, "events": events,
            "event_count": len(events) or len(hits),
            "metadata": {"version": "p2c-bocpd-1.0", "hazard": hazard,
                         "max_run_length": max_run, "short_run_max": short_run_max,
                         "short_run_mass_threshold": short_mass_threshold,
                         "short_run_mass_definition": "posterior P(1<=run_length<=short_run_max); excludes r=0",
                         "posterior_short_run_mass_max": float(posterior_short_run_mass_max),
                         "min_regime_shift": BOCPD_MIN_REGIME_SHIFT,
                         "min_contrast_z": BOCPD_MIN_CONTRAST_Z,
                         "rearm_long_mass": BOCPD_REARM_LONG_MASS,
                         "rearm_persistence": BOCPD_REARM_PERSISTENCE,
                         "confirmed_regime_reseed": "NIG posterior reinitialized from confirmed segment statistics",
                         "persistence": persistence,
                         "predictive": "Normal-Inverse-Gamma Student-t",
                         "reset_prior_center": "active previous regime posterior mean",
                         "direction_reference": "MAP prior-regime predictive mean"}}


def post_quiet_huber_detector(values: Any, *, scale_mode: str = "mad",
                              quiet_points: int = QUIET_POINTS,
                              threshold: float = HUBER_THRESHOLD,
                              k: float = HUBER_K, huber_c: float = HUBER_C,
                              max_events: int = HUBER_MAX_EVENTS) -> dict[str, Any]:
    """Two-sided sequential Huber score with MAD or Bartlett-LRV scale."""
    x = _validate_series(values, quiet_points)
    if x.size <= quiet_points:
        return _abstain_result("INSUFFICIENT_QUIET_WINDOW",
                               observations=int(x.size), required=quiet_points + 1)
    quiet = x[:quiet_points]
    center = float(np.median(quiet))
    mad = mad_sigma(quiet)
    if not math.isfinite(mad) or mad <= 0:
        return {"status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                "hits": [], "events": [], "event_count": 0}
    if scale_mode == "mad":
        scale = mad
        scale_metadata: dict[str, Any] = {"estimator": "MAD", "scale": scale}
    elif scale_mode == "bartlett":
        estimate = bartlett_lrv_scale(quiet)
        if estimate.get("status") != "OK":
            return {"status": "ABSTAIN", "abstain_reason": estimate.get("reason"),
                    "hits": [], "events": [], "event_count": 0,
                    "scale_metadata": estimate}
        scale = float(estimate["scale"])
        scale_metadata = {"estimator": "Bartlett-LRV", **estimate}
    else:
        raise ValueError("scale_mode_must_be_mad_or_bartlett")
    if not math.isfinite(scale) or scale <= 0:
        return {"status": "ABSTAIN", "abstain_reason": "INVALID_SCALE",
                "hits": [], "events": [], "event_count": 0}

    reference = center
    positive = negative = 0.0
    positive_start: int | None = None
    negative_start: int | None = None
    hits: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for t in range(quiet_points, int(x.size)):
        residual = float((x[t] - reference) / scale)
        psi = float(np.clip(residual, -huber_c, huber_c))
        old_positive, old_negative = positive, negative
        positive = max(0.0, positive + psi - k)
        negative = max(0.0, negative - psi - k)
        if positive == 0.0:
            positive_start = None
        elif old_positive == 0.0:
            positive_start = t
        if negative == 0.0:
            negative_start = None
        elif old_negative == 0.0:
            negative_start = t

        sign = 0
        event_start: int | None = None
        if positive >= threshold:
            sign, event_start = 1, positive_start
        elif negative >= threshold:
            sign, event_start = -1, negative_start
        if sign:
            start = int(event_start if event_start is not None else t)
            hit = {
                "index": t, "sign": sign,
                "detector": f"Post-Quiet Huber + {scale_mode.upper()}",
                "estimated_change_index": start, "detection_index": t,
                "huber_score": float(positive if sign > 0 else negative),
                "reference_mean_before_detection": float(reference),
            }
            hits.append(hit)
            events.append({
                "start_index": start, "end_index": t, "sign": sign,
                "estimated_change_index": start, "detection_index": t,
                "method": "two_sided_huber_cusum",
            })
            # Rebase only after the detection is emitted. This allows later
            # reversals/changes to be detected without re-alerting on one regime.
            reference = float(np.median(x[max(quiet_points, t - 7):t + 1]))
            positive = negative = 0.0
            positive_start = negative_start = None
            if len(hits) >= int(max_events):
                break

    return {"status": "OK", "hits": hits, "events": events,
            "event_count": len(events),
            "metadata": {"version": "p2c-huber-1.0", "scale_mode": scale_mode,
                         "scale_metadata": scale_metadata, "huber_c": huber_c,
                         "k": k, "threshold": threshold, "quiet_points": quiet_points,
                         "directional_tracks": "positive_and_negative"}}


def _normalize_online_result(raw: dict[str, Any], size: int, arm: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("hits"), list):
        raise TypeError(f"{arm}_must_return_hits")
    hits: list[dict[str, Any]] = []
    for source in raw["hits"]:
        index = source.get("index", source.get("detection_index"))
        sign = source.get("sign")
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise ValueError(f"{arm}_detection_index_must_be_integer")
        if not 0 <= int(index) < size:
            raise ValueError(f"{arm}_detection_index_out_of_range")
        if isinstance(sign, bool) or int(sign) not in (-1, 1):
            raise ValueError(f"{arm}_sign_must_be_minus_or_plus_one")
        hit = dict(source)
        hit.update({"index": int(index), "sign": int(sign),
                    "detector": str(source.get("detector", arm))})
        hits.append(hit)
    hits.sort(key=lambda z: (z["index"], z["sign"], z["detector"]))
    events = raw.get("events", [])
    if not isinstance(events, list):
        raise TypeError(f"{arm}_events_must_be_list")
    for event in events:
        start = int(event.get("start_index", -1))
        end = int(event.get("end_index", start))
        sign = int(event.get("sign", 0))
        if not 0 <= start < size or not 0 <= end < size or end < start or sign not in (-1, 1):
            raise ValueError(f"{arm}_event_contract_invalid")
    return {**raw, "hits": hits, "events": events,
            "event_count": len(events) or len(hits)}


def _audit_runner(runner: Callable[[np.ndarray], dict[str, Any]],
                  x: np.ndarray, arm: str) -> dict[str, Any]:
    full = _normalize_online_result(runner(x.copy()), x.size, arm)
    if full.get("status") == "ABSTAIN":
        return {**full, "causal_audit_violations": 0,
                "causal_audit_unverifiable_prefixes": 0}
    violations = 0
    for hit in full["hits"]:
        t = int(hit["index"])
        prefix = _normalize_online_result(runner(x[:t + 1].copy()), t + 1, arm)
        matched = any(
            int(candidate["index"]) == t and int(candidate["sign"]) == int(hit["sign"])
            and int(candidate.get("estimated_change_index", candidate["index"]))
                == int(hit.get("estimated_change_index", hit["index"]))
            for candidate in prefix["hits"]
        )
        if not matched:
            violations += 1
    for event in full["events"]:
        t = int(event["end_index"])
        prefix = _normalize_online_result(runner(x[:t + 1].copy()), t + 1, arm)
        if not any(
            int(candidate["end_index"]) == t
            and int(candidate["start_index"]) == int(event["start_index"])
            and int(candidate["sign"]) == int(event["sign"])
            for candidate in prefix["events"]
        ):
            violations += 1

    cut = max(QUIET_POINTS + 1, int(x.size * 0.65))
    if cut < x.size:
        altered = x.copy()
        altered[cut:] = altered[cut:][::-1] * -1.713 + 0.271
        changed = _normalize_online_result(runner(altered), x.size, arm)
        token = lambda rows: [
            (int(item["index"]), int(item["sign"]),
             int(item.get("estimated_change_index", item["index"])))
            for item in rows if int(item["index"]) < cut
        ]
        if token(full["hits"]) != token(changed["hits"]):
            violations += 1
        event_token = lambda rows: [
            (int(item["start_index"]), int(item["end_index"]), int(item["sign"]))
            for item in rows if int(item["end_index"]) < cut
        ]
        if event_token(full["events"]) != event_token(changed["events"]):
            violations += 1
    return {**full, "causal_audit_violations": violations,
            "causal_audit_unverifiable_prefixes": 0}


def run_p2c_all(values: Any, *, causal_audit: bool = False,
                quiet_points: int = QUIET_POINTS) -> dict[str, Any]:
    """Run the two frozen A baselines plus only the online P2-C entrants."""
    x = _validate_series(values, quiet_points)
    if x.size <= quiet_points:
        return {
            arm: _abstain_result("INSUFFICIENT_QUIET_WINDOW",
                                 observations=int(x.size), required=quiet_points + 1)
            for arm in P2C_VARIANTS
        }
    quiet_scale = mad_sigma(x[:quiet_points])
    if not math.isfinite(quiet_scale) or quiet_scale <= 0:
        return {
            arm: {"status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                  "hits": [], "events": [], "event_count": 0,
                  "causal_audit_violations": 0 if causal_audit else None,
                  "causal_audit_unverifiable_prefixes": 0 if causal_audit else None}
            for arm in P2C_VARIANTS
        }

    from structural_engine.isolated_break_detector_v1 import BreakDetectorV1

    output: dict[str, Any] = {}
    for arm, mode in (("A_FAST", "fast"), ("A_CONSENSUS", "consensus")):
        result = BreakDetectorV1(mode=mode).analyze(x)
        hits: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        violations = 0
        unverifiable = 0
        details = []
        for item in result.get("structural_breaks", []):
            detection = item.get("detection_time")
            if detection is None:
                continue
            t = int(detection)
            sign = int(item.get("direction", 0))
            if not 0 <= t < x.size or sign not in (-1, 1):
                continue
            onset = item.get("onset_time", item.get("start_index", t))
            onset = int(onset)
            hits.append({"index": t, "sign": sign, "detector": arm,
                         "estimated_change_index": onset, "detection_index": t})
            events.append({"start_index": onset, "end_index": t, "sign": sign,
                           "estimated_change_index": onset, "detection_index": t})
            if causal_audit:
                prefix_length = t + 1
                minimum = int(BreakDetectorV1.MIN_SERIES_LENGTH)
                if prefix_length < minimum:
                    unverifiable += 1
                    details.append({"time": t, "prefix_length": prefix_length,
                                    "minimum_supported_prefix": minimum,
                                    "status": "UNVERIFIABLE_BELOW_MIN_SERIES_LENGTH"})
                    continue
                prefix = BreakDetectorV1(mode=mode).analyze(x[:prefix_length])
                matched = any(
                    int(candidate.get("detection_time", -1)) == t
                    and int(candidate.get("direction", 0)) == sign
                    for candidate in prefix.get("structural_breaks", [])
                )
                if not matched:
                    violations += 1
                if mode == "consensus" and prefix_length < int(BreakDetectorV1.MIN_FULL_CONSENSUS_LENGTH):
                    details.append({"time": t, "prefix_length": prefix_length,
                                    "minimum_supported_prefix": minimum,
                                    "status": "MATCH" if matched else "MISMATCH"})
        baseline = {"status": "OK", "hits": hits, "events": events,
                    "event_count": len(events),
                    "causal_audit_violations": violations if causal_audit else None,
                    "causal_audit_unverifiable_prefixes": unverifiable if causal_audit else None}
        if arm == "A_CONSENSUS":
            baseline["causal_audit_details"] = details if causal_audit else None
        output[arm] = baseline

    runners = {
        "FOCUS": focus_detector,
        "BOCPD": bocpd_detector,
        "POST_QUIET_HUBER_MAD": lambda v: post_quiet_huber_detector(v, scale_mode="mad"),
        "POST_QUIET_HUBER_BARTLETT": lambda v: post_quiet_huber_detector(v, scale_mode="bartlett"),
    }
    for arm, runner in runners.items():
        output[arm] = _audit_runner(runner, x, arm) if causal_audit else _normalize_online_result(runner(x.copy()), x.size, arm)
    return output


# ---- Separate retrospective R-FPOP / robust segmentation track ----

_VENDOR = Path(__file__).resolve().parent / "vendor" / "robseg_lgpl"
_LIB_HANDLE: ctypes.CDLL | None = None


def _load_robseg_library() -> ctypes.CDLL:
    global _LIB_HANDLE
    if _LIB_HANDLE is not None:
        return _LIB_HANDLE
    compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise RuntimeError("R_FPOP_CXX_COMPILER_UNAVAILABLE")
    srcs = [
        _VENDOR / "fp_Rob_fpop.cc",
        _VENDOR / "fp_CFunctPart.cpp",
        _VENDOR / "fp_liste.cpp",
        _VENDOR / "chaos_robseg_wrapper.cpp",
    ]
    if not all(path.is_file() for path in srcs):
        raise RuntimeError("R_FPOP_VENDOR_SOURCE_MISSING")
    digest = hashlib.sha256()
    for path in srcs:
        digest.update(path.read_bytes())
    key = digest.hexdigest()[:20]
    output_dir = Path(tempfile.gettempdir()) / f"chaos-robseg-{key}"
    output_dir.mkdir(parents=True, exist_ok=True)
    library_path = output_dir / "libchaos_robseg.so"
    if not library_path.exists():
        command = [
            compiler, "-O3", "-std=c++11", "-fPIC", "-shared",
            "-I", str(_VENDOR), *[str(path) for path in srcs],
            "-o", str(library_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"R_FPOP_COMPILE_FAILED:{completed.stderr[-3000:]}")
    library = ctypes.CDLL(str(library_path))
    function = library.chaos_rob_fpop_huber
    double_ptr = ctypes.POINTER(ctypes.c_double)
    int_ptr = ctypes.POINTER(ctypes.c_int)
    function.argtypes = [double_ptr, ctypes.c_int, ctypes.c_double,
                         ctypes.c_double, int_ptr, double_ptr, double_ptr]
    function.restype = None
    _LIB_HANDLE = library
    return library


def r_fpop_segment(values: Any, *, quiet_points: int = QUIET_POINTS,
                   huber_k: float = R_FPOP_HUBER_K,
                   penalty_multiplier: float = R_FPOP_PENALTY_MULTIPLIER) -> dict[str, Any]:
    """Run pinned robust FPOP with Huber loss on the entire prefix.

    This is deliberately a retrospective segmentation result, not an online
    detector. Each final estimated breakpoint carries a separate detection
    index: the earliest prefix whose optimal last-segment origin equals it.
    """
    x = _validate_series(values, quiet_points)
    if x.size <= quiet_points:
        return {"status": "ABSTAIN", "abstain_reason": "INSUFFICIENT_QUIET_WINDOW",
                "breakpoints": [], "metadata": {"loss": "Huber", "observations": int(x.size)}}
    scale = mad_sigma(x[:quiet_points])
    if not math.isfinite(scale) or scale <= 0:
        return {"status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                "breakpoints": [], "metadata": {"loss": "Huber"}}
    normalized = np.ascontiguousarray((x - float(np.median(x[:quiet_points]))) / scale,
                                      dtype=np.float64)
    n = int(normalized.size)
    if n < quiet_points + 8:
        return {"status": "ABSTAIN", "abstain_reason": "INSUFFICIENT_SEGMENT_LENGTH",
                "breakpoints": [], "metadata": {"loss": "Huber"}}
    library = _load_robseg_library()
    origin = np.empty(n, dtype=np.int32)
    cost = np.empty(n, dtype=np.float64)
    mean = np.empty(n, dtype=np.float64)
    pointer = lambda arr, typ: arr.ctypes.data_as(ctypes.POINTER(typ))
    penalty = float(penalty_multiplier * math.log(max(n, 2)))
    library.chaos_rob_fpop_huber(
        pointer(normalized, ctypes.c_double), n, penalty, float(huber_k),
        pointer(origin, ctypes.c_int), pointer(cost, ctypes.c_double),
        pointer(mean, ctypes.c_double),
    )
    # The upstream path array stores the optimal previous segment origin for
    # every prefix. Reconstruct the final optimal partition by backtracking.
    starts: list[int] = []
    cursor = n - 1
    seen: set[int] = set()
    while cursor >= 0:
        if cursor in seen:
            raise RuntimeError("R_FPOP_PATH_CYCLE")
        seen.add(cursor)
        start = int(origin[cursor])
        if start <= 0:
            break
        if start >= cursor:
            raise RuntimeError(f"R_FPOP_PATH_ORIGIN_INVALID:{start}:{cursor}")
        starts.append(start)
        cursor = start - 1
    starts = sorted(set(starts))
    def prefix_contains_break(prefix_end: int, wanted: int) -> bool:
        cursor = int(prefix_end)
        visited: set[int] = set()
        while cursor > 0:
            if cursor in visited:
                raise RuntimeError("R_FPOP_PREFIX_PATH_CYCLE")
            visited.add(cursor)
            previous = int(origin[cursor])
            if previous <= 0:
                return False
            if previous == int(wanted):
                return True
            if previous > cursor:
                raise RuntimeError(f"R_FPOP_PREFIX_ORIGIN_INVALID:{previous}:{cursor}")
            cursor = previous - 1
        return False

    breakpoints = []
    for cp in starts:
        detection = next(
            (prefix_end for prefix_end in range(int(cp), n)
             if prefix_contains_break(prefix_end, int(cp))),
            None,
        )
        breakpoints.append({
            "estimated_change_index": int(cp),
            "detection_index": int(detection) if detection is not None else None,
            "first_supported_in_prefix": detection is not None,
            "retained_in_final_segmentation": True,
        })
    return {
        "status": "OK", "breakpoints": breakpoints,
        "metadata": {
            "implementation": "pinned upstream robseg::rob_fpop",
            "upstream_commit": "ce49c26aa5b5eee84a835e69cbb7ca572f669792",
            "loss": "Huber", "huber_k": float(huber_k),
            "penalty": penalty, "penalty_multiplier": float(penalty_multiplier),
            "quiet_scale": float(scale), "n": n,
            "track": "retrospective_segmentation_not_online_ranked",
            "origin_trace_sha256": hashlib.sha256(
                np.asarray(origin, dtype="<i4").tobytes()
            ).hexdigest(),
        },
    }


def r_fpop_runtime_probe(n: int = 539) -> dict[str, Any]:
    """Compile once and time a worst-case Huber segmentation probe."""
    rng = np.random.default_rng(20261125)
    x = rng.normal(0.0, 1.0, n)
    x[n // 2:] += 3.0
    started = __import__("time").perf_counter()
    result = r_fpop_segment(x)
    elapsed = __import__("time").perf_counter() - started
    return {"status": result["status"], "elapsed_seconds": elapsed,
            "breakpoints": result.get("breakpoints", []),
            "metadata": {k: v for k, v in result.get("metadata", {}).items()
                         if k != "origin_trace"}}

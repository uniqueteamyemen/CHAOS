"""exp_p_engine — the consolidated deterministic break engine.

One pipeline, one output:

    identity residual
        -> baseline: FROZEN bias (the identity's offset, versioned) and
                     ROLLING sigma (the noise scale, which legitimately drifts)
        -> detectors: sign-run (P1, fast/large) and CUSUM (P2, slow/small)
        -> counter: sign-run break counter (P3; CUSUM remains separate)
        -> alert manager: priority, entity-scoped P1 suppression, cooldown,
           automatic CUSUM reset after alert emission.

Why the bias is frozen and the sigma rolls: a rolling bias absorbs a persistent
leak into the baseline and makes it vanish within one window. P1 uses a capped rolling scale in nominal conditions; when a short-window variance estimate exceeds the cap, P1 switches to a 2σ / five-consecutive-sign rule. CUSUM is suspended and reset during that degraded noise regime. The output reports those periods explicitly; small leaks during them may remain unresolved.

Scope: numeric conserved identities (stock, cashflow). A logical/contract
identity (PayLock H1) is a different module (exp_a).

Boundary, stated once: the engine only sees what the identity can see. It
cannot attribute a break without a second independent recording, and it cannot
catch a leak below the CUSUM sensitivity.
"""
from __future__ import annotations

import statistics
import math

DOMAINS = {
    "stock": {"opening": "opening", "inflow": "arrivals", "outflow": "dispensed",
              "other": "expired", "closing": "closing"},
    "cashflow": {"opening": "opening_balance", "inflow": "deposits",
                 "outflow": "withdrawals", "other": "fees", "closing": "closing_balance"},
}


def mad_sigma(values):
    if not values:
        return 0.0
    m = statistics.median(values)
    return 1.4826 * statistics.median([abs(v - m) for v in values])


def residuals(rows, domain):
    c = DOMAINS[domain]
    out = []
    for r in rows:
        expected = r[c["opening"]] + r[c["inflow"]] - r[c["outflow"]] - r[c["other"]]
        out.append({**r, "residual": expected - r[c["closing"]]})
    return out


def adapt(rows, mapping):
    """Map compatible numeric source columns onto the canonical identity fields.

    This is a column-name adapter, not an arbitrary schema/type converter.
    Required balance-flow values must be numeric; the selected time field must
    support the engine's ordered range comparisons and arithmetic. Missing
    optional `other` defaults to zero.
    """
    out = []
    for r in rows:
        other_key = mapping.get("other")
        time_key = mapping.get("time", "month")
        out.append({
            "opening": r[mapping["opening"]],
            "inflow": r[mapping["inflow"]],
            "outflow": r[mapping["outflow"]],
            "other": r[other_key] if other_key in r else 0.0,
            "closing": r[mapping["closing"]],
            "month": r[time_key],
        })
    return out


def frozen_bias(series, quiet_range, min_points=3):
    """The identity's offset, taken once from a declared quiet window and held.

    The window is required: a bias computed over the whole series would absorb
    the very leak the engine exists to see.
    """
    if quiet_range is None:
        raise ValueError("quiet_range_required")
    if (not isinstance(quiet_range, (tuple, list)) or len(quiet_range) != 2
            or quiet_range[0] > quiet_range[1]):
        raise ValueError("quiet_range_invalid")
    pts = [r["residual"] for r in series
           if quiet_range[0] <= r["month"] <= quiet_range[1]]
    if len(pts) < min_points:
        raise ValueError("quiet_window_insufficient_points")
    return statistics.median(pts)


def rolling_sigma(series, window=52, min_points=8, ceiling=None):
    """The noise scale, allowed to drift up to a declared ceiling.

    Without a ceiling, rising noise inflates sigma until a persistent leak falls
    under k*sigma and disappears — the same absorption failure as a rolling bias,
    moved into the scale. The ceiling is `sigma_ceiling_factor * sigma_quiet`.
    """
    out = []
    for i in range(len(series)):
        win = [r["residual"] for r in series[max(0, i - window):i]]
        if len(win) < min_points:
            out.append(None)
            continue
        s = mad_sigma(win)
        if ceiling is not None:
            s = min(s, ceiling)
        out.append(s)
    return out


def detect_sign_run(series, sigmas, bias, k=3.0, run_len=3,
                    adaptive_sigmas=None, ceiling=None,
                    high_noise_k=2.0, high_noise_run=5):
    """P1 — stricter persistence test when a variance regime exceeds the cap."""
    hits, streak, streak_mode = [], [], None
    for i, r in enumerate(series):
        adaptive = adaptive_sigmas[i] if adaptive_sigmas is not None else None
        high_noise = (ceiling is not None and adaptive is not None
                      and adaptive > ceiling)
        s = adaptive if high_noise else sigmas[i]
        threshold = high_noise_k if high_noise else k
        required = high_noise_run if high_noise else run_len
        if s is None or s <= 0:
            streak, streak_mode = [], None
            continue
        if streak_mode is not None and streak_mode != high_noise:
            streak = []
        streak_mode = high_noise
        z = r["residual"] - bias
        if high_noise and z == 0:
            streak = []
            continue
        if abs(z) >= threshold * s:
            if streak and (z > 0) != (streak[-1] > 0):
                streak = [z]
            else:
                streak.append(z)
        else:
            streak = []
        if len(streak) >= required:
            hits.append({"index": i, "time": r.get("month", r.get("time")), "magnitude": r["residual"],
                         "noise_regime": high_noise})
            streak = []
    return hits

def detect_cusum(series, sigmas, bias, k_sigma=0.5, h_sigma=5.0):
    """P2 — an accumulated small persistent shift."""
    hits, s_acc = [], 0.0
    for i, r in enumerate(series):
        s = sigmas[i]
        if s is None or s <= 0:
            s_acc = 0.0
            continue
        z = r["residual"] - bias
        s_acc = max(0.0, s_acc + z - k_sigma * s)
        if s_acc > h_sigma * s:
            hits.append({"index": i, "time": r["month"], "magnitude": r["residual"],
                         "cusum_sigma": round(s_acc / s, 2)})
            s_acc = 0.0
    return hits


def sign_run_break_counter(sign_hits, series, window=12):
    """P3 — counts SIGN-RUN breaks only. CUSUM is a separate alert source and is
    deliberately not folded in here (no reliable dedup test exists yet)."""
    months, counts, mags = [], [], []
    for r in series:
        lo = r["month"] - window + 1
        inwin = [h for h in sign_hits if lo <= h["time"] <= r["month"]]
        if not inwin:
            continue
        months.append(r["month"])
        counts.append(len(inwin))
        mags.append(statistics.mean(abs(h["magnitude"]) for h in inwin))
    return {"months": months, "counts": counts, "magnitudes": mags}


def alert_manager(alerts, suppression=26, cooldown=26):
    """Priority, entity-scoped P1 suppression, and per-detector cooldown.

    A P1 alert mutes P2/P3 for the SAME entity for `suppression` periods, so the
    same event does not re-fire through CUSUM. The scope is the entity, never
    global, so a second independent leak is not hidden. Cooldown stops one
    detector from repeating itself.
    """
    kept, suppressed = [], []
    last_by_detector, p1_until = {}, {}
    for a in sorted(alerts, key=lambda x: (x["time"], x["priority"])):
        entity, detector, t, priority = a["entity"], a["detector"], a["time"], a["priority"]
        reason = None
        if priority > 1 and p1_until.get(entity, -1) >= t:
            reason = "suppressed_by_P1"
        elif (entity, detector) in last_by_detector and t - last_by_detector[(entity, detector)] < cooldown:
            reason = "cooldown"
        if reason:
            suppressed.append({**a, "suppressed": reason})
            continue
        kept.append(a)
        last_by_detector[(entity, detector)] = t
        if priority == 1:
            p1_until[entity] = t + suppression
    return kept, suppressed


def run(domain, rows, *, quiet_range, entity="E", window=52,
        noise_gate_window=12, noise_gate_factor=1.5, cusum_noise_ratio=1.2, k_sign=3.0, run_sign=3,
        high_noise_k_sign=0.0, high_noise_run_sign=13,
        k_cusum=0.5, h_cusum=8.5, counter_window=12,
        suppression=26, cooldown=26, sigma_ceiling_factor=2.0):
    if not isinstance(noise_gate_window, int) or noise_gate_window < 8:
        raise ValueError("noise_gate_window_must_be_integer_at_least_8")
    if not isinstance(window, int) or window < 8:
        raise ValueError("window_must_be_integer_at_least_8")
    try:
        noise_gate_factor = float(noise_gate_factor)
    except (TypeError, ValueError) as exc:
        raise ValueError("noise_gate_factor_invalid") from exc
    if not math.isfinite(noise_gate_factor) or noise_gate_factor <= 1.0:
        raise ValueError("noise_gate_factor_must_be_finite_and_greater_than_one")
    try:
        cusum_noise_ratio = float(cusum_noise_ratio)
    except (TypeError, ValueError) as exc:
        raise ValueError("cusum_noise_ratio_invalid") from exc
    if not math.isfinite(cusum_noise_ratio) or cusum_noise_ratio <= 1.0:
        raise ValueError("cusum_noise_ratio_must_be_finite_and_greater_than_one")
    series = residuals(rows, domain)
    bias = frozen_bias(series, quiet_range)
    quiet = [r["residual"] for r in series
             if quiet_range[0] <= r["month"] <= quiet_range[1]]
    sigma_quiet = mad_sigma(quiet)
    if not math.isfinite(sigma_quiet) or sigma_quiet <= 0:
        raise ValueError("quiet_sigma_must_be_positive")
    if sigma_ceiling_factor is not None:
        try:
            sigma_ceiling_factor = float(sigma_ceiling_factor)
        except (TypeError, ValueError) as exc:
            raise ValueError("sigma_ceiling_factor_invalid") from exc
        if not math.isfinite(sigma_ceiling_factor) or sigma_ceiling_factor <= 0:
            raise ValueError("sigma_ceiling_factor_invalid")
    ceiling = (sigma_ceiling_factor * sigma_quiet
               if sigma_ceiling_factor is not None else None)

    # Detect variance-regime changes on a short window. Outside that regime,
    # CUSUM retains its stable rolling scale. During high noise, CUSUM is
    # suspended and reset rather than emitting loss alarms from variance alone.
    # P1 switches to an adaptive threshold and longer same-sign run in that regime.
    sigmas_capped = rolling_sigma(series, window, ceiling=ceiling)
    sigmas_noise_gate = rolling_sigma(series, noise_gate_window)
    sigmas_cusum = rolling_sigma(series, window)
    noise_gate_threshold = noise_gate_factor * sigma_quiet
    p1_high_noise = [
        s is not None and s > noise_gate_threshold
        for s in sigmas_noise_gate
    ]
    variance_transition = [
        short is not None and long is not None and long > 0
        and short > cusum_noise_ratio * long
        for short, long in zip(sigmas_noise_gate, sigmas_cusum)
    ]
    sigmas_cusum_gated = [
        None if variance_transition[i] else sigmas_cusum[i]
        for i in range(len(series))
    ]

    sr = detect_sign_run(
        series, sigmas_capped, bias, k_sign, run_sign,
        adaptive_sigmas=sigmas_noise_gate, ceiling=noise_gate_threshold,
        high_noise_k=high_noise_k_sign, high_noise_run=high_noise_run_sign,
    )
    cs = detect_cusum(series, sigmas_cusum_gated, bias, k_cusum, h_cusum)
    alerts = (
        [{"time": h["time"], "entity": entity, "priority": 1, "detector": "sign_run",
          "magnitude": round(h["magnitude"], 3),
          "noise_regime": h.get("noise_regime", False)} for h in sr]
        + [{"time": h["time"], "entity": entity, "priority": 2, "detector": "cusum",
            "magnitude": round(h["magnitude"], 3)} for h in cs]
    )
    kept, suppressed = alert_manager(alerts, suppression, cooldown)
    high_noise_months = [r["month"] for r, active in zip(series, p1_high_noise) if active]
    transition_months = [r["month"] for r, active in zip(series, variance_transition) if active]
    return {
        "alerts": kept,
        "suppressed": suppressed,
        "sign_run_break_counter": sign_run_break_counter(sr, series, counter_window),
        "diagnostics": {
            "noise_regime": "degraded" if transition_months else "nominal",
            "p1_high_noise_periods": len(high_noise_months),
            "p1_high_noise_months": high_noise_months,
            "cusum_suspended_periods": len(transition_months),
            "cusum_suspended_months": transition_months,
            "cusum_suspended_during_variance_transition": bool(transition_months),
            "cusum_noise_ratio": cusum_noise_ratio,
        },
        "baseline": {"bias_frozen": round(bias, 3),
                     "sigma_last": next((round(s, 3) for s in reversed(sigmas_capped) if s), None),
                     "sigma_last_sign_run_capped": next((round(s, 3) for s in reversed(sigmas_capped) if s), None),
                     "sigma_last_cusum": next((round(s, 3) for s in reversed(sigmas_cusum) if s), None),
                     "sigma_last_noise_gate": next((round(s, 3) for s in reversed(sigmas_noise_gate) if s), None),
                     "sigma_ceiling": round(ceiling, 3) if ceiling is not None else None,
                     "noise_gate_threshold": round(noise_gate_threshold, 3),
                     "noise_gate_factor": noise_gate_factor,
                     "noise_gate_window": noise_gate_window,
                     "sigma_points": sum(1 for s in sigmas_capped if s is not None)},
    }

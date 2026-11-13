"""exp_p_engine — the consolidated deterministic break engine.

One pipeline, one output:

    identity residual
        -> baseline: FROZEN bias (the identity's offset, versioned) and
                     ROLLING sigma (the noise scale, which legitimately drifts)
        -> detectors: sign-run (P1, fast/large) and CUSUM (P2, slow/small)
        -> counter: break count C and mean magnitude M per trailing window (P3)
        -> alert manager: priority, entity-scoped P1 suppression, cooldown,
           operator-confirmed reset.

Why the bias is frozen and the sigma rolls: a rolling bias absorbs a persistent
leak into the baseline and makes it vanish within one window. The noise scale,
by contrast, does drift, so it is allowed to roll. Rolling both would silently
delete the very signal the engine exists to see.

Scope: numeric conserved identities (stock, cashflow). A logical/contract
identity (PayLock H1) is a different module (exp_a).

Boundary, stated once: the engine only sees what the identity can see. It
cannot attribute a break without a second independent recording, and it cannot
catch a leak below the CUSUM sensitivity.
"""
from __future__ import annotations

import statistics

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


def frozen_bias(series, quiet_range):
    """The identity's offset, taken once from a declared quiet window and held."""
    pts = [r["residual"] for r in series
           if quiet_range is None or quiet_range[0] <= r["month"] <= quiet_range[1]]
    return statistics.median(pts) if pts else 0.0


def rolling_sigma(series, window=52, min_points=8):
    """The noise scale, allowed to drift; None until enough history exists."""
    out = []
    for i in range(len(series)):
        win = [r["residual"] for r in series[max(0, i - window):i]]
        out.append(mad_sigma(win) if len(win) >= min_points else None)
    return out


def detect_sign_run(series, sigmas, bias, k=3.0, run_len=3):
    """P1 — a run of same-sign centred residuals beyond k sigma."""
    hits, streak = [], []
    for i, r in enumerate(series):
        s = sigmas[i]
        if s is None or s <= 0:
            streak = []
            continue
        z = r["residual"] - bias
        if abs(z) >= k * s:
            if streak and (z > 0) != (streak[-1] > 0):
                streak = [z]
            else:
                streak.append(z)
        else:
            streak = []
        if len(streak) >= run_len:
            hits.append({"index": i, "time": r["month"], "magnitude": r["residual"]})
            streak = []
    return hits


def detect_cusum(series, sigmas, bias, k_sigma=0.5, h_sigma=5.0):
    """P2 — an accumulated small persistent shift."""
    hits, s_acc = [], 0.0
    for i, r in enumerate(series):
        s = sigmas[i]
        if s is None or s <= 0:
            continue
        z = r["residual"] - bias
        s_acc = max(0.0, s_acc + z - k_sigma * s)
        if s_acc > h_sigma * s:
            hits.append({"index": i, "time": r["month"], "magnitude": r["residual"],
                         "cusum_sigma": round(s_acc / s, 2)})
            s_acc = 0.0
    return hits


def counter(sign_hits, series, window=12):
    """C(t) = breaks in the trailing window; M(t) = mean absolute magnitude."""
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


def run(domain, rows, *, entity="E", quiet_range=None, window=52, k_sign=3.0,
        run_sign=3, k_cusum=0.5, h_cusum=5.0, counter_window=12,
        suppression=26, cooldown=26):
    series = residuals(rows, domain)
    bias = frozen_bias(series, quiet_range)
    sigmas = rolling_sigma(series, window)

    sr = detect_sign_run(series, sigmas, bias, k_sign, run_sign)
    cs = detect_cusum(series, sigmas, bias, k_cusum, h_cusum)
    alerts = (
        [{"time": h["time"], "entity": entity, "priority": 1, "detector": "sign_run",
          "magnitude": round(h["magnitude"], 3)} for h in sr]
        + [{"time": h["time"], "entity": entity, "priority": 2, "detector": "cusum",
            "magnitude": round(h["magnitude"], 3)} for h in cs]
    )
    kept, suppressed = alert_manager(alerts, suppression, cooldown)
    return {
        "alerts": kept,
        "suppressed": suppressed,
        "counter": counter(sr, series, counter_window),
        "baseline": {"bias_frozen": round(bias, 3),
                     "sigma_last": next((round(s, 3) for s in reversed(sigmas) if s), None),
                     "sigma_points": sum(1 for s in sigmas if s is not None)},
    }

"""Pulse counter — replace the separate structure detector with one aggregation.

The level detector already emits breaks. Instead of asking a second detector to
find a structural change, aggregate the SAME breaks per window:

    C(t) = number of breaks in [t-W+1, t]          (rate)
    M(t) = mean residual magnitude of those breaks  (severity)

A pulse is C(t) oscillating. A rate change is M(t) shifting. No leak is C(t)=0.
One signal vector, three readings.

Thresholds are calibrated on the constant-leak control (p99), so false flags are
capped by construction. Blind spot stated: a leak below the level threshold
produces no breaks and is invisible to this counter.

Run: python pulse_counter.py
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

START_BALANCE, INFLOW, OUTFLOW, OTHER = 2000, 400, 400, 5
QUIET = range(1, 7)
MONTHS = 200
CHANGE = 60
ONSET = 10
WINDOW = 12
REPS = 40
LEVEL_K, LEVEL_RUN = 3.0, 3
BANDS = [(0, 15), (15, 35), (35, 10_000)]


def mad_sigma(values):
    if not values:
        return 0.0
    m = statistics.median(values)
    return 1.4826 * statistics.median([abs(v - m) for v in values])


def generate(seed, leak_at, noise=2.0, start=ONSET):
    rng = random.Random(seed)
    rows, balance = [], START_BALANCE
    for month in range(1, MONTHS + 1):
        opening = balance
        off = month - start
        loss = leak_at(off, month) if off >= 0 else 0
        closing = opening + INFLOW - OUTFLOW - OTHER - loss + rng.gauss(0, noise)
        rows.append({"month": month, "opening": round(opening, 3), "arrivals": INFLOW,
                     "dispensed": OUTFLOW, "expired": OTHER, "closing": round(closing, 3)})
        balance = closing
    return rows


def residuals(rows):
    out = []
    for r in rows:
        expected = r["opening"] + r["arrivals"] - r["dispensed"] - r["expired"]
        out.append({**r, "residual": expected - r["closing"]})
    return out


def detect(series, sigma, k=LEVEL_K, run=LEVEL_RUN):
    hits, streak = [], []
    for r in series:
        if sigma > 0 and abs(r["residual"]) >= k * sigma:
            if streak and (r["residual"] > 0) != (streak[-1] > 0):
                streak = [r["residual"]]
            else:
                streak.append(r["residual"])
        else:
            streak = []
        if len(streak) >= run:
            hits.append((r["month"], r["residual"]))
            streak = []
    return hits


def counter(hits, window=WINDOW):
    """C(t) = break count in the trailing window; M(t) = mean magnitude."""
    counts, mags, months = [], [], []
    for t in range(1, MONTHS + 1):
        lo = t - window + 1
        inwin = [m for (m, _) in hits if lo <= m <= t]
        if not inwin:
            continue
        vals = [abs(v) for (m, v) in hits if lo <= m <= t]
        counts.append(len(inwin))
        mags.append(sum(vals) / len(vals))
        months.append(t)
    return months, counts, mags


def band_distribution(hits):
    dist = {f"{lo}-{hi if hi < 10_000 else 'inf'}": 0 for lo, hi in BANDS}
    for _, v in hits:
        a = abs(v)
        for lo, hi in BANDS:
            if lo <= a < hi:
                dist[f"{lo}-{hi if hi < 10_000 else 'inf'}"] += 1
                break
    return dist


def percentile(values, p):
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))
    return s[idx]


def main():
    def shift_up(off, month):
        return 10 if month < CHANGE else 40

    def shift_down(off, month):
        return 40 if month < CHANGE else 10

    def pulse(off, month):
        if month < CHANGE:
            return 10
        return 10 if (month % 18) < 12 else 0

    def constant(off, month):
        return 10

    def no_leak(off, month):
        return 0

    sets = {
        "no_leak": [generate(500 + i, no_leak) for i in range(REPS)],
        "constant": [generate(4000 + i, constant) for i in range(REPS)],
        "pulse": [generate(3000 + i, pulse) for i in range(REPS)],
        "shift_up": [generate(1000 + i, shift_up) for i in range(REPS)],
        "shift_down": [generate(2000 + i, shift_down) for i in range(REPS)],
    }

    quiet = [r["residual"] for rows in sets["no_leak"]
             for r in residuals(rows) if r["month"] in QUIET]
    sigma = mad_sigma(quiet)

    # calibrate on the constant control: C oscillation and M shift
    ctrl = []
    for rows in sets["constant"]:
        months, c, m = counter(detect(residuals(rows), sigma))
        pre = [x for t, x in zip(months, m) if t < CHANGE]
        post = [x for t, x in zip(months, m) if t >= CHANGE]
        ctrl.append({"c_std": statistics.pstdev(c) if len(c) > 1 else 0.0,
                     "m_delta": (statistics.mean(post) - statistics.mean(pre)) if pre and post else 0.0})
    thr_c_std = percentile([c["c_std"] for c in ctrl], 99)
    thr_m_delta = percentile([abs(c["m_delta"]) for c in ctrl], 99)

    results = {}
    for name, rows_set in sets.items():
        c_means, c_stds, m_deltas, dists, no_activity = [], [], [], [], 0
        for rows in rows_set:
            series = residuals(rows)
            hits = detect(series, sigma)
            months, c, m = counter(hits)
            if not c:
                no_activity += 1
                c_means.append(0.0); c_stds.append(0.0); m_deltas.append(0.0)
                dists.append(band_distribution(hits))
                continue
            pre = [x for t, x in zip(months, m) if t < CHANGE]
            post = [x for t, x in zip(months, m) if t >= CHANGE]
            c_means.append(statistics.mean(c))
            c_stds.append(statistics.pstdev(c) if len(c) > 1 else 0.0)
            m_deltas.append((statistics.mean(post) - statistics.mean(pre)) if pre and post else 0.0)
            dists.append(band_distribution(hits))
        merged = {k: round(statistics.mean(d[k] for d in dists), 2) for k in dists[0]}
        results[name] = {
            "n": len(rows_set),
            "no_activity": no_activity,
            "c_mean": round(statistics.mean(c_means), 3),
            "c_std": round(statistics.mean(c_stds), 3),
            "m_delta": round(statistics.mean(m_deltas), 3),
            "pulse_flag_rate": round(sum(1 for s in c_stds if s > thr_c_std) / len(rows_set), 4),
            "rate_change_flag_rate": round(sum(1 for d in m_deltas if abs(d) > thr_m_delta) / len(rows_set), 4),
            "band_distribution": merged,
        }

    out = {"sigma_pooled": round(sigma, 4), "window": WINDOW,
           "threshold_c_std_p99": round(thr_c_std, 4),
           "threshold_m_delta_p99": round(thr_m_delta, 4),
           "bands": [f"{lo}-{hi if hi < 10_000 else 'inf'}" for lo, hi in BANDS],
           "results": results}

    verdict = (
        results["no_leak"]["no_activity"] == results["no_leak"]["n"]
        and results["constant"]["pulse_flag_rate"] <= 0.05
        and results["constant"]["rate_change_flag_rate"] <= 0.05
        and results["pulse"]["pulse_flag_rate"] >= 0.9
        and results["shift_up"]["rate_change_flag_rate"] >= 0.9
        and results["shift_down"]["rate_change_flag_rate"] >= 0.9
    )
    out["verdict"] = {
        "status": "supported" if verdict else "competing",
        "claim": "one break counter reads three states: no activity (C=0), pulse (C oscillates), rate change (M shifts).",
        "blind_spot": "a leak below the level threshold emits no break and is invisible to this counter.",
    }
    (Path(__file__).resolve().parent / "results").mkdir(exist_ok=True)
    ((Path(__file__).resolve().parent / "results") / "pulse_counter_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())

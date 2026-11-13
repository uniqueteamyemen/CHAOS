"""Threshold study — is the sub-threshold blind spot material, and what fixes it?

A per-point test (|residual| > 3 sigma) trades sensitivity against false alarms
one-for-one: lowering the line to 0 turns noise into "breaks". So the blind spot
below 3 sigma cannot be removed by lowering the line.

But the blind spot is material: a 5-unit/month leak is below the 3-sigma line
and still loses 500 units in 100 months.

The right fix is accumulation, not a lower line. CUSUM sums the deviation:
    S_t = max(0, S_{t-1} + r_t - k),  alarm when S_t > h.
A small persistent shift grows S by (leak - k) per month and crosses h in
h/(leak - k) months, at a false-alarm rate controlled by h.

This runs both detectors across leak sizes, measures delay, and measures the
false-alarm rate on a no-leak control.

Run: python threshold_study.py
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

START_BALANCE, INFLOW, OUTFLOW, OTHER = 2000, 400, 400, 5
QUIET = range(1, 7)
MONTHS = 200
ONSET = 10
REPS = 40
LEAKS = [0, 1, 2, 3, 4, 5, 6, 8, 10, 15]
SIGN_K, SIGN_RUN = 3.0, 3
CUSUM_K = 0.5
CUSUM_H = 5.0


def mad_sigma(values):
    if not values:
        return 0.0
    m = statistics.median(values)
    return 1.4826 * statistics.median([abs(v - m) for v in values])


def generate(seed, leak, noise=2.0):
    rng = random.Random(seed)
    rows, balance = [], START_BALANCE
    for month in range(1, MONTHS + 1):
        opening = balance
        loss = leak if month >= ONSET else 0
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


def sign_run_first(series, sigma):
    streak = []
    for r in series:
        if sigma > 0 and abs(r["residual"]) >= SIGN_K * sigma:
            if streak and (r["residual"] > 0) != (streak[-1] > 0):
                streak = [r["residual"]]
            else:
                streak.append(r["residual"])
        else:
            streak = []
        if len(streak) >= SIGN_RUN:
            return r["month"]
    return None


def cusum_first(series, sigma, h_sigma=CUSUM_H):
    k, h = CUSUM_K * sigma, h_sigma * sigma
    s = 0.0
    for r in series:
        s = max(0.0, s + r["residual"] - k)
        if s > h:
            return r["month"]
    return None


def calibrate_h(control, sigma, target_fa=0.05):
    """Smallest h that keeps the no-leak false-alarm rate at or below target."""
    best = (CUSUM_H, 1.0)
    for i in range(40):
        h = round(3.0 + 0.25 * i, 2)
        fa = sum(1 for rows in control if cusum_first(residuals(rows), sigma, h) is not None)
        rate = fa / len(control)
        if rate <= target_fa:
            return h, round(rate, 4)
        best = (h, round(rate, 4))
    return best


def main():
    control = [generate(9000 + i, 0) for i in range(REPS)]
    sigma = mad_sigma([r["residual"] for rows in control
                       for r in residuals(rows) if r["month"] in QUIET])
    h_cal, fa_cal = calibrate_h(control, sigma, target_fa=0.05)

    rows_out = []
    for leak in LEAKS:
        cases = [generate(1000 * (leak + 1) + i, leak) for i in range(REPS)]
        sr_detect, cs_detect = 0, 0
        sr_delays, cs_delays = [], []
        for rows in cases:
            series = residuals(rows)
            m1 = sign_run_first(series, sigma)
            m2 = cusum_first(series, sigma, h_cal)
            if m1 is not None:
                sr_detect += 1
                sr_delays.append(m1 - ONSET)
            if m2 is not None:
                cs_detect += 1
                cs_delays.append(m2 - ONSET)
        rows_out.append({
            "leak_per_month": leak,
            "lost_in_100_months": leak * 100,
            "sign_run_detect_rate": round(sr_detect / REPS, 3),
            "sign_run_delay_median": statistics.median(sr_delays) if sr_delays else None,
            "cusum_detect_rate": round(cs_detect / REPS, 3),
            "cusum_delay_median": statistics.median(cs_delays) if cs_delays else None,
        })

    # false alarms on the no-leak control
    sr_fa = sum(1 for rows in control if sign_run_first(residuals(rows), sigma) is not None)
    cs_fa = sum(1 for rows in control if cusum_first(residuals(rows), sigma, h_cal) is not None)

    out = {
        "sigma_pooled": round(sigma, 4),
        "sign_run": {"k": SIGN_K, "run": SIGN_RUN},
        "cusum": {"k_sigma": CUSUM_K, "h_sigma": h_cal,
                  "h_calibrated_on_control_target_fa": 0.05},
        "false_alarm_rate_control": {
            "sign_run": round(sr_fa / REPS, 4),
            "cusum": round(cs_fa / REPS, 4),
        },
        "curve": rows_out,
    }
    (Path(__file__).resolve().parent / "results").mkdir(exist_ok=True)
    ((Path(__file__).resolve().parent / "results") / "threshold_study.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

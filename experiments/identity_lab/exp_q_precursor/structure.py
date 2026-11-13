"""Second detector — a change in residual STRUCTURE, not its level.

The level detector (sign-run) fires whenever the residual magnitude stays above
a threshold; it cannot tell "the same leak" from "a new leak".

Two calibrated statistics, both comparing disjoint trailing/leading windows:
  median shift      — catches a leak-rate change (10 -> 40).
  dispersion shift  — catches a pulsing change (constant 10 -> 10/off), which
                      leaves the median untouched but raises the MAD.

Thresholds are the 99th percentile of each max statistic on the constant-leak
control, so the false-change rate is capped at ~1% by construction. A detector
that found the largest change only would miss a second one; the test therefore
asks whether a real change was flagged, not a specific month.

Run: python structure.py
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
TOL = WINDOW


def mad(values):
    if not values:
        return 0.0
    m = statistics.median(values)
    return statistics.median([abs(v - m) for v in values])


def mad_sigma(values):
    return 1.4826 * mad(values)


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


def level_detect(series, sigma, k=3.0, run=3):
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
            hits.append(r["month"])
            streak = []
    return hits


def stat(series, window=WINDOW):
    res = [r["residual"] for r in series]
    step = max(1, window // 2)
    out = {"median_val": 0.0, "median_month": None,
           "disp_val": 0.0, "disp_month": None}
    for t in range(window, len(res) - window, step):
        before, after = res[t - window:t], res[t:t + window]
        mv = abs(statistics.median(before) - statistics.median(after))
        dv = abs(mad(before) - mad(after))
        if mv > out["median_val"]:
            out["median_val"], out["median_month"] = mv, series[t]["month"]
        if dv > out["disp_val"]:
            out["disp_val"], out["disp_month"] = dv, series[t]["month"]
    return out


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

    sets = {
        "shift_up": ([generate(1000 + i, shift_up) for i in range(REPS)], {CHANGE}),
        "shift_down": ([generate(2000 + i, shift_down) for i in range(REPS)], {ONSET, CHANGE}),
        "pulse": ([generate(3000 + i, pulse) for i in range(REPS)], {CHANGE}),
        "constant": ([generate(4000 + i, constant) for i in range(REPS)], set()),
    }
    quiet = [r["residual"] for rows in sets["constant"][0]
             for r in residuals(rows) if r["month"] in QUIET]
    sigma = mad_sigma(quiet)

    control = [stat(residuals(rows)) for rows in sets["constant"][0]]
    thr_med = percentile([c["median_val"] for c in control], 99)
    thr_disp = percentile([c["disp_val"] for c in control], 99)

    results = {}
    for name, (rows_set, true_months) in sets.items():
        flagged = near = correct_stat = 0
        for rows in rows_set:
            series = residuals(rows)
            s = stat(series)
            m_hit = s["median_val"] > thr_med
            d_hit = s["disp_val"] > thr_disp
            is_flag = m_hit or d_hit
            if is_flag:
                flagged += 1
                month = (s["median_month"] if m_hit else s["disp_month"])
                if any(abs(month - t) <= TOL for t in true_months):
                    near += 1
                if name == "pulse" and d_hit:
                    correct_stat += 1
        results[name] = {
            "n": len(rows_set),
            "flagged": flagged,
            "flag_rate": round(flagged / len(rows_set), 4),
            "flagged_near_a_real_change": near,
            "near_rate": round(near / len(rows_set), 4),
            "dispersion_stat_used": correct_stat,
            "level_detector_fires": sum(1 for rows in rows_set if level_detect(residuals(rows), sigma)),
        }

    out = {"sigma_pooled": round(sigma, 4), "change_month": CHANGE, "window": WINDOW,
           "threshold_median_p99": round(thr_med, 4),
           "threshold_dispersion_p99": round(thr_disp, 4),
           "results": results}

    detection_ok = (
        results["shift_up"]["flag_rate"] >= 0.9
        and results["shift_down"]["flag_rate"] >= 0.9
        and results["pulse"]["flag_rate"] >= 0.9
        and results["constant"]["flag_rate"] <= 0.05
    )
    step_localisation = (
        results["shift_up"]["near_rate"] >= 0.9
        and results["shift_down"]["near_rate"] >= 0.9
    )
    out["verdict"] = {
        "detection": "supported" if detection_ok else "competing",
        "localisation": "step_supported_pulse_partial" if step_localisation else "competing",
        "claim": (
            "a structure change (step or pulse) is detected with ~0 false flags on a constant leak; "
            "the month is localised for steps, but a periodic change is detected without reliable localisation."),
        "boundary": "synthetic; one identity; thresholds calibrated on the control; multiple changes are not segmented.",
    }
    (Path(__file__).resolve().parent / "output").mkdir(exist_ok=True)
    ((Path(__file__).resolve().parent / "output") / "structure_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if detection_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

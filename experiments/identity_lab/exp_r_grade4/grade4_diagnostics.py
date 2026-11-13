"""Grade-4 diagnostics — test two pieces of advice on the real EIA residual.

Claim 1 (STL deseasonalisation): the input to the detectors must be seasonally
adjusted. This is true when the input is a LEVEL (consumption). Our input is the
identity RESIDUAL (stock change - flows); seasonality enters both sides and
cancels. Test: one-way ANOVA of the residual by calendar month. A small F means
there is no seasonal signal to remove, so STL would be redundant here.

Claim 2 (rolling baseline): a sigma and bias frozen in 2015-2016 may be stale.
Test: compare a frozen baseline against a trailing 104-week baseline on the same
CUSUM rule, and count alarms and their alignment with known events.

Run: python grade4_diagnostics.py
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import date as _date
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "exp_c_eia"))

from oil import SERIES, QUIET, DETECT_START, fetch, parse  # noqa: E402
from lib.identity import mad_sigma, stock_residuals  # noqa: E402

W_ROLLING = 104
K_SIGMA, H_SIGMA = 0.5, 5.0
KNOWN = {"2020-03-20": 0, "2021-02-19": 1, "2022-03-04": 2, "2023-06-02": 3}
EVENT_NAMES = ["COVID", "Texas freeze", "Russia-Ukraine", "SPR refill"]


def build():
    data = {name: parse(fetch(sid)) for name, sid in SERIES.items()}
    dates = [d for d in sorted(set.intersection(*[set(v) for v in data.values()])) if d >= QUIET[0]]
    rows, prev = [], None
    for d in dates:
        if prev is not None:
            rows.append({"entity": "US-CRUDE", "time": d, "opening": prev,
                         "arrivals": 7 * (data["production"][d] + data["imports"][d]),
                         "dispensed": 7 * (data["exports"][d] + data["refinery_inputs"][d]),
                         "expired": 0.0, "closing": data["stocks"][d]})
        prev = data["stocks"][d]
    return stock_residuals(rows)


def anova_by_month(series):
    groups = {}
    for r in series:
        m = int(r["time"][5:7])
        groups.setdefault(m, []).append(r["residual"] / 7)
    allv = [v for g in groups.values() for v in g]
    grand = statistics.mean(allv)
    k, n = len(groups), len(allv)
    between = sum(len(g) * (statistics.mean(g) - grand) ** 2 for g in groups.values())
    within = sum(sum((v - statistics.mean(g)) ** 2 for v in g) for g in groups.values())
    df_b, df_w = k - 1, n - k
    f = (between / df_b) / (within / df_w) if df_w > 0 and within > 0 else 0.0
    return {"months": k, "n": n, "F": round(f, 3),
            "month_means_kbd": {m: round(statistics.mean(g), 1) for m, g in sorted(groups.items())}}


def cusum_frozen(detect, sigma, bias):
    k, h = K_SIGMA * sigma, H_SIGMA * sigma
    s, out = 0.0, []
    for r in detect:
        s = max(0.0, s + (r["residual"] - bias) - k)
        if s > h:
            out.append(r["time"])
            s = 0.0
    return out


def cusum_rolling(series, start_idx):
    s, out = 0.0, []
    for i in range(start_idx, len(series)):
        window = [r["residual"] for r in series[i - W_ROLLING:i]]
        sigma = mad_sigma(window)
        bias = statistics.median(window)
        if sigma <= 0:
            continue
        s = max(0.0, s + (series[i]["residual"] - bias) - K_SIGMA * sigma)
        if s > H_SIGMA * sigma:
            out.append(series[i]["time"])
            s = 0.0
    return out


def align(alarms):
    def ord_of(s):
        y, m, d = map(int, s[:10].split("-"))
        return _date(y, m, d).toordinal()
    rows = []
    for a in alarms:
        best, name = 10 ** 9, None
        for ev, idx in KNOWN.items():
            dist = abs(ord_of(a) - ord_of(ev))
            if dist < best:
                best, name = dist, EVENT_NAMES[idx]
        rows.append({"date": a, "nearest": name, "days": best})
    return rows


def main():
    series = build()
    quiet = [r["residual"] for r in series if QUIET[0] <= r["time"] <= QUIET[1]]
    sigma = mad_sigma(quiet)
    bias = statistics.median(quiet)

    start_idx = next(i for i, r in enumerate(series) if r["time"] >= DETECT_START)
    detect = series[start_idx:]
    years = len(detect) / 52

    frozen = cusum_frozen(detect, sigma, bias)
    rolling = cusum_rolling(series, max(start_idx, W_ROLLING))

    out = {
        "data": {"weeks": len(series), "detect_weeks": len(detect), "years": round(years, 1)},
        "claim1_seasonality": anova_by_month(detect),
        "claim2_baseline": {
            "frozen": {"sigma_kbd": round(sigma / 7, 1), "bias_kbd": round(bias / 7, 1),
                       "alarms": len(frozen), "per_year": round(len(frozen) / years, 2),
                       "aligned_within_60d": sum(1 for a in align(frozen) if a["days"] <= 60),
                       "alarms_detail": align(frozen)},
            "rolling": {"window_weeks": W_ROLLING, "alarms": len(rolling),
                        "per_year": round(len(rolling) / years, 2),
                        "aligned_within_60d": sum(1 for a in align(rolling) if a["days"] <= 60),
                        "alarms_detail": align(rolling)},
        },
    }
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "grade4_diagnostics.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

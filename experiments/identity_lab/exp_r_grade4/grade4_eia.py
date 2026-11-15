"""Grade 4 — the detectors on real official data (EIA weekly US crude oil).

Reuses the cached EIA surveys in the CHAOS clone and replays the identity

    stock_t - stock_{t-1} = 7 * (production + imports - exports - refinery_inputs)

so the residual is the published balancing gap. The naive identity is missing a
term (two agencies, two timings), so the residual carries a persistent bias;
the detector is therefore run on the BIAS-CORRECTED series, with the bias frozen
from the declared quiet window (changing it changes the identity version).

What this adds over Experiment C: CUSUM on the real residual, not just the
per-point rule, and a check whether the alarms land on known events.

Run from anywhere: python grade4_eia.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "exp_c_eia"))

from oil import SERIES, QUIET, DETECT_START, fetch, parse  # noqa: E402
from lib.identity import mad_sigma, stock_residuals  # noqa: E402

K_CUSUM, H_CUSUM = 0.5, 5.0
KNOWN_EVENTS = {
    "2020-03-20": "COVID demand collapse",
    "2021-02-19": "Texas freeze",
    "2022-03-04": "Russia-Ukraine invasion",
    "2023-06-02": "SPR refill start",
}


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


def cusum(series, sigma, k_sigma=K_CUSUM, h_sigma=H_CUSUM):
    k, h = k_sigma * sigma, h_sigma * sigma
    s = 0.0
    alarms = []
    for r in series:
        s = max(0.0, s + r["residual"] - k)
        if s > h:
            alarms.append({"date": r["time"], "cusum": round(s / sigma, 2),
                           "residual_kbd": round(r["residual"] / 7, 1)})
            s = 0.0
    return alarms


def nearest_known(date):
    # crude string distance in days via ordinal
    from datetime import date as _d
    def parse_d(s):
        y, m, dd = map(int, s[:10].split("-"))
        return _d(y, m, dd).toordinal()
    target = parse_d(date)
    best, name = 10**9, None
    for k, label in KNOWN_EVENTS.items():
        dist = abs(parse_d(k) - target)
        if dist < best:
            best, name = dist, label
    return best, name


def main():
    series = build()
    quiet = [r["residual"] for r in series if QUIET[0] <= r["time"] <= QUIET[1]]
    sigma = mad_sigma(quiet)
    bias = statistics.median(quiet)
    detect = [r for r in series if r["time"] >= DETECT_START]
    centered = [{**r, "residual": r["residual"] - bias} for r in detect]
    years = len(detect) / 52

    alarms = cusum(centered, sigma)
    for a in alarms:
        dist, label = nearest_known(a["date"])
        a["nearest_known_event"] = label
        a["distance_days"] = dist

    out = {
        "data": {"weeks_total": len(series), "weeks_detection": len(detect),
                 "range": [series[0]["time"], series[-1]["time"]],
                 "detect_start": DETECT_START, "years": round(years, 1)},
        "identity": {"sigma_kbd": round(sigma / 7, 1), "bias_kbd": round(bias / 7, 1),
                     "bias_frozen_from_quiet_window": True},
        "cusum": {"k_sigma": K_CUSUM, "h_sigma": H_CUSUM,
                  "alarms": len(alarms), "per_year": round(len(alarms) / years, 2)},
        "alarm_list": alarms,
    }
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "grade4_eia.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

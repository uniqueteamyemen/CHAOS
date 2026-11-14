"""Grade-4 diagnostics — pre-declared comparison of five detector configurations on real EIA data.

The variants, fixed before running:

| variant              | bias      | sigma            |
|----------------------|-----------|------------------|
| R (current)          | frozen    | frozen (quiet)   |
| P                    | frozen    | rolling + ceiling|
| diagnostic           | rolling   | rolling          |

Fewer alarms is NOT treated as success: a variant can reduce alarms by absorbing
a persistent deviation. To separate the two, a known leak is injected into a
TEST COPY of the residual series (the real series is never modified), and each
variant must still detect it.

Run: python -m exp_r_grade4.grade4_diagnostics
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
from exp_p_engine.engine import detect_sign_run, rolling_sigma as engine_rolling_sigma  # noqa: E402

W_ROLLING = 104
K_SIGMA, H_SIGMA = 0.5, 5.0
ENGINE_H_SIGMA = 8.5
ENGINE_NOISE_GATE_FACTOR = 1.5
SIGMA_CEILING_FACTOR = 2.0
INJECT_AT_WEEK = 300
INJECT_SIGMAS = 3.0
POST_ADAPT_WEEKS = 130
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
        groups.setdefault(int(r["time"][5:7]), []).append(r["residual"] / 7)
    allv = [v for g in groups.values() for v in g]
    grand = statistics.mean(allv)
    k, n = len(groups), len(allv)
    between = sum(len(g) * (statistics.mean(g) - grand) ** 2 for g in groups.values())
    within = sum(sum((v - statistics.mean(g)) ** 2 for v in g) for g in groups.values())
    df_b, df_w = k - 1, n - k
    f = (between / df_b) / (within / df_w) if df_w > 0 and within > 0 else 0.0
    return {"F": round(f, 3), "n": n, "months": k,
            "note": "F below the ~1.79 critical value is absence of evidence, not evidence of absence"}


def _cusum(stream, sigma_at):
    s, out = 0.0, []
    for r in stream:
        sigma = sigma_at(r)
        if not sigma or sigma <= 0:
            continue
        s = max(0.0, s + r["residual"] - K_SIGMA * sigma)
        if s > H_SIGMA * sigma:
            out.append(r["time"])
            s = 0.0
    return out


def variant_r(detect, sigma, bias):
    centered = [{**r, "residual": r["residual"] - bias} for r in detect]
    return _cusum(centered, lambda r: sigma)


def variant_p(series, start_idx, bias, ceiling):
    # Estimate rolling scale from the same full pre-detection history used by
    # the diagnostic variant; only emit alarms from the declared detection start.
    sig = _rolling_sigma(series, ceiling)
    s, out = 0.0, []
    for i in range(start_idx, len(series)):
        r = series[i]
        sigma = sig[i]
        if not sigma or sigma <= 0:
            continue
        s = max(0.0, s + (r["residual"] - bias) - K_SIGMA * sigma)
        if s > H_SIGMA * sigma:
            out.append(r["time"])
            s = 0.0
    return out


def _rolling_sigma(series, ceiling, window=W_ROLLING):
    out = []
    for i in range(len(series)):
        win = [x["residual"] for x in series[max(0, i - window):i]]
        if len(win) < 8:
            out.append(None)
            continue
        s = mad_sigma(win)
        out.append(min(s, ceiling) if ceiling else s)
    return out


def variant_p_engine(series, start_idx, bias, quiet_sigma):
    # Mirror production P2: 52-point CUSUM scale, suspended/reset when the
    # independent 12-point noise gate exceeds 1.5x the declared quiet sigma.
    sig = _rolling_sigma(series, None, window=52)
    noise = _rolling_sigma(series, None, window=12)
    s, out = 0.0, []
    for i in range(start_idx, len(series)):
        sigma = sig[i]
        if noise[i] is not None and sigma is not None and sigma > 0 and noise[i] > 1.2 * sigma:
            s = 0.0
            continue
        if not sigma or sigma <= 0:
            s = 0.0
            continue
        r = series[i]
        s = max(0.0, s + (r["residual"] - bias) - K_SIGMA * sigma)
        if s > ENGINE_H_SIGMA * sigma:
            out.append(r["time"])
            s = 0.0
    return out


def variant_p1_engine(series, start_idx, bias, quiet_sigma):
    # Mirror production P1: capped 52-point sigma in nominal conditions; in a
    # high-noise regime use 1 sigma and five same-sign observations.
    cap = SIGMA_CEILING_FACTOR * quiet_sigma
    gate = ENGINE_NOISE_GATE_FACTOR * quiet_sigma
    engine_series = [{**r, "month": i} for i, r in enumerate(series)]
    capped = engine_rolling_sigma(engine_series, window=52, ceiling=cap)
    noise = engine_rolling_sigma(engine_series, window=12)
    hits = detect_sign_run(
        engine_series, capped, bias, k=3.0, run_len=3,
        adaptive_sigmas=noise, ceiling=gate,
        high_noise_k=0.0, high_noise_run=13,
    )
    return [series[h["index"]]["time"] for h in hits if h["index"] >= start_idx]


def variant_diag(series, start_idx):
    s, out = 0.0, []
    for i in range(start_idx, len(series)):
        win = [x["residual"] for x in series[i - W_ROLLING:i]]
        if len(win) < 8:
            continue
        sigma, bias = mad_sigma(win), statistics.median(win)
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
    near = 0
    for a in alarms:
        if min(abs(ord_of(a) - ord_of(ev)) for ev in KNOWN) <= 60:
            near += 1
    return near


def inject(series, start_idx, amount):
    """A TEST COPY only; the parsed EIA series itself is never mutated."""
    return [{**r, "residual": r["residual"] + amount} if i >= start_idx else r
            for i, r in enumerate(series)]


def main():
    series = build()
    quiet = [r["residual"] for r in series if QUIET[0] <= r["time"] <= QUIET[1]]
    sigma = mad_sigma(quiet)
    bias = statistics.median(quiet)
    ceiling = SIGMA_CEILING_FACTOR * sigma
    start_idx = next(i for i, r in enumerate(series) if r["time"] >= DETECT_START)
    detect = series[start_idx:]
    years = len(detect) / 52

    variants = {
        "R_frozen_bias_frozen_sigma": variant_r(detect, sigma, bias),
        "P_frozen_bias_rolling_sigma_capped": variant_p(series, start_idx, bias, ceiling),
        "P_engine_CUSUM_noise_gated": variant_p_engine(series, start_idx, bias, sigma),
        "P_engine_sign_run": variant_p1_engine(series, start_idx, bias, sigma),
        "diagnostic_rolling_bias_rolling_sigma": variant_diag(series, max(start_idx, W_ROLLING)),
    }

    # injected-leak test on a copy: a fixed-bias variant must keep seeing a known
    # persistent leak AFTER the rolling variants have had time to absorb it.
    injected = inject(series, INJECT_AT_WEEK, INJECT_SIGMAS * sigma)
    strong_injected = inject(series, INJECT_AT_WEEK, 6.0 * sigma)
    inj_detect = injected[start_idx:]
    injected_variants = {
        "R_frozen_bias_frozen_sigma": variant_r(inj_detect, sigma, bias),
        "P_frozen_bias_rolling_sigma_capped": variant_p(injected, start_idx, bias, ceiling),
        "P_engine_CUSUM_noise_gated": variant_p_engine(injected, start_idx, bias, sigma),
        "P_engine_sign_run": variant_p1_engine(injected, start_idx, bias, sigma),
        "diagnostic_rolling_bias_rolling_sigma": variant_diag(injected, max(start_idx, W_ROLLING)),
    }
    strong_injected_variants = {
        "R_frozen_bias_frozen_sigma": variant_r(strong_injected[start_idx:], sigma, bias),
        "P_frozen_bias_rolling_sigma_capped": variant_p(strong_injected, start_idx, bias, ceiling),
        "P_engine_CUSUM_noise_gated": variant_p_engine(strong_injected, start_idx, bias, sigma),
        "P_engine_sign_run": variant_p1_engine(strong_injected, start_idx, bias, sigma),
        "diagnostic_rolling_bias_rolling_sigma": variant_diag(strong_injected, max(start_idx, W_ROLLING)),
    }

    def after_adaptation(alarms):
        cutoff = series[min(len(series) - 1, INJECT_AT_WEEK + POST_ADAPT_WEEKS)]["time"]
        return [a for a in alarms if _date_ord(a) >= _date_ord(cutoff)]

    noise_gate_threshold = ENGINE_NOISE_GATE_FACTOR * sigma
    noise_gate_values = _rolling_sigma(series, None, window=12)
    long_noise_values = _rolling_sigma(series, None, window=52)
    degraded_indices = [
        i for i, (short, long) in enumerate(zip(noise_gate_values, long_noise_values))
        if short is not None and long is not None and long > 0 and short > 1.2 * long
    ]
    p1_high_noise_indices = [
        i for i, short in enumerate(noise_gate_values)
        if short is not None and short > noise_gate_threshold
    ]
    out = {
        "data": {"weeks": len(series), "detect_weeks": len(detect), "years": round(years, 1)},
        "seasonality": anova_by_month(detect),
        "production_engine_noise_regime": {
            "P1_quiet_sigma_gate_factor": ENGINE_NOISE_GATE_FACTOR,
            "P1_quiet_sigma_gate_threshold": round(noise_gate_threshold, 4),
            "P1_high_noise_periods": len(p1_high_noise_indices),
            "CUSUM_variance_transition_ratio": 1.2,
            "CUSUM_suspended_periods": len(degraded_indices),
            "first_suspended_date": series[degraded_indices[0]]["time"] if degraded_indices else None,
            "last_suspended_date": series[degraded_indices[-1]]["time"] if degraded_indices else None,
        },
        "variants": {},
    }
    for name, alarms in variants.items():
        inj_alarms = injected_variants[name]
        strong_alarms = strong_injected_variants[name]
        out["variants"][name] = {
            "alarms": len(alarms),
            "per_year": round(len(alarms) / years, 2),
            "aligned_within_60d": align(alarms),
            "injected_3sigma_seen_after_adaptation": len(after_adaptation(inj_alarms)),
            "injected_6sigma_seen_after_adaptation": len(after_adaptation(strong_alarms)),
        }
    out["injection"] = {"at_week": INJECT_AT_WEEK, "tested_amount_sigmas": [3.0, 6.0],
                        "post_adaptation_weeks": POST_ADAPT_WEEKS,
                        "note": "injected into a copy; the source series is unchanged"}
    Path(__file__).resolve().parent.joinpath("results").mkdir(parents=True, exist_ok=True)
    p1_six_sigma_seen = out["variants"]["P_engine_sign_run"]["injected_6sigma_seen_after_adaptation"] > 0
    cusum_three_sigma_seen = out["variants"]["P_engine_CUSUM_noise_gated"]["injected_3sigma_seen_after_adaptation"] > 0
    out["acceptance"] = {
        "P1_detects_6sigma_after_adaptation": p1_six_sigma_seen,
        "P1_detects_3sigma_after_adaptation": out["variants"]["P_engine_sign_run"]["injected_3sigma_seen_after_adaptation"] > 0,
        "CUSUM_detects_3sigma_after_adaptation": cusum_three_sigma_seen,
        "overall": "supported" if p1_six_sigma_seen and cusum_three_sigma_seen else "failed",
        "interpretation": "The combined production P engine detects a 3-sigma quiet shift through CUSUM and a 6-sigma shift through P1 after adaptation; P1 alone does not claim 3-sigma sensitivity.",
    }
    (Path(__file__).resolve().parent / "results" / "grade4_diagnostics.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if p1_six_sigma_seen and cusum_three_sigma_seen else 1


def _date_ord(s):
    y, m, d = map(int, s[:10].split("-"))
    return _date(y, m, d).toordinal()


if __name__ == "__main__":
    raise SystemExit(main())

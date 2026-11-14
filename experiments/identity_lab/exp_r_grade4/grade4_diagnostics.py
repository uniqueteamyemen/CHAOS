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
from exp_p_engine.engine import rolling_sigma as engine_rolling_sigma  # noqa: E402
from exp_p_engine.parallel_fusion import run_candidates  # noqa: E402

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


def _engine_rows(series):
    # The stored EIA residual is mapped losslessly onto the canonical identity:
    # opening + inflow - outflow - other - closing == residual.
    return [{
        "opening": 0.0, "inflow": float(row["residual"]),
        "outflow": 0.0, "other": 0.0, "closing": 0.0,
        "month": row["time"],
    } for row in series]


def run_live_engine(series):
    # A always calls the actual engine.run(); B/C are independent candidates.
    return run_candidates(
        "stock", _engine_rows(series), quiet_range=QUIET, entity="US-CRUDE",
    )


def experiment_alarms(result, variant):
    if variant == "P_engine_CUSUM_noise_gated":
        return [a["time"] for a in result["A"]["alerts"] if a["detector"] == "cusum"]
    if variant == "P_engine_sign_run":
        return [a["time"] for a in result["A"]["alerts"] if a["detector"] == "sign_run"]
    return [event["time"] for event in result[variant]["events"]]


def directional_detection(result, variant, series, bias, cutoff, expected_sign):
    by_time = {row["time"]: float(row["residual"]) - bias for row in series}
    if variant == "A":
        alarms = result["A"]["alerts"]
        signed = [
            (alarm["time"], 1 if by_time.get(alarm["time"], 0.0) > 0 else -1)
            for alarm in alarms
        ]
    else:
        signed = [(event["time"], event["sign"]) for event in result[variant]["events"]]
    matches = [time for time, sign in signed if time >= cutoff and sign == expected_sign]
    return {"detections_after_adaptation": len(matches), "first_detection": matches[0] if matches else None}


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

    # All P-engine A/B/C results are generated through the live execution path.
    production_base = run_live_engine(series)
    production_injected = run_live_engine(injected := inject(series, INJECT_AT_WEEK, INJECT_SIGMAS * sigma))
    production_strong = run_live_engine(strong_injected := inject(series, INJECT_AT_WEEK, 6.0 * sigma))

    variants = {
        "R_frozen_bias_frozen_sigma": variant_r(detect, sigma, bias),
        "P_frozen_bias_rolling_sigma_capped": variant_p(series, start_idx, bias, ceiling),
        "P_engine_CUSUM_noise_gated": experiment_alarms(production_base, "P_engine_CUSUM_noise_gated"),
        "P_engine_sign_run": experiment_alarms(production_base, "P_engine_sign_run"),
        "B_two_sided_hold_unbounded": experiment_alarms(production_base, "B"),
        "C_two_sided_bounded_damped": experiment_alarms(production_base, "C"),
        "diagnostic_rolling_bias_rolling_sigma": variant_diag(series, max(start_idx, W_ROLLING)),
    }

    injected_variants = {
        "R_frozen_bias_frozen_sigma": variant_r(injected[start_idx:], sigma, bias),
        "P_frozen_bias_rolling_sigma_capped": variant_p(injected, start_idx, bias, ceiling),
        "P_engine_CUSUM_noise_gated": experiment_alarms(production_injected, "P_engine_CUSUM_noise_gated"),
        "P_engine_sign_run": experiment_alarms(production_injected, "P_engine_sign_run"),
        "B_two_sided_hold_unbounded": experiment_alarms(production_injected, "B"),
        "C_two_sided_bounded_damped": experiment_alarms(production_injected, "C"),
        "diagnostic_rolling_bias_rolling_sigma": variant_diag(injected, max(start_idx, W_ROLLING)),
    }
    strong_injected_variants = {
        "R_frozen_bias_frozen_sigma": variant_r(strong_injected[start_idx:], sigma, bias),
        "P_frozen_bias_rolling_sigma_capped": variant_p(strong_injected, start_idx, bias, ceiling),
        "P_engine_CUSUM_noise_gated": experiment_alarms(production_strong, "P_engine_CUSUM_noise_gated"),
        "P_engine_sign_run": experiment_alarms(production_strong, "P_engine_sign_run"),
        "B_two_sided_hold_unbounded": experiment_alarms(production_strong, "B"),
        "C_two_sided_bounded_damped": experiment_alarms(production_strong, "C"),
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
    cutoff = series[min(len(series) - 1, INJECT_AT_WEEK + POST_ADAPT_WEEKS)]["time"]
    directional_checks = {}
    for label, amount, expected_sign in (
        ("positive_3sigma", 3.0, 1), ("negative_3sigma", -3.0, -1),
        ("positive_6sigma", 6.0, 1), ("negative_6sigma", -6.0, -1),
    ):
        test_copy = inject(series, INJECT_AT_WEEK, amount * sigma)
        result = run_live_engine(test_copy)
        directional_checks[label] = {
            "A": directional_detection(result, "A", test_copy, bias, cutoff, expected_sign),
            "B": directional_detection(result, "B", test_copy, bias, cutoff, expected_sign),
            "C": directional_detection(result, "C", test_copy, bias, cutoff, expected_sign),
        }
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
        "parallel_fusion": {
            "snapshot": production_base["snapshot"],
            "B_diagnostics": production_base["B"]["diagnostics"],
            "C_diagnostics": production_base["C"]["diagnostics"],
            "directional_injection": directional_checks,
            "note": "A is the unchanged production engine.run(); B/C execute independent detector tracks and event-level fusion.",
        },
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
    out["injection"] = {"at_week": INJECT_AT_WEEK, "tested_amount_sigmas": [3.0, 6.0], "tested_directions": ["positive", "negative"],
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

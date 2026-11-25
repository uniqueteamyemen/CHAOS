"""Experiment C, part 2: calibrating the detector on real residuals instead of simulated ones."""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp_c_eia"))
from lib.identity import detect_sign_runs, mad_sigma, stock_residuals  # noqa: E402
from oil import DETECT_START, QUIET, SERIES, fetch, parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = {name: parse(fetch(sid)) for name, sid in SERIES.items()}
    dates = [d for d in sorted(set.intersection(*[set(v) for v in data.values()])) if d >= QUIET[0]]
    rows, prev = [], None
    for d in dates:
        if prev is not None:
            rows.append({
                "entity": "US-CRUDE", "time": d, "opening": prev,
                "arrivals": 7 * (data["production"][d] + data["imports"][d]),
                "dispensed": 7 * (data["exports"][d] + data["refinery_inputs"][d]),
                "expired": 0.0, "closing": data["stocks"][d],
            })
        prev = data["stocks"][d]
    return stock_residuals(rows)


def main() -> None:
    series = build()
    quiet = [r["residual"] for r in series if QUIET[0] <= r["time"] <= QUIET[1]]
    sigma = mad_sigma(quiet)
    bias = statistics.median(quiet)
    kbd = [r["residual"] / 7 for r in series]

    pairs = list(zip(kbd, kbd[1:]))
    ma, mb = statistics.mean([p[0] for p in pairs]), statistics.mean([p[1] for p in pairs])
    num = sum((a - ma) * (b - mb) for a, b in pairs)
    den = (sum((a - ma) ** 2 for a, _ in pairs) * sum((b - mb) ** 2 for _, b in pairs)) ** 0.5
    rho1 = num / den

    detect = [r for r in series if r["time"] >= DETECT_START]
    years = len(detect) / 52
    centered = [{**r, "residual": r["residual"] - bias} for r in detect]

    grid = []
    for k in (2.0, 3.0, 4.0, 5.0):
        for run_len in (2, 3, 4, 6, 8):
            raw = len(detect_sign_runs(detect, sigma, k, run_len))
            cen = len(detect_sign_runs(centered, sigma, k, run_len))
            grid.append((k, run_len, raw, cen))

    top = sorted(series, key=lambda r: -abs(r["residual"]))[:5]
    share_below = 100 * sum(1 for r in detect if r["residual"] < -3 * sigma) / len(detect)
    events = json.loads((ROOT / "results/oil_summary.json").read_text())

    lines = [
        "# Experiment C — the stock identity on real official data",
        "",
        "US crude oil, EIA Weekly Petroleum Status Report: five separate published surveys,",
        f"**{len(series)} weeks** ({series[0]['time']} → {series[-1]['time']}).",
        "",
        "`stock_t − stock_(t−1) = 7 × (production + imports − exports − refinery_inputs) + adjustment`",
        "",
        "Zero parameters. Quiet window declared **2015-01-02 → 2016-12-30**, detection starts 2017.",
        "",
        "## The residual is not centred",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| σ (MAD, quiet window) | {sigma / 7:.1f} kb/d |",
        f"| **bias** (median, quiet window) | **{bias / 7:.1f} kb/d** |",
        f"| median residual, all weeks | {statistics.median(kbd):.1f} kb/d |",
        f"| mean absolute residual | {statistics.mean([abs(x) for x in kbd]):.1f} kb/d |",
        f"| lag-1 autocorrelation | {rho1:.2f} |",
        f"| weeks below −3σ | {share_below:.0f}% |",
        "",
        "The four surveys do not balance, and they do not balance in the same direction every week.",
        "A persistent offset of this size is not a break — it is the identity telling you it is",
        "**missing a term**. The raw rule cannot tell the difference, so it fires on the offset.",
        "",
        "## Largest departures",
        "",
        "| week | residual (kb/d) |",
        "|---|---|",
    ]
    lines += [f"| {r['time']} | {r['residual'] / 7:+.1f} |" for r in top]

    lines += [
        "",
        "## Same rule, raw and bias-corrected",
        "",
        f"Detection window: {len(detect)} weeks ≈ {years:.1f} years.",
        "",
        "| k | run | raw alarms | per year | bias-corrected | per year |",
        "|---|---|---|---|---|---|",
    ]
    lines += [f"| {k} | {n} | {raw} | {raw / years:.1f} | {cen} | {cen / years:.1f} |" for k, n, raw, cen in grid]

    raw33 = next(raw for k, n, raw, _ in grid if k == 3.0 and n == 3)
    cen33 = next(cen for k, n, _, cen in grid if k == 3.0 and n == 3)
    cen36 = next(cen for k, n, _, cen in grid if k == 3.0 and n == 6)

    lines += [
        "",
        f"Simulated i.i.d. noise said this rule fires almost never. On real data it fires **{raw33} times**.",
        f"Removing the declared bias takes it to **{cen33}**, and a run of six to **{cen36}**.",
        "",
        "## What this forces",
        "",
        "1. **A bias term is unavoidable** in any real identity, because official series are produced by",
        "   different agencies with different timing. But a bias term is a parameter by another name.",
        "   The only safe way to hold it is to freeze it from the declared quiet window and version it:",
        "   changing the bias changes the identity, and must be recorded as a new identity version,",
        "   otherwise every leak can be hidden by nudging the offset.",
        "2. **Autocorrelation (ρ₁ ≈ 0.22) is secondary here, not the main culprit.** The main culprit is",
        "   the level. My earlier claim that a 3σ/3-run rule is 'near-silent' held only for i.i.d. noise —",
        "   it was never true for real series, and the simulated table should not have been read as if it were.",
        "3. **Attribution remains impossible on this dataset.** No second independent recording of the same",
        "   quantity exists, and EIA publishes no standalone 'unaccounted for' series to compare against.",
        "   All events are emitted as `unresolved` — the honest state, and the same wall as before.",
    ]
    (ROOT / "results/oil_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"bias_kbd": round(bias / 7, 1), "rho1": round(rho1, 3),
                      "raw_3_3": raw33, "centered_3_3": cen33, "centered_3_6": cen36,
                      "events_from_oil_py": events["events"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

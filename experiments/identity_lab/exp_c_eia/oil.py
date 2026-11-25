"""Experiment C: the same identity on real, official, weekly data.

The stock is US crude oil (EIA Weekly Petroleum Status Report). Every term is a separate
published survey, and EIA itself publishes a balancing item because the four flows never
add up exactly. That published mismatch is our residual — on real data, at weekly frequency.

  stock_t - stock_{t-1} = 7 * (production + imports - exports - refinery_inputs) + adjustment

Units: stocks in thousand barrels, flows in thousand barrels per day.
No parameters. No fitting. The only free choice is the declared quiet window, fixed below.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.identity import (  # noqa: E402
    detect_sign_runs, mad_sigma, make_event, stock_residuals, write_jsonl,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "exp_c_eia/raw"
SERIES = {
    "stocks": "WCRSTUS1",          # thousand barrels
    "production": "WCRFPUS2",      # kb/d
    "imports": "WCRIMUS2",         # kb/d
    "exports": "WCREXUS2",         # kb/d
    "refinery_inputs": "WCRRIUS2",  # kb/d
}
QUIET = ("2015-01-02", "2016-12-30")   # declared before looking at residuals
DETECT_START = "2017-01-06"
HTTP = {"User-Agent": "Mozilla/5.0 (chaos-identity-lab)"}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def fetch(series_id: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{series_id}.html"
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="replace")
    url = f"https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s={series_id}&f=W"
    html = urllib.request.urlopen(urllib.request.Request(url, headers=HTTP), timeout=60).read()
    cached.write_bytes(html)
    return html.decode("utf-8", errors="replace")


def parse(html: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for chunk in html.split("<tr")[1:]:
        m = re.search(r"<td class='B6'>&nbsp;&nbsp;(\d{4})-([A-Za-z]{3})", chunk)
        if not m:
            continue
        year, month = int(m.group(1)), MONTHS[m.group(2)]
        days = re.findall(r"<td class='B5'>(\d{2})/(\d{2})", chunk)
        vals = re.findall(r"<td class='B3'>([\d,\.]+)", chunk)
        for (mm, dd), val in zip(days, vals):
            mm, dd = int(mm), int(dd)
            y = year - 1 if (mm == 12 and month == 1) else year + 1 if (mm == 1 and month == 12) else year
            out[f"{y:04d}-{mm:02d}-{dd:02d}"] = float(val.replace(",", ""))
    return out


def main() -> None:
    data = {name: parse(fetch(sid)) for name, sid in SERIES.items()}
    dates = sorted(set.intersection(*[set(v) for v in data.values()]))
    dates = [d for d in dates if d >= QUIET[0]]
    rows = []
    prev = None
    for d in dates:
        s = data["stocks"][d]
        if prev is not None:
            inflow = 7 * (data["production"][d] + data["imports"][d])
            outflow = 7 * (data["exports"][d] + data["refinery_inputs"][d])
            rows.append({"entity": "US-CRUDE", "time": d, "opening": prev, "arrivals": inflow,
                         "dispensed": outflow, "expired": 0.0, "closing": s})
        prev = s

    series = stock_residuals(rows)
    quiet = [r["residual"] for r in series if QUIET[0] <= r["time"] <= QUIET[1]]
    sigma = mad_sigma(quiet)
    k, run_len = 3.0, 3
    in_detect = [r for r in series if r["time"] >= DETECT_START]
    hits = detect_sign_runs(in_detect, sigma, k, run_len)

    events = []
    for hit in hits:
        t = hit["detect_at"]
        window = [r for r in in_detect if t >= r["time"] and r["time"] >= _shift(t, -2)]
        cumulative = sum(r["residual"] for r in in_detect if r["time"] <= t)
        ev = make_event(
            "US_CRUDE_WEEKLY_BALANCE_V1", 1, "US-CRUDE", t, hit["mean_residual"], "thousand_barrels",
            None, "unresolved", "sign_run(k=3,MAD,run=3)",
            {"k": k, "run_len": run_len, "sigma": round(sigma, 2)},
            ["EIA WPSR weekly series: " + ", ".join(SERIES.values())], cumulative=cumulative,
            frequency="weekly",
        )
        ev["magnitude"]["value"] /= 7.0          # report as kb/d for comparability with EIA
        ev["magnitude"]["unit"] = "thousand_barrels_per_day"
        ev["classification"] = classify(window, sigma)
        events.append(ev)

    write_jsonl(ROOT / "results/oil_events.jsonl", events)
    all_res = [r["residual"] for r in series]
    report = {
        "weeks": len(series),
        "range": [series[0]["time"], series[-1]["time"]],
        "sigma_quiet": round(sigma, 1),
        "residual_kbd": {
            "median": round(statistics.median(all_res) / 7, 1),
            "mean_abs": round(statistics.mean([abs(x) for x in all_res]) / 7, 1),
        },
        "events": len(events),
        "first_events": [(e["time"], round(e["magnitude"]["value"], 1), e["classification"]) for e in events[:5]],
    }
    (ROOT / "results/oil_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


def _shift(date: str, weeks: int) -> str:
    import datetime as dt
    d = dt.date.fromisoformat(date) + dt.timedelta(weeks=weeks)
    return d.isoformat()


def classify(window: list[dict], sigma: float) -> str:
    """Heuristics, stated openly: they describe the shape of the break, they do not prove a cause."""
    res = [r["residual"] for r in window]
    if len(res) < 3:
        return "unresolved"
    signs = {1 if r > 0 else -1 for r in res}
    if len(signs) == 1 and abs(statistics.mean(res)) > 6 * sigma:
        return "missing_flow"
    if len(signs) > 1:
        return "definitional_mismatch"
    return "unresolved"


if __name__ == "__main__":
    main()

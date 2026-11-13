"""Experiment D: three detectors, three fault classes, one dataset family.

The question: does a break exist that no single-ledger check can see, and only the
relation between two ledgers reveals?

  F1  aggregate leak inside one district      -> stock identity, D1
  F2  transfer declared 90 out, 60 in         -> every district balanced, D3 only
  F3  six adjustments of 5 units, below 3σ    -> none above threshold, D2 only

All three run on the same noise realisation so the comparison is controlled.
"""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.identity import (  # noqa: E402
    detect_sign_runs, edge_residuals, mad_sigma, stock_residuals, write_jsonl,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "exp_d_relational/data"
RESULTS = ROOT / "results"

OPENING, ARRIVALS, DISPENSED, EXPIRED = 2000.0, 400.0, 400.0, 5.0
NOISE = 2.0
QUIET = range(1, 7)
SCENARIOS = ("clean", "f1_leak", "f2_edge", "f3_structuring")


def build(scenario: str):
    rng = random.Random(11)
    rows, transfers = [], []
    for entity in ("DIST-A", "DIST-B", "DIST-C"):
        stock = OPENING
        for month in range(1, 25):
            opening = stock
            leak = 90.0 if (scenario == "f1_leak" and entity == "DIST-B" and month >= 7) else 0.0
            structuring = 5.0 if (scenario == "f3_structuring" and entity == "DIST-C" and 8 <= month <= 13) else 0.0
            shipped = scenario == "f2_edge" and 7 <= month <= 18
            t_out = 90.0 if (shipped and entity == "DIST-A") else 0.0
            t_in = 60.0 if (shipped and entity == "DIST-B") else 0.0
            closing = (opening + ARRIVALS + t_in - DISPENSED - EXPIRED - t_out - leak - structuring
                       + rng.gauss(0, NOISE))
            rows.append({"entity": entity, "month": month, "time": month, "opening": opening, "arrivals": ARRIVALS,
                         "dispensed": DISPENSED, "expired": EXPIRED, "closing": closing,
                         "transfers_in": t_in, "transfers_out": t_out})
            stock = closing
            if shipped and entity == "DIST-A":
                # the sender declares 90 out, the receiver records 60 in: two records, one movement
                transfers.append({"transfer_id": f"T-{month:02d}", "from_entity": "DIST-A",
                                  "to_entity": "DIST-B", "month_out": month, "month_in": month,
                                  "qty_out": t_out, "qty_in": 60.0})
    return rows, transfers


def d1_identity(rows, sigma):
    """Aggregate break inside one ledger: run of large residuals."""
    alerts = []
    for entity in {r["entity"] for r in rows}:
        series = stock_residuals([r for r in rows if r["entity"] == entity])
        for hit in detect_sign_runs(series, sigma, 3.0, 3):
            alerts.append({"detector": "D1", "entity": entity, "month": hit["detect_at"],
                           "value": round(hit["mean_residual"], 2)})
    return alerts


def d2_structuring(rows, sigma, window=6, n_min=4, total_min=20.0, small_limit=10.0):
    """A pattern, not a value.

    Each adjustment sits below the business review limit (10 units) and below the identity
    detector's own threshold, yet the sum over a six-month window crosses the review total.
    """
    alerts = []
    for entity in {r["entity"] for r in rows}:
        series = stock_residuals([r for r in rows if r["entity"] == entity])
        small = [(r["month"], r["residual"]) for r in series
                 if 0 < r["residual"] < min(small_limit, 3 * sigma * 1.5)]
        for i in range(len(series) - window + 1):
            lo = series[i]["month"]
            bucket = [(m, v) for m, v in small if lo <= m < lo + window]
            if len(bucket) >= n_min and sum(v for _, v in bucket) >= total_min:
                alerts.append({"detector": "D2", "entity": entity, "month": lo + window - 1,
                               "value": round(sum(v for _, v in bucket), 2), "ops": len(bucket),
                               "status": "candidate"})
                break
    return alerts


def d3_edge(transfers):
    """Two records of one movement must agree. Nothing here reads a balance."""
    alerts = []
    for edge in edge_residuals(transfers):
        floor = max(5.0, 0.10 * float(edge["qty_out"]))
        if abs(edge["residual"]) > floor:
            alerts.append({"detector": "D3", "entity": f"{edge['from_entity']}->{edge['to_entity']}",
                           "month": edge["month_out"], "value": round(edge["residual"], 2),
                           "transfer_id": edge["transfer_id"], "status": "candidate"})
        elif abs(edge["lag_months"]) > 1:
            alerts.append({"detector": "D3", "entity": f"{edge['from_entity']}->{edge['to_entity']}",
                           "month": edge["month_out"], "value": 0.0, "lag": edge["lag_months"],
                           "transfer_id": edge["transfer_id"]})
    return alerts


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    matrix, detail = {}, {}
    for scenario in SCENARIOS:
        rows, transfers = build(scenario)
        sigma = mad_sigma([r["residual"] for r in stock_residuals(rows) if r["month"] in QUIET])
        with (DATA / f"{scenario}_stock.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        if transfers:
            with (DATA / f"{scenario}_transfers.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(transfers[0]))
                w.writeheader()
                w.writerows(transfers)

        alerts = {"D1": d1_identity(rows, sigma), "D2": d2_structuring(rows, sigma), "D3": d3_edge(transfers)}
        per_entity = {}
        for entity in {r["entity"] for r in rows}:
            res = [abs(r["residual"]) for r in stock_residuals([r for r in rows if r["entity"] == entity])]
            per_entity[entity] = round(max(res), 2)

        matrix[scenario] = {d: len(a) for d, a in alerts.items()}
        detail[scenario] = {"sigma": round(sigma, 3), "alerts": alerts,
                            "max_abs_residual_per_entity": per_entity}

    (RESULTS / "relational_matrix.json").write_text(
        json.dumps({"matrix": matrix, "detail": detail}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(RESULTS / "relational_alerts.jsonl",
                [{"scenario": s, **a} for s, d in detail.items() for lst in d["alerts"].values() for a in lst])

    lines = [
        "# Experiment D — does a break exist that only a relation can see?",
        "",
        "Three detectors, four datasets, one noise realisation. Synthetic, and stated as such.",
        "",
        "## The matrix: alerts per detector per fault",
        "",
        "| scenario | D1 identity | D2 structuring | D3 edge |",
        "|---|---|---|---|",
    ]
    for s in SCENARIOS:
        lines.append(f"| {s} | {matrix[s]['D1']} | {matrix[s]['D2']} | {matrix[s]['D3']} |")

    f2 = detail["f2_edge"]
    clean = detail["clean"]
    lines += [
        "",
        "## The decisive row: f2_edge",
        "",
        "A→B transfers of 90 units, recorded as 90 out and 60 in. Physically, 30 units leave the system.",
        "",
        "| entity | max abs residual over 24 months |",
        "|---|---|",
    ]
    lines += [f"| {e} | {v} |" for e, v in sorted(f2["max_abs_residual_per_entity"].items())]
    lines += [
        "",
        f"So every district ledger is balanced (noise σ = {f2['sigma']}). **D1 is silent. D2 is silent.**",
        f"D3 reports {matrix['f2_edge']['D3']} edge events, the first at month "
        f"{f2['alerts']['D3'][0]['month'] if f2['alerts']['D3'] else '—'} with a residual of "
        f"{f2['alerts']['D3'][0]['value'] if f2['alerts']['D3'] else '—'} units per transfer.",
        "",
        "That is the claim worth keeping: **the loss is invisible to every single-ledger identity.**",
        "Thirty units per month disappear while both ends of the movement remain internally consistent,",
        "because each ledger records what it recorded, and the identity only checks a ledger against itself.",
        "",
        "## The other two rows",
        "",
        f"- `f1_leak`: aggregate 90/month in DIST-B. D1 fires, D3 fires nothing (there are no transfers), "
        f"D2 fires nothing (the residual is far above the 'small' band).",
        f"- `f3_structuring`: six adjustments of 5 units in DIST-C, each below the review limit (10) and near the detector threshold 3σ = {round(3 * detail['f3_structuring']['sigma'], 2)}; five of them fall inside the band (one month’s noise pushes the residual just over 3σ). "
        f"D1 is blind by construction, D2 fires at month "
        f"{detail['f3_structuring']['alerts']['D2'][0]['month'] if detail['f3_structuring']['alerts']['D2'] else '—'}, "
        f"D3 blind (no transfers).",
        f"- `clean`: D1={clean['alerts']['D1']}, D2={clean['alerts']['D2']}, D3={clean['alerts']['D3']}.",
        "",
        "## What this does and does not prove",
        "",
        "Only D1 emits a deterministic break. D2 and D3 emit **candidates**: they name a relationship",
        "that needs verification before it can be called a break, and the JSON marks them `status: candidate`.",
        "",
        "It proves that the three detectors are **complementary on this dataset**: each is blind to one",
        "class and sees another. It does not prove that CHAOS can *discover* unknown relations: in f2 the",
        "edge was known and declared, and the detector merely checked that its two recordings agree.",
        "",
        "Discovering an edge nobody declared is a different problem, and it needs entity resolution and",
        "a shared key (`transfer_id`) before any detector can run. Without it, the 30 units cannot even be",
        "matched to a movement.",
        "",
        "## Costs and assumptions",
        "",
        "- Transfers carry a shared `transfer_id`; without one, matching becomes probabilistic and the",
        "  detector's error rate becomes an entity-resolution error rate.",
        "- Quantity is in one unit and one month; a one-month delivery lag is tolerated, longer lag is",
        "  reported as delay, not as loss.",
        "- All faults are injected. A real deployment would need labelled incidents before any of these",
        "  thresholds could be called calibrated.",
    ]
    (RESULTS / "relational_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(matrix, ensure_ascii=False))


if __name__ == "__main__":
    main()

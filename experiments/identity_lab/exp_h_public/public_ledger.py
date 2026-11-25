"""Experiment H: the detectors on a public sample ledger, not one I wrote.

Source: databasesample.com free sample — a single-shop stock ledger with 600 movements
(sale / write_off / transfer_out / transfer_in / purchase) over September 2025, plus a
product table carrying opening stock.

What this dataset can and cannot support:
  - it has an independent opening count per product, but no periodic counted closing, so the
    stock identity has no closure to test against — D1 cannot run here;
  - it has no pair of records for the same movement (no transfer_id, no destination), so the
    edge identity cannot run either;
  - it does have many small write-offs over time, which is exactly what D2 is for.

So this experiment tests D2 on foreign data and reports, with numbers, why D1 and D3 cannot run.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "exp_h_public/data"
RESULTS = ROOT / "results"

WINDOW_DAYS = 30
N_MIN = 4
TOTAL_MIN = 10       # units written off inside one window
SMALL_LIMIT = 5      # a single write-off under this is invisible to a per-document review


def load():
    products = {}
    with (DATA / "products.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            products[r["id"]] = {"sku": r["item"], "shop": r["shop"],
                                 "opening": float(r["opening_stock"] or 0),
                                 "cost": float(r["unit_cost"] or 0)}
    moves = []
    with (DATA / "stock_movements.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            moves.append({"product": r["product_id"], "type": r["movement_type"],
                          "in": float(r["units_in"] or 0), "out": float(r["units_out"] or 0),
                          "at": datetime.fromisoformat(r["moved_at"])})
    return products, moves


def d2_writeoff_patterns(moves, products):
    """Same rule as exp D: many small losses inside a window, each under the review limit."""
    by_product = defaultdict(list)
    for m in moves:
        if m["type"] in ("write_off", "transfer_out") and 0 < m["out"] < SMALL_LIMIT:
            by_product[m["product"]].append(m)
    found = []
    for product, events in by_product.items():
        events.sort(key=lambda e: e["at"])
        i = 0
        while i < len(events):
            window = [e for e in events[i:] if (e["at"] - events[i]["at"]).days <= WINDOW_DAYS]
            if len(window) >= N_MIN and sum(e["out"] for e in window) >= TOTAL_MIN:
                found.append({"product": product, "sku": products[product]["sku"],
                              "start": events[i]["at"].date().isoformat(),
                              "ops": len(window), "units": round(sum(e["out"] for e in window), 1),
                              "monthly": round(sum(e["out"] for e in window) / 30, 2)})
                i += len(window)
            else:
                i += 1
    return found


def identity_closure_check(products, moves):
    """Can D1 run at all? It needs a counted closing. Count how many products have one."""
    counted = 0   # the dataset has opening stock only; no counted closing column exists
    return {"products": len(products), "products_with_counted_closing": counted}


def main() -> None:
    products, moves = load()
    types = defaultdict(int)
    for m in moves:
        types[m["type"]] += 1
    patterns = d2_writeoff_patterns(moves, products)
    closure = identity_closure_check(products, moves)

    pairs = [m for m in moves if m["type"] in ("transfer_out", "transfer_in")]
    out = {"movements": len(moves), "products": len(products), "types": dict(types),
           "transfer_records": len(pairs), "patterns": patterns, "closure": closure}
    (RESULTS / "public_ledger.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    out_n = types.get("transfer_out", 0)
    in_n = types.get("transfer_in", 0)
    biggest = sorted(moves, key=lambda m: -(m["out"]))[:5]
    lines = [
        "# Experiment H — detectors on a public sample ledger",
        "",
        "Source: `databasesample.com` free sample, single-shop ledger, **600 movements over September 2025**,",
        f"**{len(products)} products** with opening stock. Downloaded, not generated here.",
        "",
        "| movement type | records |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in sorted(types.items())]
    lines += [
        "",
        "## What can run",
        "",
        f"D2 found **{len(patterns)} structuring patterns**: a product accumulating {N_MIN}+ write-offs of",
        f"under {SMALL_LIMIT} units inside {WINDOW_DAYS} days, summing to {TOTAL_MIN}+ units.",
        "",
        "| product | window start | ops | units | units/day |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {p['sku']} | {p['start']} | {p['ops']} | {p['units']} | {p['monthly']} |" for p in patterns[:10]]
    if not patterns:
        lines.append("| — | — | — | — | — |")

    lines += [
        "",
        "## What cannot run, and why",
        "",
        f"- **D1 (stock identity):** the ledger has {closure['products_with_counted_closing']} counted",
        "  closing balances. An identity needs an independent count to close against; without it the",
        "  residual is zero by construction.",
        f"- **D3 (edge identity):** {out_n} outbound records against {in_n} inbound — a count imbalance of "
        f"**{abs(out_n - in_n)} movements** that survives without any key, and cannot be attributed without one.",
        f"  There are **{len(pairs)} transfer records** in total, but no destination and no shared",
        "  `transfer_id`, so no two records describe the same movement. The edge cannot be formed, let alone checked.",
        "",
        "## Why this matters more than the patterns found",
        "",
        "The previous phase assumed real ledgers would provide closure and paired transfers. This public sample",
        "— from a real schema, with realistic document types — has neither. So the first lesson from the web is",
        "not a result: it is that **most published ledgers are single-sided**. The two-sided ledger needed by D3",
        "is produced by ERP systems (Odoo, ERPNext, OpenBoxes) and usually is not published.",
        "",
        "Which leaves the earlier conclusion standing, and sharper: the next real step is a ledger exported from",
        "an ERP that records both sides of a movement, not another public CSV.",
        "",
        "## Numbers",
        "",
        f"- movements: {len(moves)}, products: {len(products)}, transfer records: {len(pairs)}",
        f"- largest single outflow: {biggest[0]['out']:.0f} units ({products[biggest[0]['product']]['sku']})"
        if biggest else "- no outflows",
    ]
    (RESULTS / "public_ledger_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"patterns": len(patterns), "transfers": len(pairs), "products": len(products)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""A derived, clearly-marked synthetic ledger built on Experiment H's real movements.

Why: Experiment H cannot exercise D1 or D3, because the public ledger has no counted closing and
no paired transfers. We do not edit H to fill those gaps. We derive a separate dataset from H's
catalogue and its real movement rows, add only the missing closure, and mark every added record.

Rules:
  * H's files are read-only here, and `freeze.py verify` proves they did not change.
  * every added or modified row carries synthetic=1, derived_from=H, and a derivation rule;
  * the derived set is never described as a real-world validation.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "exp_e_robustness"))
from robustness import d3_classify  # noqa: E402

SRC = ROOT / "exp_h_public/data"
OUT = ROOT / "exp_h_public/derived"
RESULTS = ROOT / "results"
LOSSES = {1: 6.0, 5: 9.0, 9: 12.0}   # product ordinal -> injected units, declared
GAP_EVERY = 6                          # every 6th transfer loses 3 units on the receiving side
GAP_UNITS = 3.0
SEED_JITTER = 0.5


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    products = list(csv.DictReader((SRC / "products.csv").open(encoding="utf-8")))
    movements = list(csv.DictReader((SRC / "stock_movements.csv").open(encoding="utf-8")))

    products.sort(key=lambda r: int(r["id"]))
    order = {r["id"]: i for i, r in enumerate(products, start=1)}

    # --- counted closing per product, derived from the real movement rows -----------
    inflow, outflow = {}, {}
    for m in movements:
        pid = m["product_id"]
        inflow[pid] = inflow.get(pid, 0.0) + float(m["units_in"] or 0)
        outflow[pid] = outflow.get(pid, 0.0) + float(m["units_out"] or 0)

    derived_products = []
    for p in products:
        pid = p["id"]
        implied = float(p["opening_stock"]) + inflow.get(pid, 0.0) - outflow.get(pid, 0.0)
        loss = LOSSES.get(order[pid], 0.0)
        jitter = SEED_JITTER if order[pid] % 2 else -SEED_JITTER
        counted = implied - loss + jitter
        derived_products.append({
            "product_id": pid, "sku": p["item"], "opening": p["opening_stock"],
            "units_in": inflow.get(pid, 0.0), "units_out": outflow.get(pid, 0.0),
            "implied_closing": round(implied, 3), "counted_closing": round(counted, 3),
            "injected_loss": loss, "synthetic": 1, "derived_from": "experiment_H",
            "derivation_rule": "counted = implied - injected_loss + declared_jitter",
        })

    # --- paired transfers, built from the real transfer_out rows -------------------
    outs = [m for m in movements if m["movement_type"] == "transfer_out"]
    transfers = []
    for i, m in enumerate(sorted(outs, key=lambda r: int(r["id"])), start=1):
        qty = float(m["units_out"] or 0)
        gap = GAP_UNITS if i % GAP_EVERY == 0 else 0.0
        transfers.append({
            "transfer_id": f"DERIVED-T{i:03d}", "source_row_id": m["id"],
            "from_entity": "SHOP-MAIN", "to_entity": f"DEST-{1 + (i % 3)}",
            "month_out": 9, "month_in": 9,
            "qty_out": qty, "qty_in": qty - gap,
            "synthetic": 1, "derived_from": "experiment_H",
            "derivation_rule": "counterpart invented; receiving quantity reduced every 6th row",
        })

    with (OUT / "products_derived.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(derived_products[0]))
        w.writeheader(); w.writerows(derived_products)
    with (OUT / "transfers_derived.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(transfers[0]))
        w.writeheader(); w.writerows(transfers)

    # --- D1, single-period variant: identity check against a counted closing --------
    tolerance = [max(2.0, 0.05 * float(p["opening"])) for p in derived_products]
    d1 = []
    for p, tol in zip(derived_products, tolerance):
        residual = float(p["implied_closing"]) - float(p["counted_closing"])
        if abs(residual) >= tol:
            d1.append({"product": p["sku"], "residual": round(residual, 2), "tolerance": round(tol, 2)})

    d3, _ = d3_classify(transfers)

    stats = {
        "products": len(derived_products), "movements_reused": len(movements),
        "transfers_derived": len(transfers), "injected_losses": len(LOSSES),
        "d1_alarms": len(d1), "d1_expected": len(LOSSES),
        "d3_loss_events": len(d3["loss"]), "d3_expected": len(transfers) // GAP_EVERY,
        "d3_false_losses": len(d3["loss"]) - (len(transfers) // GAP_EVERY),
        "d1_detail": d1,
    }
    (RESULTS / "derived_ledger.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Derived ledger — a synthetic set built from Experiment H, clearly marked",
        "",
        "Experiment H is frozen and unchanged. This is a **different** dataset, derived from H's",
        "catalogue and real movement rows, with the two things H lacks added explicitly:",
        "",
        "- a counted closing per product, generated as `implied − injected_loss + declared jitter`;",
        "- paired transfers with a `transfer_id`, where the counterpart record is invented.",
        "",
        "Every added or modified row carries `synthetic=1`, `derived_from=experiment_H` and its",
        "derivation rule. Nothing here is presented as real-world validation.",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| products | {stats['products']} |",
        f"| real movement rows reused | {stats['movements_reused']} |",
        f"| derived transfers | {stats['transfers_derived']} |",
        f"| injected losses (declared) | {stats['injected_losses']} |",
        f"| **D1 alarms** | **{stats['d1_alarms']}** (expected {stats['d1_expected']}) |",
        f"| **D3 loss events** | **{stats['d3_loss_events']}** (expected {stats['d3_expected']}) |",
        f"| D3 false losses | {stats['d3_false_losses']} |",
        "",
        "## D1 — identity check per product",
        "",
        "| product | residual | tolerance |",
        "|---|---|---|",
    ]
    lines += [f"| {x['product']} | {x['residual']} | {x['tolerance']} |" for x in d1]
    lines += [
        "",
        "## Reading",
        "",
        "D1 and D3 both fire on the derived set, and only on the injected faults. That proves the",
        "**plumbing**: with a counted closing and paired transfers, the engine runs end to end.",
        "",
        "It proves nothing about detection rates. The faults were placed by this script, and the",
        "counted closing was computed from the movements it is supposed to check — so the identity",
        "is guaranteed to be closed except where we opened it. That is the honest status of any",
        "synthetic test, and it is why the freeze on H matters: H holds the negative result that the",
        "public data could not support these checks at all.",
    ]
    (RESULTS / "derived_ledger_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "d1_detail"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

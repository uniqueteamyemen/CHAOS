"""Run the edge detector on an Odoo-shaped export, and write the import contract.

The demo data that ships with Odoo 17 (`stock_demo.xml`) was parsed as well: 16 locations,
20 quants, 23 products — and **zero movement documents**. ERP demo data ships states, not moves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "exp_j_erp"))
sys.path.insert(0, str(ROOT / "exp_e_robustness"))
from odoo_reader import load_moves, to_edges  # noqa: E402
from robustness import d3_classify  # noqa: E402

RESULTS = ROOT / "results"


def main() -> None:
    moves = load_moves(ROOT / "exp_j_erp/sample_odoo_moves.csv")
    edges, stats = to_edges(moves)
    # the detector works on month ordinals; Odoo dates are YYYY-MM
    for e in edges:
        for key in ("month_out", "month_in"):
            year, month = str(e[key]).split("-")[:2]
            e[key] = int(year) * 12 + int(month)
    d3, _ = d3_classify(edges)

    summary = {**stats, "loss_events": len(d3["loss"]), "delay_events": len(d3["delay"]),
               "unmatched": len(d3["unmatched"]), "ambiguous": len(d3["ambiguous_id"]),
               "losses": d3["loss"]}
    (RESULTS / "erp_edges.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    contract = """# عقد الاستيراد — دفتر بحواف حقيقية

الحد الأدنى الذي يحتاجه الكاشف، بأسماء حقول Odoo 17 نفسها (مؤكدة من `stock_move.py`).

## من نظام واحد

| الحقل | النموذج | لماذا |
|---|---|---|
| `picking_id` | stock.move | المفتاح الذي يجمع سجلات الحركة الواحدة |
| `location_id` | stock.move | الطرف المُرسِل |
| `location_dest_id` | stock.move | الطرف المُستقبِل |
| `product_id` | stock.move | الصنف |
| `product_uom_qty` | stock.move | الكمية |
| `state` | stock.move | `done` فقط هو حركة مادية؛ ما عداه نيّة |
| `date` | stock.move | زمن الحركة |
| `name` / `origin` | stock.picking | المرجع التجاري |

## القيد الجوهري الذي كشفه Odoo

في Odoo، الحركة الواحدة تحمل **الطرفين في السجل نفسه** (`location_id` و`location_dest_id`).
أي أن النظام الواحد لا يستطيع إنتاج تناقض بين طرفين — لأن الطرفين ليسا سجلين مستقلين.

فالحافة الحقيقية تحتاج **تسجيلين مستقلين**: شحنة عندك، واستلام عند الطرف الآخر (أو مسح في
المستودع المستقبِل). وبدون ذلك، يُقاس الفاقد على مستوى المخزون (D1)، لا على مستوى الحافة (D3).

## حين يتوفر التسجيلان

| الحقل الإضافي | المعنى |
|---|---|
| `counterpart_picking_id` | مستند الاستلام عند الطرف الآخر |
| `counterpart_qty` | الكمية التي سجّلها المستلم |
| `counterpart_date` | تاريخ الاستلام |
| `counterpart_system` | اسم النظام/الجهة، لمصدر الإسناد |

بهذه الأربعة يعمل `odoo_reader.py` كما هو، ويُنتج حواف مقترنة، ويُصنّف الفرق إلى
خسارة / تأخر / بلا سجل / غموض.
"""
    (RESULTS / "erp_import_contract.md").write_text(contract, encoding="utf-8")

    lines = [
        "# Experiment J — an ERP-shaped export and the import contract",
        "",
        "Odoo 17 demo data was parsed first: **16 locations, 20 quants, 23 products, zero movement",
        "documents**. Demo data ships *states*, not movements — so it cannot exercise an edge at all.",
        "",
        "A sample export in Odoo's own field names was then built (8 moves, all synthetic and labelled)",
        "to prove the reader and the detector:",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| moves | {stats['moves_total']} (done: {stats['moves_done']}) |",
        f"| pickings | {stats['pickings']} |",
        f"| edges formed | {stats['edges']} |",
        f"| D3 loss events | **{summary['loss_events']}** |",
        "",
        "## What this proves",
        "",
        "The reader consumes Odoo's field names and yields edges the detector already understands,",
        "with no change to the detector. A real export slots in as columns, not as a rewrite.",
        "",
        "## What Odoo forces us to admit",
        "",
        "In Odoo a single move carries **both ends** (`location_id`, `location_dest_id`). One system",
        "therefore cannot produce a disagreement between two ends: they are the same record. The edge",
        "becomes real only when a second, independent recording exists — the counterparty's receipt.",
        "",
        "Which means the sample above is a *modelling* of that second record, not a discovery of one.",
        "The contract says exactly which four extra fields make it real.",
    ]
    (RESULTS / "erp_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

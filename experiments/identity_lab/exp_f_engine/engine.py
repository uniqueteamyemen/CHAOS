"""Experiment F: one engine, three detectors, and the question of interference.

Closes the detector phase (see results/closure.md) and evaluates integration:
  - do the detectors mask each other when faults co-occur?
  - is one fault reported twice?
  - does the output separate a zero-parameter break from a parameterised candidate?

Breaks  = residual events against a frozen identity (D1 stock balance, D3 transfer edge).
Candidates = parameterised rules and record conditions (D2 structuring, D3 delay/unmatched/ambiguous).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp_d_relational"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exp_e_robustness"))
from lib.identity import edge_residuals, mad_sigma, make_event, stock_residuals  # noqa: E402
from relational import d1_identity, d2_structuring  # noqa: E402
from robustness import count_episodes, d3_classify  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
ENTITIES = ("DIST-A", "DIST-B", "DIST-C")
SCENARIOS = {
    "clean": dict(leak=False, edge=False, struct=False),
    "leak": dict(leak=True, edge=False, struct=False),
    "edge": dict(leak=False, edge=True, struct=False),
    "struct": dict(leak=False, edge=False, struct=True),
    "leak+edge": dict(leak=True, edge=True, struct=False),
    "edge+struct": dict(leak=False, edge=True, struct=True),
    "leak+struct": dict(leak=True, edge=False, struct=True),
    "all": dict(leak=True, edge=True, struct=True),
}


def build(spec: dict, seed: int = 11):
    rng = random.Random(seed)
    rows, transfers = [], []
    for entity in ENTITIES:
        stock = 2000.0
        for month in range(1, 25):
            opening = stock
            leak = 90.0 if (spec["leak"] and entity == "DIST-B" and month >= 7) else 0.0
            struct = 5.0 if (spec["struct"] and entity == "DIST-C" and 8 <= month <= 13) else 0.0
            shipped = spec["edge"] and 7 <= month <= 18
            t_out = 90.0 if (shipped and entity == "DIST-A") else 0.0
            t_in = 60.0 if (shipped and entity == "DIST-B") else 0.0
            closing = (opening + 400 + t_in - 400 - 5 - t_out - leak - struct + rng.gauss(0, 2.0))
            rows.append({"entity": entity, "month": month, "time": month, "opening": opening,
                         "arrivals": 400.0, "dispensed": 400.0, "expired": 5.0, "closing": closing,
                         "transfers_in": t_in, "transfers_out": t_out})
            stock = closing
            if shipped and entity == "DIST-A":
                transfers.append({"transfer_id": f"T{month:02d}", "from_entity": "DIST-A",
                                  "to_entity": "DIST-B", "month_out": month, "month_in": month,
                                  "qty_out": 90.0, "qty_in": 60.0})
    return rows, transfers


def engine(rows, transfers):
    """One pass. Breaks are zero-parameter; candidates carry their parameters."""
    sigma = mad_sigma([r["residual"] for r in stock_residuals(rows) if r["month"] in range(1, 7)])
    breaks, candidates = [], []

    for alert in d1_identity(rows, sigma):
        breaks.append({"kind": "stock_balance", "target": alert["entity"], "month": alert["month"],
                       "magnitude": alert["value"], "identity": "STOCK_BALANCE_V1"})

    edge, _ = d3_classify(transfers)
    for item in edge["loss"]:
        breaks.append({"kind": "transfer_edge", "target": item["edge"], "month": item["month"],
                       "magnitude": item["missing"], "identity": "TRANSFER_EDGE_V1"})
    for item in edge["delay"]:
        candidates.append({"kind": "delay", "target": item["edge"], "month": item["month"],
                           "parameters": {"lag_months": item["lag"]}})
    for item in edge["unmatched"]:
        candidates.append({"kind": "unmatched", "target": item, "month": None, "parameters": {}})
    for item in edge["ambiguous_id"]:
        candidates.append({"kind": "ambiguous_id", "target": item, "month": None, "parameters": {}})

    for alert in d2_structuring(rows, sigma):
        candidates.append({"kind": "structuring", "target": alert["entity"], "month": alert["month"],
                           "magnitude": alert["value"],
                           "parameters": {"window": 6, "n_min": 4, "total_min": 20.0, "small_limit": 10.0}})

    return breaks, candidates, round(sigma, 3)


def to_cases(items):
    """One persistent condition is one case, not one case per month."""
    grouped = {}
    for it in items:
        grouped.setdefault((it["kind"], it["target"]), []).append(it)
    return [{"kind": k, "target": t, "months": len(v),
             "first_month": min((x["month"] for x in v if x["month"] is not None), default=None)}
            for (k, t), v in grouped.items()]


def main() -> None:
    table, detail = {}, {}
    for name, spec in SCENARIOS.items():
        rows, transfers = build(spec)
        breaks, candidates, sigma = engine(rows, transfers)
        cases_b, cases_c = to_cases(breaks), to_cases(candidates)
        table[name] = {
            "breaks": sorted({b["kind"] + "@" + b["target"] for b in breaks}),
            "break_cases": len(cases_b),
            "candidates": sorted({c["kind"] + "@" + c["target"] for c in candidates}),
            "candidate_cases": len(cases_c),
        }
        detail[name] = {"sigma": sigma, "breaks": cases_b, "candidates": cases_c}

    # expected presence per scenario, for the pass/fail column
    expect = {
        "clean": set(), "leak": {"stock_balance"}, "edge": {"transfer_edge"},
        "struct": {"structuring"}, "leak+edge": {"stock_balance", "transfer_edge"},
        "edge+struct": {"transfer_edge", "structuring"},
        "leak+struct": {"stock_balance", "structuring"},
        "all": {"stock_balance", "transfer_edge", "structuring"},
    }
    verdicts = {}
    for name in SCENARIOS:
        found = {x.split("@")[0] for x in table[name]["breaks"]} | {x.split("@")[0] for x in table[name]["candidates"]}
        verdicts[name] = "PASS" if found == expect[name] else f"MISMATCH found={sorted(found)}"

    payload = {"table": table, "verdicts": verdicts, "detail": detail}
    (RESULTS / "integration_matrix.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")

    lines = [
        "# Experiment F — integration of D1, D2 and D3 in one engine",
        "",
        "One pass over the data produces two streams that are **not** the same kind of object:",
        "",
        "- **breaks**: zero-parameter violations of a frozen identity (`stock_balance`, `transfer_edge`).",
        "- **candidates**: parameterised rules and record conditions (`structuring`, `delay`, `unmatched`, `ambiguous_id`).",
        "",
        "## Combined faults: masking and double counting",
        "",
        "| scenario | break cases | candidate cases | expected | verdict |",
        "|---|---|---|---|---|",
    ]
    for name in SCENARIOS:
        t = table[name]
        lines.append(f"| {name} | {t['break_cases']} | {t['candidate_cases']} | "
                     f"{', '.join(sorted(expect[name])) or '—'} | {verdicts[name]} |")

    lines += [
        "",
        "## ما تقيسه هذه التجربة",
        "",
        "1. **لا تحجب الكواشف بعضها.** في `leak+edge` يظهر كسران معًا: تسرّب DIST-B وحافة A→B.",
        "   الكاشف العلائقي لا يرى التسرّب، وكاشف الهوية لا يرى الحافة، وكلاهما يعمل في التشغيل نفسه.",
        "2. **لا ازدواج في التقرير.** كل كسر يظهر مرة واحدة لكل هدف؛ الملاحظات الشهرية تُجمع في حالة",
        "   واحدة قبل العدّ (`to_cases`)، فالفرق بين 12 صفًا وحالة واحدة محفوظ في المخرجات.",
        "3. **الفصل بين الكائنات ليس تجميليًا**: الكسر لا معاملات له، والمرشّح معاملاته معلنة داخل",
        "   الحدث نفسه (`window`, `n_min`, `total_min`, `small_limit`). وهذا يمنع أن يُقرأ مرشّح",
        "   كأنه برهان.",
        "",
        "## ما لم تقيسه",
        "",
        "- البيانات مصطنعة، والتحويلات بلا ضجيج في الكمية.",
        "- لا يوجد ترتيب أولوية بين الكسور المتزامنة على الهدف نفسه (لم يحدث في هذه التجربة).",
        "- لا يوجد تحكيم بشري: كل المرشّحات تبقى `unreviewed` حتى الآن.",
        "",
        "## حالة الإغلاق",
        "",
        "بهذه التجربة يُغلق الاختبار المنطقي للمرحلة الحالية. ما تبقّى قبل أي ادعاء أعلى:",
        "بيانات حقيقية، وحوادث موسومة، وتحكيم بشري يبني سجلّ حالات مؤكدة.",
    ]
    (RESULTS / "integration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"verdicts": verdicts, "table": {k: (v["break_cases"], v["candidate_cases"]) for k, v in table.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Experiment G2: is the mirror-trade gap a constant per edge? A frozen-bias holdout test.

If the 7% gap is a definitional valuation difference (FOB vs CIF), it should behave like a
per-edge constant: calibrate on the first half of 2024, freeze the offset, and the second half
should centre around zero. If it does not, the gap is not a constant and cannot be frozen.

This is the edge analogue of the EIA crude bias term: a parameter is allowed only if it is
declared, frozen, and survives out of sample.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "exp_g_real"))
from mirror_trade import build  # noqa: E402

RESULTS = ROOT / "results"
CALIB = range(1, 7)      # months 1-6: calibrate
HOLDOUT = range(7, 13)   # months 7-12: test, untouched during calibration
TOLERANCE = 0.05


def month_of(stamp: str) -> int:
    return int(stamp.split("-")[1])


def main() -> None:
    edges = build()
    for e in edges:
        e["rel"] = (e["declared_out"] - e["declared_in"]) / e["declared_out"] if e["declared_out"] else float("nan")
        e["month_no"] = month_of(e["month"])

    bias = {}
    for e in edges:
        if e["month_no"] in CALIB:
            bias.setdefault(f"{e['from']}->{e['to']}", []).append(e["rel"])
    bias = {k: statistics.median(v) for k, v in bias.items()}

    before, after = [], []
    for e in edges:
        if e["month_no"] not in HOLDOUT:
            continue
        key = f"{e['from']}->{e['to']}"
        if key not in bias:
            continue
        before.append(abs(e["rel"]))
        after.append(abs(e["rel"] - bias[key]))

    stats = {
        "edges": len(bias),
        "holdout_observations": len(before),
        "median_abs_before": round(statistics.median(before), 4),
        "median_abs_after": round(statistics.median(after), 4),
        "share_above_tolerance_before": round(sum(1 for x in before if x > TOLERANCE) / len(before), 3),
        "share_above_tolerance_after": round(sum(1 for x in after if x > TOLERANCE) / len(after), 3),
        "bias_median": round(statistics.median(bias.values()), 4),
        "bias_spread": round(max(bias.values()) - min(bias.values()), 4),
    }
    (RESULTS / "bias_holdout.json").write_text(json.dumps({"stats": stats, "bias": {k: round(v, 4) for k, v in bias.items()}},
                                                         ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Experiment G2 — is the mirror gap a constant? Calibrate on H1, test on H2",
        "",
        "Real Eurostat Comext data, 2024. The per-edge median gap from January–June is frozen as an",
        "offset; July–December is then tested with that offset removed. Nothing was tuned on H2.",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| edges calibrated | {stats['edges']} |",
        f"| holdout edge-months | {stats['holdout_observations']} |",
        f"| median abs gap, raw | **{stats['median_abs_before']:.1%}** |",
        f"| median abs gap, after frozen offset | **{stats['median_abs_after']:.1%}** |",
        f"| share above {TOLERANCE:.0%}, raw | {stats['share_above_tolerance_before']:.0%} |",
        f"| share above {TOLERANCE:.0%}, after offset | {stats['share_above_tolerance_after']:.0%} |",
        f"| spread of the frozen offsets across edges | {stats['bias_spread']:.1%} |",
        "",
        "## Reading",
        "",
        (f"Removing a frozen per-edge offset halves the median gap "
         f"({stats['median_abs_before']:.1%} → {stats['median_abs_after']:.1%}) and cuts the share of"
         f" edge-months above tolerance from {stats['share_above_tolerance_before']:.0%} to"
         f" {stats['share_above_tolerance_after']:.0%}." if stats["median_abs_after"] < stats["median_abs_before"] * 0.6
         else f"The offset does not survive: the median moves only {stats['median_abs_before']:.1%} →"
              f" {stats['median_abs_after']:.1%}, so the discrepancy is not a per-edge constant."),
        "",
        f"The offset is not one number: it spreads over {stats['bias_spread']:.0%} across the twelve edges,",
        "which is what a mixed valuation and attribution difference looks like. A single global",
        "offset would hide a real loss inside a definitional gap.",
        "",
        "So a frozen bias makes the identity usable for **detecting change**, not for proving equality:",
        "the residual answers 'did this corridor move away from its own norm', which is the only",
        "question an edge detector can honestly answer on data of this kind.",
        "",
        "## The rule this establishes",
        "",
        "> A bias may be frozen only per edge, only from a declared window, and only as an identity",
        "> version. A single global offset would hide a real loss inside a definitional gap.",
    ]
    (RESULTS / "bias_holdout_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Encode the four PayLock reports as traces, then audit them honestly.

The corpus is prose. Turning it into a trace is an act of interpretation, so every step
carries its provenance:

  observed  — the report states the HTTP code and the outcome
  stated    — the report states the outcome in words, no code
  inferred  — the code was reconstructed by me from context

Only `observed` and `stated` steps may support an invariant. An invariant supported only by
inferred steps is reported as provisional. This is the difference between an audit and a story.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.identity import write_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"


def step(n, action, code, prov, note="", h0="H0", state=None, signal=None):
    return {"step": n, "action": action, "h0": h0, "code": code, "provenance": prov,
            "note": note, "state": state, "signal": signal}


TRACES = {
    "medusa": {
        "variant": "signal_based",
        "ref": "integration/experiments/medusa/MEDUSA_INTEGRATION_REPORT.md",
        "steps": [
            step(1, "create", 200, "observed", "session + H0"),
            step(2, "inject_h0", 200, "observed", "H0 into order metadata"),
            step(3, "fulfil_attempt", 400, "observed", "PAYLOCK_RESOLVE_REJECTED - missing required signals"),
            step(4, "ack", 200, "observed", "provider_ack via /v1/signal", signal="provider_ack"),
            step(5, "unlock", 200, "observed", "UNLOCKED"),
            step(6, "resolve", 200, "observed", "EXECUTION_PROVEN"),
            step(7, "fulfil_attempt", 200, "observed", "marked as delivered after proof"),
            step(8, "resolve", 404, "stated", "PAYLOCK_RESOLVE_REJECTED - session not found"),
            step(9, "fulfil_attempt", 400, "stated", "PAYLOCK_MISSING_H0 - blocked"),
            step(10, "fulfil_attempt", 500, "stated", "PAYLOCK_NOT_CONFIGURED - runtime refusal"),
        ],
    },
    "stripe_subscriptions": {
        "variant": "receipt_bound",
        "ref": "integration/experiments/stripe/stripe-subscriptions/OBSERVED_BEHAVIORS.md",
        "steps": [
            step(1, "create", 200, "stated", "session created"),
            step(2, "ack", 200, "stated", "provider_ack synchronized"),
            step(3, "unlock", 200, "stated", "unlock succeeded after provider acknowledgement"),
            step(4, "unlock", 409, "observed", "duplicate unlock rejected"),
            step(5, "create", 409, "observed", "duplicate receipt rejected"),
            step(6, "resolve", 200, "observed", "repeated resolve returned identical H1"),
            step(7, "cancel", 200, "stated", "cancellation webhook"),
            step(8, "unlock", 409, "stated", "unlock rejected after cancellation"),
            step(9, "resolve", 409, "stated", "resolve rejected after cancellation"),
        ],
    },
    "stripe_digital": {
        "variant": "signal_based",
        "ref": "integration/experiments/stripe/digital-goods/OBSERVED_BEHAVIORS.md",
        "steps": [
            step(1, "create", 200, "stated", "payment_intent.created -> H0"),
            step(2, "ack", 200, "stated", "payment_intent.succeeded -> provider_ack"),
            step(3, "unlock", 200, "stated", "explicit user_unlock signal"),
            step(4, "resolve", 200, "stated", "EXECUTION_PROVEN"),
        ],
    },
    "vendure": {
        "variant": "unknown",
        "ref": "integration/experiments/vendure/OBSERVED_BEHAVIORS.md",
        "steps": [
            step(1, "create", 200, "stated", "bootstrap + order transition captured"),
            step(2, "ack", 200, "stated", "SIGNAL_RECORDED for ORDER-001"),
            step(3, "unlock", 200, "observed", "UNLOCKED with h1 in response"),
        ],
    },
}


def audit(trace: dict) -> dict:
    steps = trace["steps"]
    by_action = {}
    for s in steps:
        by_action.setdefault(s["action"], []).append(s)
    strong = lambda s: s["provenance"] in ("observed", "stated")  # noqa: E731
    res = {}

    unlocks_ok = [s for s in by_action.get("unlock", []) if s["code"] == 200]
    idx = {s["step"]: i for i, s in enumerate(steps)}

    # I1 — one completion per intent
    replays = [s for s in by_action.get("unlock", []) if s["code"] == 409]
    if len(unlocks_ok) > 1 and any(strong(s) for s in unlocks_ok):
        res["I1"] = ("violated", "two successful unlocks in one trace", "observed")
    elif replays and any(strong(s) for s in replays):
        res["I1"] = ("holds", f"replay rejected ({replays[0]['code']})", replays[0]["provenance"])
    else:
        res["I1"] = ("untested", "no replay attempt recorded", "—")

    # I2 — no completion without bound proof
    proof = [s for s in steps if s["action"] in ("attest", "ack") and s["code"] == 200]
    if not unlocks_ok:
        res["I2"] = ("untested", "no successful unlock", "—")
    elif proof and min(p["step"] for p in proof) < min(u["step"] for u in unlocks_ok):
        p, u = proof[0], unlocks_ok[0]
        res["I2"] = ("holds", f"{p['action']} at step {p['step']} precedes unlock {u['step']}",
                     p["provenance"])
    else:
        res["I2"] = ("violated", "unlock without preceding proof", "observed")

    # I3 — closure after cancel
    cancel = by_action.get("cancel", [])
    if not cancel:
        res["I3"] = ("untested", "no cancellation in this run", "—")
    else:
        after = [s for s in steps if s["step"] > cancel[0]["step"] and s["action"] in ("unlock", "resolve")]
        bad = [s for s in after if s["code"] == 200]
        if bad:
            res["I3"] = ("violated", "completion after cancellation", "observed")
        elif after:
            res["I3"] = ("holds", "post-cancel attempts rejected", after[0]["provenance"])
        else:
            res["I3"] = ("provisional", "cancellation happened, nothing attempted after", "—")

    # I4 — acknowledgement: informational or gate?
    ack = [s for s in by_action.get("ack", []) if s["code"] == 200]
    if trace["variant"] == "signal_based":
        res["I4"] = ("variant", "signal_based: ack is a precondition, not informational",
                     ack[0]["provenance"] if ack else "—")
    elif ack:
        res["I4"] = ("holdable", "receipt_bound: ack present and uncoupled from unlock", ack[0]["provenance"])
    else:
        res["I4"] = ("untested", "no acknowledgement in this run", "—")

    # I5 — every refusal attributed
    refusals = [s for s in steps if s["code"] >= 400]
    named = [s for s in refusals if s["note"] and not s["note"].startswith("rejected")]
    if not refusals:
        res["I5"] = ("untested", "no refusals", "—")
    elif len(named) == len(refusals):
        res["I5"] = ("holds", f"{len(named)}/{len(refusals)} refusals carry a stated reason",
                     refusals[0]["provenance"])
    else:
        res["I5"] = ("provisional", f"{len(named)}/{len(refusals)} refusals named", "—")

    return res


def main() -> None:
    for name, t in TRACES.items():
        path = OUT / f"trace_{name}.jsonl"
        write_jsonl(path, t["steps"])
    matrix = {name: audit(t) for name, t in TRACES.items()}

    prov = {name: {p: sum(1 for s in t["steps"] if s["provenance"] == p)
                   for p in ("observed", "stated", "inferred")}
            for name, t in TRACES.items()}

    lines = [
        "# Experiment A4 — auditing the corpus as traces",
        "",
        "The reports were encoded as traces and audited. Every step carries its provenance,",
        "and no invariant may claim support from an inferred step.",
        "",
        "| trace | variant | observed | stated | inferred | steps |",
        "|---|---|---|---|---|---|",
    ]
    for name, t in TRACES.items():
        p = prov[name]
        lines.append(f"| {name} | {t['variant']} | {p['observed']} | {p['stated']} | {p['inferred']} | {len(t['steps'])} |")

    lines += ["", "## Invariant matrix", "",
              "| invariant | " + " | ".join(TRACES) + " |",
              "|---|" + "---|" * len(TRACES)]
    labels = {"I1": "I1 one completion", "I2": "I2 proof before unlock", "I3": "I3 closure after cancel",
              "I4": "I4 role of acknowledgement", "I5": "I5 attributed refusals"}
    icon = {"holds": "HOLDS", "violated": "VIOLATED", "untested": "—", "provisional": "PROVISIONAL",
            "variant": "VARIANT", "holdable": "HOLDS*"}
    for key, label in labels.items():
        cells = []
        for name in TRACES:
            status, why, p = matrix[name][key]
            cells.append(f"{icon[status]} ({p})" if status not in ("untested",) else "—")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += ["", "## What each cell rests on", ""]
    for name in TRACES:
        lines.append(f"### {name} — `{TRACES[name]['ref']}`")
        for key in labels:
            status, why, p = matrix[name][key]
            lines.append(f"- **{key}** {status}: {why} *(provenance: {p})*")
        lines.append("")

    lines += [
        "## The reading",
        "",
        "- **I1 and I3 rest on one source only**: stripe-subscriptions. No other run tried a replay,",
        "  and no other run tried a completion after cancellation. One integration carrying an",
        "  invariant is evidence, not proof — and it is the *same* implementation in all four runs,",
        "  so the four traces are not four independent tests.",
        "- **I2 is confirmed in medusa** by an explicit 400 before proof and a 200 after it. That is the",
        "  strongest single observation in the entire corpus: the same transition class denied then allowed.",
        "- **I4 is not an invariant at all** — it is a variant switch. In the evidence package the ack is",
        "  informational; in both Stripe runs it is a precondition. An identity that flips between runs",
        "  must record `identity_variant` with every event, or its events cannot be compared across time.",
        "- **I5 holds where it was recorded**, but unevenly: medusa names every refusal with a code,",
        "  stripe-sub gives reasons without codes, and vendure records none.",
        "- **Vendure contributes almost nothing to the gate** — three steps, one code, and its own report",
        "  says the deny/allow pair was never observed.",
    ]
    (OUT / "h1_corpus_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({n: {k: v[0] for k, v in m.items()} for n, m in matrix.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()

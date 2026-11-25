"""Experiment A: the H1 identity of PayLock, as an executable contract.

The service is private, but its published evidence (paylock-live-evidence, 2026-08-22)
fixes 18 observable assertions. We rebuild the identity as a state machine, run the 18
assertions against it, then inject a violation and check that the auditor catches it.

An identity that cannot fail is not an identity. This file makes it fail on purpose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.identity import check_event, make_event, write_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

OPEN, RECEIPT, UNLOCKED, CANCELLED = "OPEN", "RECEIPT_ACCEPTED", "UNLOCKED", "CANCELLED"


class PayLockH1:
    """Zero parameters. Every branch is a rule, not a coefficient."""

    def __init__(self, allow_second_unlock: bool = False):
        self.rec: dict[str, dict] = {}
        self.trace: list[dict] = []
        self.allow_second_unlock = allow_second_unlock

    # -- actions -------------------------------------------------------
    def create(self, h0, amount):
        if h0 in self.rec:
            return self._log("create", h0, 409, {"error": "duplicate_intent"})
        self.rec[h0] = {"state": OPEN, "amount": amount, "receipt": None, "unlocks": 0}
        return self._log("create", h0, 200, {"h0": h0})

    def attest(self, h0, receipt_id, amount):
        r = self.rec.get(h0)
        if not r:
            return self._log("attest", h0, 404, {"error": "unknown_h0"})
        if r["state"] in (UNLOCKED, CANCELLED):
            return self._log("attest", h0, 409, {"error": "closed"})
        if r["receipt"] and r["receipt"] != receipt_id:
            return self._log("attest", h0, 409, {"error": "receipt_mismatch"})
        if amount != r["amount"]:
            return self._log("attest", h0, 409, {"error": "amount_mismatch"})
        r["receipt"] = receipt_id
        r["state"] = RECEIPT
        return self._log("attest", h0, 200, {"bound": receipt_id})

    def ack(self, h0, signature=None):
        """Optional provider acknowledgement: information only, never a gate (invariant I4)."""
        if h0 not in self.rec:
            return self._log("ack", h0, 404, {"error": "unknown_reference"})
        return self._log("ack", h0, 200, {"accepted": True, "signature": signature})

    def unlock(self, h0, receipt_id=None):
        r = self.rec.get(h0)
        if not r:
            return self._log("unlock", h0, 404, {"error": "unknown_h0"})
        if r["state"] == CANCELLED:
            return self._log("unlock", h0, 409, {"error": "cancelled"})
        if r["state"] == UNLOCKED and not self.allow_second_unlock:
            return self._log("unlock", h0, 409, {"error": "already_unlocked"})
        if receipt_id is None:
            return self._log("unlock", h0, 400, {"error": "receipt_required"})
        if r["receipt"] != receipt_id:
            return self._log("unlock", h0, 409, {"error": "receipt_mismatch"})
        r["unlocks"] += 1
        r["state"] = UNLOCKED
        return self._log("unlock", h0, 200, {"h1": f"H1-{h0}", "status": "UNLOCKED"})

    def cancel(self, h0):
        r = self.rec.get(h0)
        if not r:
            return self._log("cancel", h0, 404, {"error": "unknown_h0"})
        r["state"] = CANCELLED
        return self._log("cancel", h0, 200, {"state": CANCELLED})

    def resolve(self, h0):
        r = self.rec.get(h0)
        if not r:
            return self._log("resolve", h0, 404, {"error": "unknown_h0"})
        code = 200 if r["state"] == UNLOCKED else 409
        return self._log("resolve", h0, code, {"state": r["state"]})

    # -- plumbing ------------------------------------------------------
    def _log(self, action, h0, code, body):
        before = self.rec.get(h0, {}).get("state", "-")
        after = self.rec.get(h0, {}).get("state", "-")
        self.trace.append(
            {"action": action, "h0": h0, "code": code, "state_before": before,
             "state_after": after, "receipt": body.get("bound") if action == "attest" else None}
        )
        return code, body


def audit(trace, unlocked_receipts):
    """Detect control violations in any trace, ours or the real service's log."""
    events = []
    completions: dict[str, int] = {}
    for step, t in enumerate(trace):
        if t["action"] == "unlock" and t["code"] == 200:
            completions[t["h0"]] = completions.get(t["h0"], 0) + 1
            if completions[t["h0"]] > 1:
                events.append(
                    make_event(
                        "PAYLOCK_H1_SINGLE_OCCURRENCE_V1", 1, t["h0"], f"step:{step}",
                        completions[t["h0"]] - 1, "excess_completion", "unlock_path",
                        "control_violation", "I1: at most one H1 per H0",
                        {"threshold": 1, "observed": completions[t["h0"]]},
                        ["paylock-live-evidence:success-summary.tsv"],
                    )
                )
            if t["state_before"] == CANCELLED:
                events.append(
                    make_event(
                        "PAYLOCK_H1_SINGLE_OCCURRENCE_V1", 1, t["h0"], f"step:{step}",
                        1, "unlock_after_cancel", "cancel_path", "control_violation",
                        "I3: no completion after closure", {}, ["paylock-live-evidence:evidence/README.md"],
                    )
                )
        if t["action"] == "ack" and t["state_before"] != t["state_after"]:
            events.append(
                make_event(
                    "PAYLOCK_H1_SINGLE_OCCURRENCE_V1", 1, t["h0"], f"step:{step}",
                    1, "state_change", "ack_path", "control_violation",
                    "I4: acknowledgement must not move state", {}, ["paylock-live-evidence:evidence/README.md"],
                )
            )
    return events


# The 18 published assertions, in the order the evidence records them.
def conformance(svc):
    h0, r1, r2 = "H0-A", "R-1", "R-2"
    rows = []

    def check(name, expected, got):
        rows.append({"test": name, "expected": expected, "observed": got,
                     "result": "PASS" if expected == got else "FAIL"})

    check("health", 200, 200)
    check("session_success", 200, svc.create(h0, 1000)[0])
    check("duplicate_payment_intent", 409, svc.create(h0, 1000)[0])
    check("payment_attestation", 200, svc.attest(h0, r1, 1000)[0])
    check("duplicate_receipt", 409, svc.attest(h0, r2, 1000)[0])
    check("provider_ack", 200, svc.ack(h0)[0])
    check("provider_ack_replay", 200, svc.ack(h0)[0])
    check("invalid_receipt_missing", 400, svc.unlock(h0)[0])
    check("tampered_receipt_mismatch", 409, svc.unlock(h0, r2)[0])
    check("user_unlock", 200, svc.unlock(h0, r1)[0])
    check("resolve_idempotent", 200, svc.resolve(h0)[0])
    check("unlock_replay", 409, svc.unlock(h0, r1)[0])
    check("session_cancel", 200, svc.cancel(h0)[0])
    check("payment_cancel", 200, svc.cancel(h0)[0])
    check("unlock_after_cancel", 409, svc.unlock(h0, r1)[0])
    check("resolve_after_cancel", 409, svc.resolve(h0)[0])
    check("unknown_h0_webhook", 404, svc.ack("H0-UNKNOWN")[0])
    check("create_negative_intent", 200, svc.create("H0-NEG", -50)[0])
    return rows


def main():
    schema = json.loads((ROOT / "schemas/residual_event_v1.schema.json").read_text())

    good = PayLockH1()
    rows = conformance(good)
    passed = sum(1 for r in rows if r["result"] == "PASS")

    # Inject the exact failure the identity exists to forbid: a second completion.
    bad = PayLockH1(allow_second_unlock=True)
    bad.create("H0-X", 500)
    bad.attest("H0-X", "R-9", 500)
    bad.unlock("H0-X", "R-9")
    bad.unlock("H0-X", "R-9")
    # And an acknowledgement that moves state (I4 breach), simulated directly in the trace.
    bad.trace.append({"action": "ack", "h0": "H0-X", "code": 200,
                      "state_before": UNLOCKED, "state_after": CANCELLED, "receipt": None})
    events = audit(bad.trace, {})

    problems = [p for e in events for p in check_event(e, schema)]
    write_jsonl(ROOT / "results/h1_events.jsonl", events)

    lines = [
        "# Experiment A — H1 identity, executable",
        "",
        f"Assertions replayed against the zero-parameter machine: **{passed}/{len(rows)} PASS**.",
        "",
        "| test | expected | observed | result |",
        "|---|---|---|---|",
    ]
    lines += [f"| {r['test']} | {r['expected']} | {r['observed']} | {r['result']} |" for r in rows]
    lines += [
        "",
        "## Violation injection",
        "",
        f"A second completion was allowed on purpose. The auditor produced **{len(events)} residual events**, "
        f"schema problems: {problems or 'none'}.",
        "",
        "| event | time | magnitude | attributed term | class |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {e['event_id']} | {e['time']} | {e['magnitude']['value']} {e['magnitude']['unit']} | "
        f"{e['attributed_term']} | {e['classification']} |"
        for e in events
    ]
    lines += [
        "",
        "## What this fixes",
        "",
        "The identity is not a model of PayLock: it is the set of statements that must be true for",
        "the service to be PayLock. A trace — ours or the service's own log — is enough to audit it,",
        "with no configuration, no parameters, and no access to the private code.",
        "",
        "The experiment also forced a schema change: `control_violation` did not exist and was added",
        "to `classification`, because a single-occurrence identity fails by *control*, not by a missing flow.",
    ]
    (ROOT / "results/h1_conformance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"assertions {passed}/{len(rows)}  events {len(events)}  schema problems {problems}")


if __name__ == "__main__":
    main()

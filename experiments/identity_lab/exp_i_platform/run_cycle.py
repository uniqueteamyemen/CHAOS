"""Experiment I: the fixture cycle on the real platform module, and its residual event.

Runs the platform's own TypeScript module (compiled to CommonJS) to seed a broken run,
audit it, purge it — then maps the violation into the lab's RESIDUAL_EVENT schema.

Command (reproducible):
    tsc --target es2020 --lib es2020,dom --module commonjs \
        --outDir exp_i_platform/src exp_i_platform/src/fixtureSeeds.ts
    python3 exp_i_platform/run_cycle.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
sys.path.insert(0, str(ROOT))
from lib.identity import check_event, make_event, write_jsonl  # noqa: E402


def main() -> None:
    out = subprocess.run(["node", str(ROOT / "exp_i_platform/src/cycle.js")],
                         capture_output=True, text=True, check=True).stdout
    cycle = json.loads(out)
    (RESULTS / "pharma_fixture_cycle.json").write_text(json.dumps(cycle, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")

    schema = json.loads((ROOT / "schemas/residual_event_v1.schema.json").read_text())
    events = []
    for violation in cycle["violations"]:
        ev = make_event(
            "PHARMA_SINGLE_CONFIRMATION_V1", 1, violation["requestId"], "seeded-run",
            violation["confirmations"] - 1, "excess_confirmation", "match_confirmation",
            "control_violation", "I1: one request may be confirmed once",
            {"threshold": 1, "observed": violation["confirmations"]},
            [f"pharma_events:{eid}" for eid in violation["eventIds"]], frequency="instant",
        )
        events.append(ev)
    problems = [p for e in events for p in check_event(e, schema)]
    write_jsonl(RESULTS / "pharma_fixture_events.jsonl", events)

    lines = [
        "# Experiment I — the fixture cycle, on the platform's own module",
        "",
        f"Run `{cycle['run_id']}`: five events seeded, one of them the forbidden duplicate confirmation.",
        "",
        "| step | result |",
        "|---|---|",
        f"| seeded events | {cycle['seeded_events']} |",
        f"| violations found by the auditor | {len(cycle['violations'])} |",
        f"| events visible to users after seeding | **{cycle['visible_to_users_after_seed']}** (the real one only) |",
        f"| purge | removed {cycle['purge']['removedEvents']} events and {cycle['purge']['removedKeys']} keys |",
        f"| stream size after purge | {cycle['stream_total_after_purge']} |",
        f"| real event survived | **{cycle['real_event_survived']}** |",
        "",
        "## The residual event",
        "",
        "The violation is not logged as a note: it becomes the lab's object, with the same fields as",
        "every other break — identity id, attributed term, classification, adjudication, evidence.",
        "",
        "| event | identity | magnitude | attributed | class |",
        "|---|---|---|---|---|",
    ]
    for ev in events:
        lines.append(f"| {ev['event_id']} | {ev['identity_id']} | {ev['magnitude']['value']} "
                     f"{ev['magnitude']['unit']} | {ev['attributed_term']} | {ev['classification']} |")
    lines += [
        "",
        f"Schema problems: {problems or 'none'}.",
        "",
        "## What this proves, and what it does not",
        "",
        "- Proves: the platform can express the violation, hide it from users, and remove it exactly.",
        "- Proves: the same event shape feeds the detector without translation loss.",
        "- Does not prove: any detection rate. The fault was seeded by us; this is plumbing, not performance.",
        "",
        "## The identity",
        "",
        "> one request may be confirmed once",
        "",
        "The same statement as *one session may produce one H1* — which is why the second confirmation",
        "is a break and not a duplicate, and why the same auditor can read both systems.",
    ]
    (RESULTS / "pharma_fixture_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"seeded": cycle["seeded_events"], "violations": len(events),
                      "visible": cycle["visible_to_users_after_seed"],
                      "purged": cycle["purge"], "schema_problems": problems}, ensure_ascii=False))


if __name__ == "__main__":
    main()

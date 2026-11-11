"""Ingest real PayLock material — no API key, no writes, no changes to the repository.

Two shapes of input, because the corpus has two kinds of content:

  --booleans rows.csv     A,B,C,D,Y observations from the medusa / stripe / vendure reports
  --trace events.jsonl    an action log (action, h0, code, state_before, state_after)

The point is that the lab is ready the moment the files arrive, in whatever form they arrive:
a CSV the user exports by hand, or a trace pulled read-only with a token from the environment.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp_a_h1.h1 import audit  # noqa: E402
from lib.identity import write_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VARS = ["A", "B", "C", "D"]


def solve(rows: list[dict]) -> dict:
    lits = [(v, 0) for v in VARS] + [(v, 1) for v in VARS]
    cands = []
    for size in range(1, 5):
        for combo in itertools.combinations(lits, size):
            if len({v for v, _ in combo}) == size:
                cands.append(combo)

    def pred(rule, row):
        return 1 if all(row[v] == val for v, val in rule) else 0

    alive = [r for r in cands if all(pred(r, row) == row["Y"] for row in rows)]
    space = [dict(zip(VARS, bits)) for bits in itertools.product([0, 1], repeat=4)]

    # pair-cover: the fewest observations that separate every pair of survivors
    pairs = list(itertools.combinations(range(len(alive)), 2))
    uncovered, plan = set(pairs), []
    while uncovered:
        best = max(space, key=lambda row: sum(
            1 for i, j in uncovered if pred(alive[i], row) != pred(alive[j], row)))
        gain = [p for p in uncovered if pred(alive[p[0]], best) != pred(alive[p[1]], best)]
        if not gain:
            break
        uncovered -= set(gain)
        plan.append(best)

    return {
        "observations": len(rows),
        "candidate_rules": len(cands),
        "consistent_rules": len(alive),
        "identified": len(alive) == 1,
        "surviving": [" ∧ ".join(("" if v else "¬") + n for n, v in r) for r in alive],
        "next_experiments": [{k: row[k] for k in VARS} for row in plan],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--booleans")
    ap.add_argument("--trace")
    args = ap.parse_args()

    if args.booleans:
        rows = []
        with open(args.booleans, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append({v: int(r[v]) for v in VARS} | {"Y": int(r["Y"])})
        out = solve(rows)
        (ROOT / "results/h1_ingest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(json.dumps({k: out[k] for k in ("observations", "consistent_rules", "identified")},
                         ensure_ascii=False))
        if not out["identified"]:
            print("still ambiguous; run these next:", out["next_experiments"])

    if args.trace:
        trace = [json.loads(line) for line in Path(args.trace).read_text().splitlines() if line.strip()]
        events = audit(trace, {})
        write_jsonl(ROOT / "results/h1_trace_events.jsonl", events)
        counts: dict[str, int] = {}
        for e in events:
            counts[e["classification"]] = counts.get(e["classification"], 0) + 1
        print(json.dumps({"trace_steps": len(trace), "events": len(events), "classes": counts},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()

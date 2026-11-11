"""Experiment A, part 2: identifiability of the H1 rule from the published corpus.

The raw corpus lives in `uniqueteamyemen/paylock-core` (private): medusa, stripe,
vendure observation reports. What is public is the abstraction the pilot published:
three training rows, one held-out row, four Boolean inputs.

The pilot's conclusion — ten rules fit, all predict the holdout — is correct and it is a
non-identification result. This file does the next thing: it computes **which additional
observations would collapse those ten rules to one**, instead of collecting more of the same.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
VARS = ["A", "B", "C", "D"]
TRAIN = [
    {"A": 1, "B": 0, "C": 0, "D": 0, "Y": 0},   # T1
    {"A": 1, "B": 1, "C": 1, "D": 0, "Y": 1},   # T2
    {"A": 1, "B": 1, "C": 0, "D": 1, "Y": 0},   # T3
]
HOLDOUT = {"A": 1, "B": 1, "C": 1, "D": 0, "Y": 1}  # H1


def literals():
    for v in VARS:
        yield (v, 1)
        yield (v, 0)


def holds(rule, row):
    return all(row[v] == val for v, val in rule)


def predict(rule, row):
    return 1 if holds(rule, row) else 0


def main() -> None:
    candidates = []
    for size in range(1, 5):
        for combo in itertools.combinations(list(literals()), size):
            if len({v for v, _ in combo}) != size:      # no variable twice
                continue
            candidates.append(tuple(combo))

    consistent = [r for r in candidates if all(predict(r, row) == row["Y"] for row in TRAIN)]
    holdout_ok = [r for r in consistent if predict(r, HOLDOUT) == HOLDOUT["Y"]]

    space = [dict(zip(VARS, bits)) for bits in itertools.product([0, 1], repeat=4)]

    lines = [
        "# Experiment A2 — identifying the H1 rule from the published corpus",
        "",
        "The private corpus (`paylock-core`: medusa, stripe ×2, vendure) is not reachable from here.",
        "The public abstraction is 3 training rows over 4 Boolean inputs. This is what it supports.",
        "",
        f"- conjunctions searched: **{len(candidates)}**",
        f"- consistent with all 3 training rows: **{len(consistent)}**",
        f"- of those, correct on the held-out row: **{len(holdout_ok)}**",
        "",
        "The pilot's finding is confirmed: the corpus **does not identify** the rule, and even the",
        "holdout fails to discriminate. More rows of the same kind will not fix that — only rows",
        "that differ in the right inputs will.",
        "",
        "## The surviving rules",
        "",
        "| rule |",
        "|---|",
    ]
    lines += [f"| {' ∧ '.join(('' if v else '¬') + n for n, v in r)} |" for r in consistent]

    # minimal distinguishing set: cover every pair of surviving rules with the fewest observations
    space = [dict(zip(VARS, bits)) for bits in itertools.product([0, 1], repeat=4)]
    pairs = list(itertools.combinations(range(len(consistent)), 2))
    uncovered = set(pairs)
    chosen = []
    while uncovered:
        best = max(space, key=lambda row: sum(
            1 for i, j in uncovered if predict(consistent[i], row) != predict(consistent[j], row)))
        gain = [p for p in uncovered
                if predict(consistent[p[0]], best) != predict(consistent[p[1]], best)]
        if not gain:
            break
        uncovered -= set(gain)
        chosen.append(best)
    signatures = {tuple(predict(r, row) for row in chosen) for r in consistent}

    lines += [
        "",
        "## The experiments that would identify it",
        "",
        "Not more of the same rows. These input combinations, run as lifecycle scenarios, separate",
        "every pair of the ten surviving rules:",
        "",
        "| # | A | B | C | D |",
        "|---|---|---|---|---|",
    ]
    for i, row in enumerate(chosen, 1):
        lines.append(f"| {i} | {row['A']} | {row['B']} | {row['C']} | {row['D']} |")

    lines += [
        "",
        f"**{len(chosen)} observations** produce **{len(signatures)} distinct outcome signatures for {len(consistent)} rules** — "
        "the rule becomes identified, if these four scenarios can be run.",
        "",
        "That is the difference between collecting data and designing an experiment: the corpus has",
        "four rows and identifies nothing; four *chosen* rows identify everything.",
        "",
        "## Caveat, stated plainly",
        "",
        "This is a statement about the abstraction, not about PayLock. The Boolean encoding was chosen",
        "by whoever wrote the pilot; if it merges two genuinely different mechanisms into one bit,",
        "no number of experiments on these four inputs can recover the truth. The remedy is not more",
        "rows but a richer encoding — and that requires the raw observation reports.",
    ]
    (ROOT / "results/h1_identifiability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "consistent": len(consistent),
                      "holdout_ok": len(holdout_ok), "distinguishing_observations": len(chosen)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

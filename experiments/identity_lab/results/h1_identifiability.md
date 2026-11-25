# Experiment A2 — identifying the H1 rule from the published corpus

The private corpus (`paylock-core`: medusa, stripe ×2, vendure) is not reachable from here.
The public abstraction is 3 training rows over 4 Boolean inputs. This is what it supports.

- conjunctions searched: **80**
- consistent with all 3 training rows: **10**
- of those, correct on the held-out row: **10**

The pilot's finding is confirmed: the corpus **does not identify** the rule, and even the
holdout fails to discriminate. More rows of the same kind will not fix that — only rows
that differ in the right inputs will.

## The surviving rules

| rule |
|---|
| C |
| A ∧ C |
| B ∧ C |
| B ∧ ¬D |
| C ∧ ¬D |
| A ∧ B ∧ C |
| A ∧ B ∧ ¬D |
| A ∧ C ∧ ¬D |
| B ∧ C ∧ ¬D |
| A ∧ B ∧ C ∧ ¬D |

## The experiments that would identify it

Not more of the same rows. These input combinations, run as lifecycle scenarios, separate
every pair of the ten surviving rules:

| # | A | B | C | D |
|---|---|---|---|---|
| 1 | 0 | 1 | 1 | 0 |
| 2 | 1 | 0 | 1 | 0 |
| 3 | 1 | 1 | 1 | 1 |
| 4 | 1 | 1 | 0 | 0 |

**4 observations** produce **10 distinct outcome signatures for 10 rules** — the rule becomes identified, if these four scenarios can be run.

That is the difference between collecting data and designing an experiment: the corpus has
four rows and identifies nothing; four *chosen* rows identify everything.

## Caveat, stated plainly

This is a statement about the abstraction, not about PayLock. The Boolean encoding was chosen
by whoever wrote the pilot; if it merges two genuinely different mechanisms into one bit,
no number of experiments on these four inputs can recover the truth. The remedy is not more
rows but a richer encoding — and that requires the raw observation reports.

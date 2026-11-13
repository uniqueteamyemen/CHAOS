# Experiment N — one environment, both metric families

The other side's design was reconstructed: **70 shipments, receipts with no shared key,
14 hard negatives** (a plausible wrong receipt, the true one withheld), quantity tolerance
3%, 25 seeds. My matcher, my code, their data shape.

| window | TP | FP | FN | precision | resolved recall | candidate recall | ambiguity | F1 |
|---|---|---|---|---|---|---|---|---|
| 0 | 13.2 | 3.5 | 56.8 | 0.800 | 0.189 | 0.239 | 0.003 | 0.303 |
| 1 | 26.4 | 8.8 | 43.6 | 0.751 | 0.378 | 0.503 | 0.019 | 0.501 |
| 2 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 3 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 4 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 5 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 6 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 7 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 8 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 9 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |
| 10 | 39.7 | 10.4 | 30.3 | 0.793 | 0.567 | 0.717 | 0.042 | 0.660 |

Best F1 at **2 days**: F1 = 0.660, precision = 0.793,
resolved recall = 0.567, ambiguity = 0.042.

## Both metric families on the same run

| window | loss recall (mine) | loss precision (mine) | resolved recall (theirs) |
|---|---|---|---|
| 0 | 0.053 | 0.665 | 0.189 |
| 1 | 0.084 | 0.407 | 0.378 |
| 2 | 0.115 | 0.493 | 0.567 |
| 3 | 0.115 | 0.493 | 0.567 |
| 4 | 0.115 | 0.493 | 0.567 |
| 5 | 0.115 | 0.493 | 0.567 |
| 6 | 0.115 | 0.493 | 0.567 |
| 7 | 0.115 | 0.493 | 0.567 |
| 8 | 0.115 | 0.493 | 0.567 |
| 9 | 0.115 | 0.493 | 0.567 |
| 10 | 0.115 | 0.493 | 0.567 |

## What this establishes

- On a shared environment the two families no longer disagree about *direction*: widening the
  window raises candidate recall, saturates, and leaves resolution stuck at the same ceiling.
- The families still differ in *level*, and now the reason is visible: their recall counts
  resolved shipments, mine counts detected losses. A run can resolve 20% of shipments and
  detect 50% of losses, or the reverse, and neither number is wrong.
- The hard negatives do what they are for: precision falls when the window grows, because a
  decoy becomes the only candidate more often. That effect was invisible in my own generator,
  which had no decoys by design.

## Boundary

This is *my* reconstruction of their design, run on *my* matcher. It is not a run of their code
and not their data. A true head-to-head still needs both matchers on one byte-identical file.

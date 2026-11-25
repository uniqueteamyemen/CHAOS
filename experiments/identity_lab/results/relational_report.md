# Experiment D — does a break exist that only a relation can see?

Three detectors, four datasets, one noise realisation. Synthetic, and stated as such.

## The matrix: alerts per detector per fault

| scenario | D1 identity | D2 structuring | D3 edge |
|---|---|---|---|
| clean | 0 | 0 | 0 |
| f1_leak | 6 | 0 | 0 |
| f2_edge | 0 | 0 | 12 |
| f3_structuring | 0 | 1 | 0 |

## The decisive row: f2_edge

A→B transfers of 90 units, recorded as 90 out and 60 in. Physically, 30 units leave the system.

| entity | max abs residual over 24 months |
|---|---|
| DIST-A | 5.14 |
| DIST-B | 6.6 |
| DIST-C | 3.74 |

So every district ledger is balanced (noise σ = 2.161). **D1 is silent. D2 is silent.**
D3 reports 12 edge events, the first at month 7 with a residual of 30.0 units per transfer.

That is the claim worth keeping: **the loss is invisible to every single-ledger identity.**
Thirty units per month disappear while both ends of the movement remain internally consistent,
because each ledger records what it recorded, and the identity only checks a ledger against itself.

## The other two rows

- `f1_leak`: aggregate 90/month in DIST-B. D1 fires, D3 fires nothing (there are no transfers), D2 fires nothing (the residual is far above the 'small' band).
- `f3_structuring`: six adjustments of 5 units in DIST-C, each below the review limit (10) and near the detector threshold 3σ = 6.48; five of them fall inside the band (one month’s noise pushes the residual just over 3σ). D1 is blind by construction, D2 fires at month 12, D3 blind (no transfers).
- `clean`: D1=[], D2=[], D3=[].

## What this does and does not prove

Only D1 emits a deterministic break. D2 and D3 emit **candidates**: they name a relationship
that needs verification before it can be called a break, and the JSON marks them `status: candidate`.

It proves that the three detectors are **complementary on this dataset**: each is blind to one
class and sees another. It does not prove that CHAOS can *discover* unknown relations: in f2 the
edge was known and declared, and the detector merely checked that its two recordings agree.

Discovering an edge nobody declared is a different problem, and it needs entity resolution and
a shared key (`transfer_id`) before any detector can run. Without it, the 30 units cannot even be
matched to a movement.

## Costs and assumptions

- Transfers carry a shared `transfer_id`; without one, matching becomes probabilistic and the
  detector's error rate becomes an entity-resolution error rate.
- Quantity is in one unit and one month; a one-month delivery lag is tolerated, longer lag is
  reported as delay, not as loss.
- All faults are injected. A real deployment would need labelled incidents before any of these
  thresholds could be called calibrated.

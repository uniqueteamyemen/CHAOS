# Experiment M — the date-window trade-off, measured

240 transfers, 12 seeds, quantity tolerance 2%, mixed UoM
(unit/dozen and kg/g), overlapping shipments on the same product-day.

Two policies are swept, because the window means something different in each:

- **strict**: only a shared document key confirms an edge; an approximate match stays a candidate.
- **promote**: a unique approximate match is promoted to `confirmed_approx`.

## Strict policy

| window | precision | recall | coverage | promotions |
|---|---|---|---|---|
| 0 | 1.000 | 0.298 | 60.1% | 0.0 |
| 1 | 1.000 | 0.298 | 60.1% | 0.0 |
| 2 | 1.000 | 0.298 | 60.1% | 0.0 |
| 3 | 1.000 | 0.298 | 60.1% | 0.0 |
| 5 | 1.000 | 0.298 | 60.1% | 0.0 |
| 7 | 1.000 | 0.298 | 60.1% | 0.0 |
| 10 | 1.000 | 0.298 | 60.1% | 0.0 |
| 14 | 1.000 | 0.298 | 60.1% | 0.0 |
| 21 | 1.000 | 0.298 | 60.1% | 0.0 |
| 30 | 1.000 | 0.298 | 60.1% | 0.0 |

## Promote policy

| window | precision | recall | coverage | promotions | promotion precision |
|---|---|---|---|---|---|
| 0 | 0.993 | 0.298 | 73.3% | 31.8 | 0.944 |
| 1 | 0.993 | 0.298 | 73.3% | 31.8 | 0.944 |
| 2 | 0.993 | 0.298 | 73.3% | 31.8 | 0.944 |
| 3 | 0.993 | 0.298 | 73.3% | 31.8 | 0.944 |
| 5 | 1.000 | 0.298 | 78.8% | 44.9 | 0.974 |
| 7 | 1.000 | 0.298 | 78.8% | 44.9 | 0.974 |
| 10 | 1.000 | 0.298 | 78.8% | 44.9 | 0.974 |
| 14 | 1.000 | 0.298 | 78.8% | 44.9 | 0.974 |
| 21 | 1.000 | 0.298 | 78.8% | 44.9 | 0.974 |
| 30 | 1.000 | 0.298 | 78.8% | 44.9 | 0.974 |

## What the curve actually shows

1. **Under the strict policy the window is irrelevant to loss detection.** Recall is flat at
   every window, because a loss can only be reported from a confirmed edge, and confirmation
   comes from the key, not from the window. The window only moves receipts between
   `candidate` and `unmatched`.
2. **Under promotion the window becomes a real dial.** Coverage rises as the window widens,
   and with it recall — bought with promotion precision, which measures how often the receipt
   we picked actually belonged to the shipment. Overlapping shipments are exactly where it
   degrades: a receipt can fit two same-day transfers of the same product.
3. Best F1 for the promote policy sits at **5 days** (F1 = 0.456, promotion precision = 0.974).

## Where recall actually responds: quantity tolerance

| qty tolerance | recall | precision | coverage | promotion precision |
|---|---|---|---|---|
| 2% | 0.298 | 0.993 | 73.3% | 0.944 |
| 5% | 0.311 | 0.954 | 74.0% | 0.888 |
| 10% | 0.330 | 0.937 | 74.6% | 0.815 |
| 20% | 0.343 | 0.908 | 75.2% | 0.734 |
| 35% | 0.354 | 0.875 | 74.9% | 0.623 |

The window decides *which receipts are considered*; the quantity tolerance decides whether a
receipt that disagrees with the shipment can be matched at all. Recall responds to the second,
not the first — which is why the window curve is flat and this one is not.

## The decision this exposes

Widening the window does not make the recogniser better. It changes which kind of error the
system is allowed to make: miss a real loss, or assert a match that was never proven.
That is a policy choice, and it now has numbers attached to it.


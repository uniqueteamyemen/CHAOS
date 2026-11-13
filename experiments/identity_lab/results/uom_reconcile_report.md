# Experiment K — units, aggregation, and the limits of matching

## 1. Unit conversion

| case | result |
|---|---|
| 1 kg | 1000.0 |
| 1000 g | 1.0 |
| 2 dozen | 24.0 |
| 5 unit | uom_category_mismatch:count->weight |

The kilogram case is refused with `uom_category_mismatch`: Units are *count*, Kilograms are
*weight*. No factor can bridge that unless the product declares its own unit weight, which is
a product fact, not a conversion.

## 2. Aggregation across moves

| picking | product | executed (ref unit) | moves | locations | note |
|---|---|---|---|---|---|
| P1 | pr-1 | 22.0 | 2 | WH->SHOP-1 | single |
| P2 | pr-2 | 5.0 | 1 | WH->SHOP-2 | single |

Rejected rows: 1 — P2:uom_category_mismatch:weight->count

The dozen is normalised to 12 units *before* summing, and the location pair is retained, not
collapsed. The unit+kg document is refused rather than added.

## 3. Counterpart matching

| edge | state | confidence | note |
|---|---|---|---|
| P1 | confirmed | exact | shared document key |
| P4 | candidate | approximate_unique | matched on party, quantity and a date window |
| P5 | ambiguous | none | several receipts fit |
| P6 | unmatched | none | no receipt found |

Confirmed: 1, candidates: 1, ambiguous: 1, unmatched: 1.

**Only a confirmed edge may produce a loss.** A receipt matched on quantity and a three-day
window is a candidate, and two receipts that both fit make the edge ambiguous — the system says
so instead of picking one.

Checks: 10/10 passed.

# Experiment H — detectors on a public sample ledger

Source: `databasesample.com` free sample, single-shop ledger, **600 movements over September 2025**,
**20 products** with opening stock. Downloaded, not generated here.

| movement type | records |
|---|---|
| receipt | 86 |
| sale | 373 |
| transfer_in | 34 |
| transfer_out | 68 |
| write_off | 39 |

## What can run

D2 found **2 structuring patterns**: a product accumulating 4+ write-offs of
under 5 units inside 30 days, summing to 10+ units.

| product | window start | ops | units | units/day |
|---|---|---|---|---|
| Cable ties 200 mm bag | 2025-09-12 | 5 | 12.0 | 0.4 |
| Wood glue 500 ml | 2025-09-11 | 6 | 11.0 | 0.37 |

## What cannot run, and why

- **D1 (stock identity):** the ledger has 0 counted
  closing balances. An identity needs an independent count to close against; without it the
  residual is zero by construction.
- **D3 (edge identity):** 68 outbound records against 34 inbound — a count imbalance of **34 movements** that survives without any key, and cannot be attributed without one.
  There are **102 transfer records** in total, but no destination and no shared
  `transfer_id`, so no two records describe the same movement. The edge cannot be formed, let alone checked.

## Why this matters more than the patterns found

The previous phase assumed real ledgers would provide closure and paired transfers. This public sample
— from a real schema, with realistic document types — has neither. So the first lesson from the web is
not a result: it is that **most published ledgers are single-sided**. The two-sided ledger needed by D3
is produced by ERP systems (Odoo, ERPNext, OpenBoxes) and usually is not published.

Which leaves the earlier conclusion standing, and sharper: the next real step is a ledger exported from
an ERP that records both sides of a movement, not another public CSV.

## Numbers

- movements: 600, products: 20, transfer records: 102
- largest single outflow: 15 units (Padlock 40 mm)

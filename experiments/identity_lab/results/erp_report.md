# Experiment J — an ERP-shaped export and the import contract

Odoo 17 demo data was parsed first: **16 locations, 20 quants, 23 products, zero movement
documents**. Demo data ships *states*, not movements — so it cannot exercise an edge at all.

A sample export in Odoo's own field names was then built (8 moves, all synthetic and labelled)
to prove the reader and the detector:

| quantity | value |
|---|---|
| moves | 10 (done: 8) |
| pickings | 4 |
| edges formed | 4 |
| D3 loss events | **1** |
| partial executions (demand > executed) | 2 |

## The quantity trap, and how it is closed

The sample contains a backorder: demand 30, executed 24, receiver records 24. With
`product_uom_qty` this would have been classified as a 6-unit loss. The reader uses
`quantity`, so that case is silent — and only the real mismatch (30 shipped, 24 received)
is reported.

## What this proves

The reader consumes Odoo's field names and yields edges the detector already understands,
with no change to the detector. A real export slots in as columns, not as a rewrite.

## What Odoo forces us to admit

In Odoo a single move carries **both ends** (`location_id`, `location_dest_id`). One system
therefore cannot produce a disagreement between two ends: they are the same record. The edge
becomes real only when a second, independent recording exists — the counterparty's receipt.

Which means the sample above is a *modelling* of that second record, not a discovery of one.
The contract says exactly which four extra fields make it real.

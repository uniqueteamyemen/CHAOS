# Derived ledger — a synthetic set built from Experiment H, clearly marked

Experiment H is frozen and unchanged. This is a **different** dataset, derived from H's
catalogue and real movement rows, with the two things H lacks added explicitly:

- a counted closing per product, generated as `implied − injected_loss + declared jitter`;
- paired transfers with a `transfer_id`, where the counterpart record is invented.

Every added or modified row carries `synthetic=1`, `derived_from=experiment_H` and its
derivation rule. Nothing here is presented as real-world validation.

| quantity | value |
|---|---|
| products | 20 |
| real movement rows reused | 600 |
| derived transfers | 68 |
| injected losses (declared) | 3 |
| **D1 alarms** | **3** (expected 3) |
| **D3 loss events** | **11** (expected 11) |
| D3 false losses | 0 |

## D1 — identity check per product

| product | residual | tolerance |
|---|---|---|
| Wood screws 4x40 box | 5.5 | 2.95 |
| Cable ties 200 mm bag | 8.5 | 2.85 |
| Masking tape 50 m | 11.5 | 2.0 |

## Reading

D1 and D3 both fire on the derived set, and only on the injected faults. That proves the
**plumbing**: with a counted closing and paired transfers, the engine runs end to end.

It proves nothing about detection rates. The faults were placed by this script, and the
counted closing was computed from the movements it is supposed to check — so the identity
is guaranteed to be closed except where we opened it. That is the honest status of any
synthetic test, and it is why the freeze on H matters: H holds the negative result that the
public data could not support these checks at all.

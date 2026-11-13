# Comparative A/B/C ERP reconciliation experiment

## Engines
- **A — Legacy:** frozen matching and loss-classification logic from commit `4c9ae2614aa290c4cf19c347129467f049d09867`. A compatibility adapter maps the historical `counterpart_picking_id == transfer_id` convention to the canonical `source_picking_id` field. The matching logic itself is not rewritten.
- **B — Hardened:** current `match_counterpart_receipts`.
- **C — Hybrid:** current `match_hybrid`, with candidate discovery separated from evidence-gated confirmation.

## Experimental controls
All engines receive the same 16 scenarios for each of 40 deterministic seeds (640 shipment cases). Ground truth is generated before scoring. Cases cover exact receipt, loss, over-receipt, multiple linked partial receipts, incomplete provenance, product/location conflicts, approximate unique candidates, multiple candidates, shared candidates, Odoo dozen conversion, date-window exclusion, duplicate receipt identity, wrong-product candidates, and unkeyed references.

Candidate tolerance is aligned at 2% around the fixed 10-unit shipment quantity. The hardened engine's absolute tolerance is therefore configured to 0.2 units. All engines use a 3-day candidate window. Loss scoring uses a shared 0.5-unit threshold. A's historical float conversion and matching semantics are retained in its isolated adapter.

## Integration boundary
The experiment imports the production-candidate B and C functions directly from the repository and invokes them on canonical Odoo-shaped shipment/receipt dictionaries with the same UoM registry. It does not connect to a live Odoo tenant, mutate records, or change the default runner. The existing Odoo reader plumbing fixture remains a separate CI check.

## Interpretation
The report distinguishes exact-confirmation precision/recall, loss precision/recall, candidate discovery counts, and runtime. Runtime is an in-process microbenchmark, not a deployment or throughput claim. The dataset is synthetic and adversarial; passing this experiment is a necessary comparative gate, not proof of production suitability.

### Candidate metric limitation
A's historical return contract exposes a single receipt for a unique candidate and only a count for ambiguous candidates; it does not expose a stable candidate-ID list for the latter. Candidate precision/recall are therefore reported as **N/A for A**, rather than inventing identity-level metrics. B and C expose candidate receipt IDs, so their identity-level discovery metrics are scored against the same ground truth.

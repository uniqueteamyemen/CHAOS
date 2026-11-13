# ERP A/B/C Shadow Mode

## Purpose and safety boundary

Shadow Mode evaluates A (frozen legacy matching semantics), B (hardened matcher), and C (hybrid matcher) against one exported Odoo snapshot. It is an offline, read-only evaluation harness: it does not connect to Odoo, call Odoo APIs, write records, reserve stock, create receipts, or promote an engine result into an operational action.

The runner is intentionally separate from the operational reconciliation entry points. Its outputs are observations and disagreements, not ground-truth accuracy claims.

## Input bundle

Provide a UTF-8 JSON file with this shape:

- schema_version: string, currently 1.0
- export_metadata: optional object describing export time, Odoo version, company scope, date range and export query/version
- moves: array of Odoo stock.move export rows
- uom_rows: array of Odoo uom.uom rows
- receipts: array of independently recorded receiving-side evidence rows

Required move fields are those consumed by aggregate_moves: picking_id, product_id, quantity (executed quantity), product_uom, product_uom_category_id, state, location_id, location_dest_id, date, and reference/name/origin where available. product_uom_qty is demand and is never substituted for quantity.

Required UoM rows: id, category_id, factor, uom_type. Export the reference UoM for every included category.

Receipt rows must preserve their own counterpart_picking_id and link to the source via source_picking_id when an explicit link exists. Include product_id, location_id, counterpart_qty, counterpart_uom_id, product_uom_category_id, counterpart_date, counterpart_system, counterpart_source and recorded_at. Do not manufacture missing source links or evidence metadata.

## Data handling

Before export, restrict the scope to the minimum date range and companies/products needed for the experiment. Replace partner, employee, customer, vendor and document identifiers with stable pseudonyms while preserving joins across the three datasets. Do not remove product identity, location relationships, dates, quantities, UoM IDs or evidence completeness indicators needed by the experiment. Keep the pseudonym mapping outside this repository and outside the report bundle.

Do not commit real ERP exports or reports containing sensitive business data. Keep input bundles and run outputs in a controlled local directory with appropriate access restrictions. The runner stores record identifiers in the disagreement report; pseudonymization is therefore required before execution.

## Execute

From the repository root:

    python -m experiments.identity_lab.exp_j_erp.shadow_mode --input /secure/path/odoo_shadow_bundle.json --output-root /secure/path/shadow_runs

The runner creates a new unique directory containing:
- manifest.json: run ID, mode, input hash and read-only guardrail
- shadow_report.json: per-engine results, counts, pairwise disagreements and evidence IDs
- comparison.md: concise comparison summary

It refuses to overwrite an existing run directory. Re-running the same bundle creates a new run while retaining the same canonical input SHA-256.

## Comparison rules

A, B and C receive deep-copied versions of the same canonical move, receipt and UoM rows. The input hash is checked after each engine run. B's absolute tolerance is set per shipment to equal 2% of its executed quantity, matching C's relative candidate tolerance and A's compatibility adapter. The date window is three days. C's reconciliation tolerance is 1%; loss classification threshold is 0.5 reference units.

Compare:
- confirmation state and evidence IDs
- candidate state and candidate receipt IDs
- loss claims
- ambiguous and unmatched cases
- pairwise state disagreements

A disagreement is an investigation item. Without independent ground truth, Shadow Mode cannot tell which engine is correct or claim precision/recall. Resolve a representative sample against signed receiving documents or an independently maintained receiving ledger before any operational approval.

## Operational gate

Shadow Mode must remain read-only. No engine is selected automatically. Do not integrate C into the write path based solely on shadow agreement or synthetic CI. Approval requires: validated real exports, stable results across an agreed observation window, adjudication of disagreement cases, documented false-positive/false-negative review, and a separate explicit production change review.
